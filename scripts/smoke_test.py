"""使用临时数据库启动真实 Uvicorn，验证 HTTP 流程后关闭进程。"""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent


def main():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"

    def request(method, path, data=None):
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = Request(base_url + path, data=body, method=method,
                      headers={"Content-Type": "application/json"} if body else {})
        with urlopen(req, timeout=2) as response:
            content = response.read()
            return response.status, json.loads(content) if content else None

    with tempfile.TemporaryDirectory(prefix="campus-smoke-") as directory:
        env = {**os.environ, "CAMPUS_DB_PATH": str(Path(directory) / "smoke.sqlite3")}
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
             "--port", str(port), "--no-proxy-headers"],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            expires = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Uvicorn exited before readiness")
                try:
                    status, health = request("GET", "/api/health")
                    assert status == 200 and health["database"] == "ok"
                    break
                except (URLError, TimeoutError):
                    if time.monotonic() >= expires:
                        raise RuntimeError("Uvicorn readiness timed out")
                    time.sleep(0.1)
            now = datetime.now(timezone.utc)
            data = {
                "title": "HTTP smoke activity", "club_name": "Demo Club", "category": "学术科技",
                "location": "Room 101", "description": "Real HTTP and SQLite verification", "capacity": 1,
                "starts_at": (now + timedelta(days=2)).isoformat(),
                "ends_at": (now + timedelta(days=2, hours=1)).isoformat(),
                "registration_deadline": (now + timedelta(days=1)).isoformat(),
            }
            status, item = request("POST", "/api/admin/activities", data)
            assert status == 201
            path = f"/api/activities/{item['id']}/registrations"
            participant = {"name": "Demo Student", "student_id": "SMOKE001", "contact": "demo@example.com"}
            assert request("POST", path, participant)[0] == 201
            try:
                request("POST", path, participant)
                raise AssertionError("duplicate was accepted")
            except HTTPError as exc:
                assert exc.code == 409
                assert json.loads(exc.read())["error"]["code"] == "ALREADY_REGISTERED"
                exc.close()
            status, roster = request("GET", f"/api/admin/activities/{item['id']}/registrations")
            assert status == 200 and roster["total"] == 1
            assert request("GET", "/api/admin/stats")[1]["registration_count"] == 1
            assert request("DELETE", f"/api/admin/activities/{item['id']}")[0] == 204
            assert request("GET", "/api/admin/stats")[1]["registration_count"] == 0
            print("PASS: real Uvicorn HTTP health/create/register/duplicate/roster/stats/delete/cascade")
        finally:
            process.terminate()
            try:
                logs, _ = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                logs, _ = process.communicate(timeout=5)
            if sys.exc_info()[0] is not None:
                print(logs.decode("utf-8", errors="replace"), file=sys.stderr)


if __name__ == "__main__":
    main()
