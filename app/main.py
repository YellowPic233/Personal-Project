from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import Database
from .errors import install_error_handlers
from .routers import activities, admin
from .security import local_demo_guard
from .services import ActivityService

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(database_path: str | Path | None = None, *, static_dir: str | Path | None = None) -> FastAPI:
    """测试可注入临时数据库和静态目录；导入模块本身不会写入数据库。"""
    database = Database(database_path if database_path is not None else os.environ.get(
        "CAMPUS_DB_PATH", str(PROJECT_ROOT / "data" / "campus.sqlite3")
    ))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.initialize()
        yield

    app = FastAPI(title="校园社团活动发布与报名管理系统", version="0.1.0", lifespan=lifespan)
    app.state.database = database
    app.state.service = ActivityService(database)
    install_error_handlers(app)
    app.middleware("http")(local_demo_guard)
    app.include_router(activities.router)
    app.include_router(admin.router)

    @app.get("/", include_in_schema=False)
    def root():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/activities/{activity_id}", include_in_schema=False)
    def activity_page(activity_id: int):
        return FileResponse(STATIC_DIR / "activity.html")

    @app.get("/admin", include_in_schema=False)
    def admin_page():
        return FileResponse(STATIC_DIR / "admin.html")

    # 只挂载专用资源目录，不把项目根目录或 SQLite 文件暴露为静态文件。
    # HTML 页面和资源均与 API 同源，不依赖前端构建工具或外部 CDN。
    app.mount("/static", StaticFiles(directory=static_dir or STATIC_DIR), name="static")
    return app


app = create_app()
