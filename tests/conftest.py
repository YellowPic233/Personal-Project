from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from app.main import create_app


@pytest.fixture
def application(tmp_path):
    return create_app(tmp_path / "test.sqlite3")


@pytest.fixture
def client(application):
    # 使用真实的回环地址，不关闭或绕过本机访问保护；with 会执行 lifespan。
    with TestClient(application, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as test_client:
        yield test_client


@pytest.fixture
def activity_data():
    now = datetime.now(timezone.utc)
    return {
        "title": "校园摄影分享会",
        "club_name": "摄影社",
        "category": "文艺体育",
        "location": "学生活动中心 201",
        "description": "交流校园摄影经验，欢迎同学参加。",
        "capacity": 3,
        "starts_at": (now + timedelta(days=3)).isoformat(),
        "ends_at": (now + timedelta(days=3, hours=2)).isoformat(),
        "registration_deadline": (now + timedelta(days=2)).isoformat(),
    }


@pytest.fixture
def registration_data():
    return {"name": "张同学", "student_id": "20260001", "contact": "student@example.com"}


@pytest.fixture
def create_activity(client, activity_data):
    def create(**overrides):
        response = client.post("/api/admin/activities", json={**activity_data, **overrides})
        assert response.status_code == 201, response.text
        return response.json()
    return create
