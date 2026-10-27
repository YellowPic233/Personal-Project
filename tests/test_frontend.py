from fastapi.testclient import TestClient
import pytest


@pytest.mark.parametrize("path,module", [("/", "activities.js"), ("/activities/1", "activity.js"), ("/admin", "admin.js")])
def test_pages_and_modules_are_served(client, path, module):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'lang="zh-CN"' in response.text
    assert f'/static/js/{module}' in response.text
    assert client.get(f"/static/js/{module}").status_code == 200
    assert client.get("/static/css/styles.css").status_code == 200
    assert client.get("/static/favicon.svg").status_code == 200


@pytest.mark.parametrize("path", ["/admin", "/admin/", "/static/admin.html"])
def test_admin_html_is_local_only(application, path):
    with TestClient(application, base_url="http://localhost", client=("203.0.113.1", 50000)) as remote:
        response = remote.get(path)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ADMIN_LOCAL_ONLY"


def test_admin_page_not_cached(client):
    assert client.get("/admin").headers["cache-control"] == "no-store"
    assert client.get("/static/admin.html").headers["cache-control"] == "no-store"


def test_public_pages_and_static_assets_revalidate(client):
    for path in ("/", "/activities/1", "/static/js/ui.js", "/static/css/styles.css?v=20261027"):
        assert client.get(path).headers["cache-control"] == "no-cache"
