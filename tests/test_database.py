import sqlite3

from fastapi.testclient import TestClient
import pytest

from app.main import create_app


def test_health_and_empty_initialization(client, application):
    assert client.get("/api/health").json() == {"status": "ok", "database": "ok"}
    assert client.get("/api/activities").json()["total"] == 0
    application.state.database.initialize()
    assert client.get("/api/admin/stats").json() == {
        "activity_count": 0, "registration_count": 0, "unique_student_count": 0, "activities": []
    }


def test_restart_preserves_data(client, application, create_activity, registration_data):
    activity = create_activity()
    assert client.post(f"/api/activities/{activity['id']}/registrations", json=registration_data).status_code == 201
    second_app = create_app(application.state.database.path)
    with TestClient(second_app, base_url="http://localhost", client=("127.0.0.1", 50001)) as restarted:
        item = restarted.get(f"/api/activities/{activity['id']}").json()
        assert item["title"] == activity["title"]
        assert item["registration_count"] == 1


def test_database_foreign_key_unique_and_check_constraints(client, application, create_activity, registration_data):
    activity = create_activity()
    client.post(f"/api/activities/{activity['id']}/registrations", json=registration_data)
    with application.state.database.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO registrations(activity_id,name,student_id,contact,created_at) VALUES(99999,'A','X','a','now')")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("""INSERT INTO registrations(activity_id,name,student_id,contact,created_at)
                                  SELECT activity_id,name,student_id,contact,created_at FROM registrations""")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE activities SET capacity = 0")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE activities SET ends_at = starts_at")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_transaction_rolls_back(client, application, create_activity):
    activity = create_activity()
    with pytest.raises(RuntimeError):
        with application.state.database.transaction(write=True) as connection:
            connection.execute("DELETE FROM activities WHERE id = ?", (activity["id"],))
            raise RuntimeError("simulate interruption")
    assert client.get(f"/api/activities/{activity['id']}").status_code == 200


def test_static_mount_and_no_database_exposure(tmp_path):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "probe.txt").write_text("static mount works", encoding="utf-8")
    app = create_app(tmp_path / "private.sqlite3", static_dir=static_dir)
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 1)) as client:
        assert client.get("/static/probe.txt").text == "static mount works"
        for url in ("/static/private.sqlite3", "/static/%2e%2e/private.sqlite3", "/data/campus.sqlite3"):
            assert client.get(url).status_code == 404
        assert client.get("/").status_code == 200
        assert client.get("/openapi.json").status_code == 200


def test_database_busy_returns_retryable_error(client, application, create_activity, registration_data, monkeypatch):
    activity = create_activity()
    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked: private-path")
    monkeypatch.setattr(application.state.service, "register", unavailable)
    response = client.post(f"/api/activities/{activity['id']}/registrations", json=registration_data)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert response.headers["retry-after"] == "1"
    assert "private-path" not in response.text
