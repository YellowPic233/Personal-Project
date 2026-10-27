"""交付审查补充：从缺失目录启动、持久化、边界输入及浏览器管理边界。"""

import sqlite3

from fastapi.testclient import TestClient
import pytest

from app.main import create_app


def test_first_start_creates_missing_parent_and_persists_crud(tmp_path, activity_data, registration_data):
    database_path = tmp_path / "first-start" / "nested" / "campus.sqlite3"
    assert not database_path.parent.exists()
    application = create_app(database_path)
    assert not database_path.exists()  # 导入/构造应用不应提前写库。
    options = {"base_url": "http://127.0.0.1", "client": ("127.0.0.1", 50000)}
    with TestClient(application, **options) as client:
        assert database_path.is_file()
        assert client.get("/api/health").status_code == 200
        created = client.post("/api/admin/activities", json=activity_data)
        assert created.status_code == 201
        activity_id = created.json()["id"]
        updated = {**activity_data, "title": "交付审查：修改已落库"}
        assert client.put(f"/api/admin/activities/{activity_id}", json=updated).status_code == 200
        assert client.post(f"/api/activities/{activity_id}/registrations", json=registration_data).status_code == 201
    # 关闭原客户端、建立新应用，排除依赖内存缓存的假持久化。
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT title FROM activities WHERE id=?", (activity_id,)).fetchone()[0] == updated["title"]
        assert connection.execute("SELECT COUNT(*) FROM registrations").fetchone()[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    with TestClient(create_app(database_path), **options) as restarted:
        detail = restarted.get(f"/api/activities/{activity_id}").json()
        assert detail["title"] == updated["title"]
        assert detail["registration_count"] == 1
        roster = restarted.get(f"/api/admin/activities/{activity_id}/registrations").json()
        assert roster["items"][0]["student_id"] == registration_data["student_id"]
        assert restarted.post(f"/api/activities/{activity_id}/registrations", json=registration_data).status_code == 409
        assert restarted.delete(f"/api/admin/activities/{activity_id}").status_code == 204
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM registrations").fetchone()[0] == 0


@pytest.mark.parametrize("method,path,body_kind", [
    ("GET", "/api/activities/{id}", None),
    ("GET", "/api/admin/activities/{id}/registrations", None),
    ("PUT", "/api/admin/activities/{id}", "activity"),
    ("DELETE", "/api/admin/activities/{id}", None),
    ("POST", "/api/activities/{id}/registrations", "registration"),
])
def test_ids_outside_sqlite_integer_range_return_422(client, activity_data, registration_data, method, path, body_kind):
    kwargs = {} if body_kind is None else {"json": activity_data if body_kind == "activity" else registration_data}
    response = client.request(method, path.format(id=2**63), **kwargs)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("field,value", [
    ("starts_at", "0001-01-01T00:00:00+14:00"),
    ("ends_at", "9999-12-31T23:59:59-08:00"),
    ("registration_deadline", "0001-01-01T00:00:00+14:00"),
])
def test_utc_overflow_is_validation_error(client, activity_data, field, value):
    response = client.post("/api/admin/activities", json={**activity_data, field: value})
    assert response.status_code == 422
    assert client.get("/api/activities").json()["total"] == 0


@pytest.mark.parametrize("field", ["title", "club_name", "location", "description"])
def test_null_characters_rejected_before_sqlite(client, activity_data, field):
    response = client.post("/api/admin/activities", json={**activity_data, field: "\x00invalid"})
    assert response.status_code == 422
    assert client.get("/api/activities").json()["total"] == 0


def test_null_character_registration_rejected(client, create_activity, registration_data):
    activity = create_activity()
    response = client.post(f"/api/activities/{activity['id']}/registrations", json={**registration_data, "name": "\x00invalid"})
    assert response.status_code == 422
    assert client.get(f"/api/activities/{activity['id']}").json()["registration_count"] == 0


@pytest.mark.parametrize("path", ["/static/ADMIN.HTML", "/static/css/%2e%2e/admin.html"])
def test_admin_static_aliases_do_not_bypass_local_guard(application, path):
    with TestClient(application, base_url="http://localhost", client=("203.0.113.10", 50000)) as remote:
        response = remote.get(path)
        assert response.status_code in {403, 404}
        assert "<html" not in response.text.lower()


def test_management_ui_cannot_be_embedded_by_other_sites(client):
    response = client.get("/admin")
    assert response.headers.get("x-frame-options") == "DENY"
    assert "frame-ancestors 'none'" in response.headers.get("content-security-policy", "")
