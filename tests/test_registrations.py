from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest

from app import services


def test_registration_list_and_public_privacy(client, create_activity, registration_data):
    activity = create_activity()
    url = f"/api/activities/{activity['id']}/registrations"
    result = client.post(url, json={**registration_data, "name": "  张同学  ", "student_id": " stu001 "})
    assert result.status_code == 201
    assert result.json()["name"] == "张同学"
    assert result.json()["student_id"] == "STU001"
    assert result.headers["cache-control"] == "no-store"
    public = client.get(f"/api/activities/{activity['id']}")
    assert public.json()["registration_count"] == 1
    assert public.json()["remaining_capacity"] == 2
    assert registration_data["contact"] not in public.text
    assert "STU001" not in public.text
    # 不存在公开 GET 名单路由；名单只有本地管理路径。
    assert client.get(url).status_code == 405
    roster = client.get(f"/api/admin/activities/{activity['id']}/registrations")
    assert roster.status_code == 200
    assert roster.json()["items"] == [result.json()]
    assert roster.json()["total"] == 1
    assert roster.headers["cache-control"] == "no-store"


def test_duplicate_id_is_case_insensitive_and_can_join_other_activity(client, create_activity, registration_data):
    first, second = create_activity(), create_activity()
    url = f"/api/activities/{first['id']}/registrations"
    assert client.post(url, json={**registration_data, "student_id": "abc001"}).status_code == 201
    duplicate = client.post(url, json={**registration_data, "student_id": "ABC001"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ALREADY_REGISTERED"
    assert client.post(f"/api/activities/{second['id']}/registrations", json={**registration_data, "student_id": "abc001"}).status_code == 201
    assert client.get(f"/api/activities/{first['id']}").json()["registration_count"] == 1


def test_capacity_and_duplicate_have_no_extra_writes(client, create_activity, registration_data):
    activity = create_activity(capacity=1)
    url = f"/api/activities/{activity['id']}/registrations"
    assert client.post(url, json=registration_data).status_code == 201
    assert client.post(url, json=registration_data).json()["error"]["code"] == "ALREADY_REGISTERED"
    full = client.post(url, json={**registration_data, "student_id": "second"})
    assert full.status_code == 409
    assert full.json()["error"]["code"] == "ACTIVITY_FULL"
    details = client.get(f"/api/activities/{activity['id']}").json()
    assert details["remaining_capacity"] == 0
    assert details["registration_count"] == 1
    assert details["registration_status"] == "full"


@pytest.mark.parametrize("data", [
    {}, {"name": "A"}, {"name": "", "student_id": "S", "contact": "x"},
    {"name": "A", "student_id": "", "contact": "x"},
    {"name": "A", "student_id": "S", "contact": "  "},
    {"name": "A", "student_id": "x' OR 1=1", "contact": "x"},
    {"name": "x" * 51, "student_id": "S", "contact": "x"},
    {"name": "A", "student_id": "S" * 33, "contact": "x"},
    {"name": "A", "student_id": 1234, "contact": "x"},
    {"name": "A", "student_id": "S", "contact": "x" * 101},
    {"name": "A", "student_id": "S", "contact": "x", "activity_id": 2},
])
def test_invalid_registration(client, create_activity, data):
    activity = create_activity()
    response = client.post(f"/api/activities/{activity['id']}/registrations", json=data)
    assert response.status_code == 422
    assert client.get(f"/api/activities/{activity['id']}").json()["registration_count"] == 0


@pytest.mark.parametrize("at_start", [False, True])
def test_deadline_and_started_activity(client, create_activity, registration_data, at_start):
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=1) if at_start else now + timedelta(days=1)
    activity = create_activity(starts_at=start.isoformat(), ends_at=(start + timedelta(hours=2)).isoformat(),
                               registration_deadline=(now - timedelta(hours=2)).isoformat())
    response = client.post(f"/api/activities/{activity['id']}/registrations", json=registration_data)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REGISTRATION_CLOSED"
    assert client.get(f"/api/activities/{activity['id']}").json()["registration_status"] == "closed"


def test_exact_deadline_boundary(client, create_activity, registration_data, monkeypatch):
    activity = create_activity()
    deadline = datetime.fromisoformat(activity["registration_deadline"])
    monkeypatch.setattr(services, "utc_now", lambda: deadline)
    response = client.post(f"/api/activities/{activity['id']}/registrations", json=registration_data)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REGISTRATION_CLOSED"


def test_capacity_update_and_roster_pagination(client, create_activity, activity_data, registration_data):
    activity = create_activity()
    activity_id = activity["id"]
    for number in range(2):
        assert client.post(f"/api/activities/{activity_id}/registrations",
                           json={**registration_data, "student_id": f"S{number}"}).status_code == 201
    conflict = client.put(f"/api/admin/activities/{activity_id}", json={**activity_data, "capacity": 1, "title": "不应保存"})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "CAPACITY_BELOW_REGISTRATIONS"
    assert client.get(f"/api/activities/{activity_id}").json()["title"] == activity["title"]
    assert client.put(f"/api/admin/activities/{activity_id}", json={**activity_data, "capacity": 2}).status_code == 200
    assert client.get(f"/api/activities/{activity_id}").json()["registration_status"] == "full"
    assert client.put(f"/api/admin/activities/{activity_id}", json={**activity_data, "capacity": 4}).status_code == 200
    assert client.get(f"/api/activities/{activity_id}").json()["registration_status"] == "open"
    page = client.get(f"/api/admin/activities/{activity_id}/registrations", params={"page": 2, "page_size": 1}).json()
    assert page["total"] == 2
    assert page["items"][0]["student_id"] == "S1"
    assert client.get(f"/api/admin/activities/{activity_id}/registrations", params={"page_size": 101}).status_code == 422


@pytest.mark.parametrize("same_student", [False, True])
def test_concurrent_requests_cannot_overbook_or_duplicate(client, create_activity, registration_data, same_student):
    # 多个真实 HTTP TestClient 请求从不同线程同时进入独立 SQLite 连接。
    activity = create_activity(capacity=10 if same_student else 1)
    barrier = Barrier(6)
    def submit(number):
        barrier.wait(timeout=10)
        student = "SAME" if same_student else f"S{number}"
        return client.post(f"/api/activities/{activity['id']}/registrations", json={**registration_data, "student_id": student})
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(submit, range(6)))
    assert sorted(response.status_code for response in responses) == [201, 409, 409, 409, 409, 409]
    expected_code = "ALREADY_REGISTERED" if same_student else "ACTIVITY_FULL"
    assert all(response.json()["error"]["code"] == expected_code for response in responses if response.status_code == 409)
    assert client.get(f"/api/activities/{activity['id']}").json()["registration_count"] == 1


def test_capacity_reduction_racing_registration(client, create_activity, activity_data, registration_data):
    activity = create_activity(capacity=3)
    url = f"/api/activities/{activity['id']}/registrations"
    assert client.post(url, json=registration_data).status_code == 201
    barrier = Barrier(2)
    def change_capacity():
        barrier.wait(timeout=10)
        return client.put(f"/api/admin/activities/{activity['id']}", json={**activity_data, "capacity": 1})
    def register_next():
        barrier.wait(timeout=10)
        return client.post(url, json={**registration_data, "student_id": "NEXT"})
    with ThreadPoolExecutor(max_workers=2) as pool:
        update = pool.submit(change_capacity)
        registration = pool.submit(register_next)
        outcomes = (update.result().status_code, registration.result().status_code)
    assert outcomes in {(200, 409), (409, 201)}
    final = client.get(f"/api/activities/{activity['id']}").json()
    assert final["registration_count"] <= final["capacity"]
