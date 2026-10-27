from fastapi.testclient import TestClient
import pytest


def test_stats_and_delete_cascade(client, application, create_activity, registration_data):
    first, second, empty = create_activity(), create_activity(), create_activity()
    for activity, student in ((first, "S1"), (first, "S2"), (second, "S1")):
        assert client.post(f"/api/activities/{activity['id']}/registrations", json={**registration_data, "student_id": student}).status_code == 201
    stats = client.get("/api/admin/stats").json()
    assert stats["activity_count"] == 3
    assert stats["registration_count"] == 3
    assert stats["unique_student_count"] == 2
    assert [row["registration_count"] for row in stats["activities"]] == [2, 1, 0]
    assert [row["remaining_capacity"] for row in stats["activities"]] == [1, 2, 3]
    assert client.delete(f"/api/admin/activities/{first['id']}").status_code == 204
    stats = client.get("/api/admin/stats").json()
    assert (stats["activity_count"], stats["registration_count"], stats["unique_student_count"]) == (2, 1, 1)
    with application.state.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM registrations WHERE activity_id = ?", (first["id"],)).fetchone()[0] == 0


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/admin/stats"), ("GET", "/api/admin/activities"),
    ("POST", "/api/admin/activities"), ("PUT", "/api/admin/activities/1"),
    ("DELETE", "/api/admin/activities/1"), ("GET", "/api/admin/activities/1/registrations"),
])
def test_remote_clients_cannot_access_any_admin_api(application, method, path):
    with TestClient(application, base_url="http://localhost", client=("203.0.113.1", 50000)) as remote:
        response = remote.request(method, path)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ADMIN_LOCAL_ONLY"
        # 伪造代理头不能将远端请求变成本地管理请求。
        assert remote.request(method, path, headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 403


@pytest.mark.parametrize("header", ["Forwarded", "X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto"])
def test_admin_rejects_forwarded_requests(client, header):
    response = client.get("/api/admin/stats", headers={header: "127.0.0.1"})
    assert response.status_code == 403


@pytest.mark.parametrize("host", ["evil.example", "localhost.evil.example", "127.0.0.1.evil.example", "user@localhost",
                                  "[broken", "localhost:invalid", "localhost:99999"])
def test_untrusted_host_is_rejected(client, host):
    response = client.get("/api/admin/stats", headers={"Host": host})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNTRUSTED_HOST"


@pytest.mark.parametrize("headers", [
    {"Origin": "https://evil.example"}, {"Origin": "null"},
    {"Origin": "http://127.0.0.1:8001"}, {"Origin": "http://localhost"},
    {"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "same-site"},
])
def test_cross_origin_writes_rejected(client, activity_data, headers):
    response = client.post("/api/admin/activities", json=activity_data, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNTRUSTED_ORIGIN"
    assert client.get("/api/activities").json()["total"] == 0


def test_same_origin_and_ipv6_loopback_are_allowed(client, activity_data, application):
    response = client.post("/api/admin/activities", json=activity_data,
                           headers={"Origin": "http://127.0.0.1", "Sec-Fetch-Site": "same-origin"})
    assert response.status_code == 201
    with TestClient(application, base_url="http://[::1]:8000", client=("::1", 50000)) as ipv6:
        assert ipv6.get("/api/admin/stats").status_code == 200


def test_public_registration_also_checks_origin(client, create_activity, registration_data):
    activity = create_activity()
    response = client.post(f"/api/activities/{activity['id']}/registrations", json=registration_data,
                           headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert client.get(f"/api/activities/{activity['id']}").json()["registration_count"] == 0
