"""通过真实 TCP/HTTP 和独立 Uvicorn 进程验证交付流程。"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent


def test_live_http_crud_registration_and_process_restart(tmp_path, activity_data, registration_data):
    database_path = tmp_path / "missing-data-directory" / "campus.sqlite3"
    assert not database_path.parent.exists()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"

    def request(method, path, data=None, headers=None):
        body = json.dumps(data).encode("utf-8") if data is not None else None
        request_headers = {"Content-Type": "application/json"} if body is not None else {}
        request_headers.update(headers or {})
        req = Request(base_url + path, data=body, method=method, headers=request_headers)
        try:
            response = urlopen(req, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            content = response.read()
            parsed = json.loads(content) if content and "application/json" in response.headers.get("Content-Type", "") else content.decode("utf-8")
            return response.status, parsed, response.headers

    @contextmanager
    def running_server(run_number):
        log_path = tmp_path / f"uvicorn-{run_number}.log"
        env = {**os.environ, "CAMPUS_DB_PATH": str(database_path)}
        with log_path.open("w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                 "--port", str(port), "--no-proxy-headers"],
                cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            try:
                deadline = time.monotonic() + 15
                while True:
                    assert process.poll() is None, log_path.read_text(encoding="utf-8")
                    try:
                        assert request("GET", "/api/health")[0] == 200
                        break
                    except (URLError, TimeoutError):
                        assert time.monotonic() < deadline, log_path.read_text(encoding="utf-8")
                        time.sleep(0.1)
                yield
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        logs = log_path.read_text(encoding="utf-8")
        assert "Traceback" not in logs and "ERROR:" not in logs, logs

    with running_server(1):
        assert database_path.is_file()
        assert request("GET", "/api/activities")[1]["total"] == 0
        assert request("GET", "/")[0] == 200
        status, activity, _ = request("POST", "/api/admin/activities", {**activity_data, "capacity": 1})
        assert status == 201
        activity_id = activity["id"]
        assert request("GET", "/api/activities")[1]["items"][0]["id"] == activity_id
        edited = {**activity_data, "title": "真实 HTTP 交付审查", "capacity": 1}
        assert request("PUT", f"/api/admin/activities/{activity_id}", edited)[0] == 200
        assert request("GET", f"/api/activities/{activity_id}")[1]["title"] == edited["title"]
        path = f"/api/activities/{activity_id}/registrations"
        assert request("POST", path, registration_data)[0] == 201
        status, duplicate, _ = request("POST", path, registration_data)
        assert status == 409 and duplicate["error"]["code"] == "ALREADY_REGISTERED"
        status, full, _ = request("POST", path, {**registration_data, "student_id": "SECOND_STUDENT"})
        assert status == 409 and full["error"]["code"] == "ACTIVITY_FULL"
        assert request("POST", "/api/admin/activities", {**edited, "capacity": 0})[0] == 422
        assert request("GET", f"/api/activities/{2**63}")[0] == 422
        assert request("GET", "/api/activities/999999")[0] == 404
        assert request("POST", "/api/admin/activities", edited, {"Origin": "https://untrusted.example"})[0] == 403
        assert request("GET", "/api/admin/stats", headers={"X-Forwarded-For": "127.0.0.1"})[0] == 403

    # 原服务进程已经退出；直接检查文件，再启动全新服务进程。
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM registrations").fetchone()[0] == 1
    with running_server(2):
        detail = request("GET", f"/api/activities/{activity_id}")[1]
        assert detail["title"] == edited["title"]
        assert detail["registration_count"] == 1 and detail["remaining_capacity"] == 0
        roster = request("GET", f"/api/admin/activities/{activity_id}/registrations")[1]
        assert roster["total"] == 1 and roster["items"][0]["student_id"] == registration_data["student_id"]
        assert request("POST", path, registration_data)[1]["error"]["code"] == "ALREADY_REGISTERED"
        assert request("GET", "/api/admin/stats")[1]["registration_count"] == 1
        assert request("DELETE", f"/api/admin/activities/{activity_id}")[0] == 204
        assert request("GET", f"/api/activities/{activity_id}")[0] == 404
        assert request("GET", "/api/admin/stats")[1]["registration_count"] == 0
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM registrations").fetchone()[0] == 0
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
