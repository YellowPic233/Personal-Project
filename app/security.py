"""只适用于本机演示，不是公网身份认证机制。"""

from ipaddress import ip_address
from urllib.parse import urlsplit

from fastapi import Request

from .errors import error_response

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
FORWARDED_HEADERS = {"forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto"}


def local_client(request: Request) -> bool:
    try:
        return bool(request.client and ip_address(request.client.host).is_loopback)
    except ValueError:
        return False


def parse_origin(value: str):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return None
        return (parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == "https" else 80))
    except ValueError:
        return None


async def local_demo_guard(request: Request, call_next):
    host_headers = request.headers.getlist("host")
    # 从 ASGI scope 读取 scheme/path，避免畸形 Host 让 URL 解析先抛异常。
    origin = parse_origin(f"{request.scope['scheme']}://{host_headers[0]}") if len(host_headers) == 1 else None
    if origin is None or origin[1] not in LOCAL_HOSTS:
        return error_response(403, "UNTRUSTED_HOST", "仅允许使用本机地址访问。")

    path = request.scope["path"]
    is_admin = path == "/api/admin" or path.startswith("/api/admin/") or path.rstrip("/") in {"/admin", "/static/admin.html"}
    if is_admin:
        if not local_client(request) or any(header in request.headers for header in FORWARDED_HEADERS):
            return error_response(403, "ADMIN_LOCAL_ONLY", "管理接口仅允许本机直接访问。")

    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and path.startswith("/api/"):
        if request.headers.get("sec-fetch-site") not in {None, "same-origin", "none"}:
            return error_response(403, "UNTRUSTED_ORIGIN", "不允许跨站写入请求。")
        origins = request.headers.getlist("origin")
        if origins and (len(origins) != 1 or parse_origin(origins[0]) != origin):
            return error_response(403, "UNTRUSTED_ORIGIN", "不允许跨站写入请求。")

    response = await call_next(request)
    if is_admin or path.endswith("/registrations"):
        response.headers["Cache-Control"] = "no-store"
    elif path.startswith("/static/") or path == "/" or path.startswith("/activities/"):
        # 原生模块无打包哈希：每次使用前重新验证，避免修改后继续展示旧脚本。
        response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
