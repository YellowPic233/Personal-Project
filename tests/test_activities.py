from datetime import datetime, timedelta, timezone

import pytest


def test_activity_crud(client, create_activity, activity_data):
    item = create_activity(title="  摄影入门  ")
    activity_id = item["id"]
    assert item["title"] == "摄影入门"
    assert item["registration_count"] == 0
    assert item["remaining_capacity"] == 3
    assert item["registration_status"] == "open"
    assert client.get(f"/api/activities/{activity_id}").json() == item
    assert client.get("/api/admin/activities").json()["items"] == [item]
    updated = client.put(f"/api/admin/activities/{activity_id}", json={**activity_data, "title": "摄影进阶", "capacity": 5})
    assert updated.status_code == 200
    assert updated.json()["title"] == "摄影进阶"
    assert updated.json()["created_at"] == item["created_at"]
    assert updated.json()["updated_at"] >= item["updated_at"]
    deleted = client.delete(f"/api/admin/activities/{activity_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/api/activities/{activity_id}").status_code == 404
    assert client.get("/api/activities").json()["total"] == 0


def test_search_categories_pagination_and_sql_safety(client, create_activity):
    first = create_activity(title="AI 入门", category="学术科技", description="机器学习分享")
    create_activity(title="志愿者交流", club_name="校园公益协会", category="志愿公益")
    create_activity(title="摄影_100%")
    assert len(client.get("/api/categories").json()) == 5
    for query in ("AI", "机器学习"):
        response = client.get("/api/activities", params={"q": query, "category": "学术科技"})
        assert response.status_code == 200
        assert [row["id"] for row in response.json()["items"]] == [first["id"]]
    assert client.get("/api/activities", params={"q": "校园公益"}).json()["total"] == 1
    assert client.get("/api/activities", params={"q": "%"}).json()["total"] == 1
    assert client.get("/api/activities", params={"q": "_"}).json()["total"] == 1
    assert client.get("/api/activities", params={"q": "' OR 1=1 --"}).json()["total"] == 0
    assert client.get("/api/activities", params={"q": "不存在"}).json()["items"] == []
    page = client.get("/api/activities", params={"page_size": 2}).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    second_page = client.get("/api/activities", params={"page_size": 2, "page": 2}).json()
    assert len(second_page["items"]) == 1
    assert set(row["id"] for row in page["items"]).isdisjoint(row["id"] for row in second_page["items"])


@pytest.mark.parametrize("field,value", [
    ("title", "  "), ("title", "x" * 101), ("club_name", ""), ("location", ""),
    ("description", ""), ("description", "x" * 5001), ("category", "未定义分类"),
    ("capacity", 0), ("capacity", -1), ("capacity", 100001), ("capacity", True),
    ("capacity", 1.5), ("capacity", "3"), ("starts_at", "not-a-date"),
    ("starts_at", "2030-01-01T10:00:00"), ("starts_at", 1900000000),
    ("registration_deadline", None), ("unexpected", "value"),
])
def test_invalid_activity_fields(client, activity_data, field, value):
    response = client.post("/api/admin/activities", json={**activity_data, field: value})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"]
    assert client.get("/api/activities").json()["total"] == 0


def test_missing_fields_and_invalid_time_order(client, activity_data, create_activity):
    assert client.post("/api/admin/activities", json={}).status_code == 422
    assert client.post("/api/admin/activities", json={**activity_data, "ends_at": activity_data["starts_at"]}).status_code == 422
    assert client.post("/api/admin/activities", json={**activity_data, "registration_deadline": activity_data["ends_at"]}).status_code == 422
    item = create_activity()
    assert client.put(f"/api/admin/activities/{item['id']}", json={"title": "不能部分更新"}).status_code == 422
    assert client.get(f"/api/activities/{item['id']}").json()["title"] == item["title"]


def test_timezones_are_normalized_before_comparing(client, create_activity):
    start = datetime.now(timezone(timedelta(hours=8))) + timedelta(days=3)
    item = create_activity(starts_at=start.isoformat(),
                           ends_at=(start.astimezone(timezone.utc) + timedelta(hours=1)).isoformat(),
                           registration_deadline=(start - timedelta(days=1)).isoformat())
    assert datetime.fromisoformat(item["starts_at"]) == start
    assert item["starts_at"].endswith("Z")


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101},
                                      {"category": "无效"}, {"q": "x" * 101}, {"page": "abc"}])
def test_invalid_list_parameters(client, params):
    assert client.get("/api/activities", params=params).status_code == 422


def test_missing_activity(client, activity_data, registration_data):
    for method, url, kwargs in (
        ("get", "/api/activities/999", {}),
        ("put", "/api/admin/activities/999", {"json": activity_data}),
        ("delete", "/api/admin/activities/999", {}),
        ("post", "/api/activities/999/registrations", {"json": registration_data}),
        ("get", "/api/admin/activities/999/registrations", {}),
    ):
        response = client.request(method, url, **kwargs)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ACTIVITY_NOT_FOUND"
    assert client.get("/api/activities/0").status_code == 422
    assert client.get("/api/activities/abc").status_code == 422


def test_malformed_json_and_method_error(client):
    response = client.post("/api/admin/activities", content="{broken", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    response = client.patch("/api/admin/activities/1")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
