from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from ..schemas import ActivityOut, ActivityPage, Category, RegistrationInput, RegistrationOut
from ..services import ActivityService

router = APIRouter(prefix="/api", tags=["公开活动与报名"])


def get_service(request: Request) -> ActivityService:
    return request.app.state.service


Service = Annotated[ActivityService, Depends(get_service)]
ActivityId = Annotated[int, Path(ge=1)]
Page = Annotated[int, Query(ge=1, le=1000000)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/health", summary="服务和数据库健康检查")
def health(request: Request):
    with request.app.state.database.connect() as connection:
        connection.execute("SELECT id FROM activities LIMIT 1").fetchall()
    return {"status": "ok", "database": "ok"}


@router.get("/categories", response_model=list[Category], summary="获取固定分类")
def categories():
    return list(Category)


@router.get("/activities", response_model=ActivityPage, summary="搜索、筛选和分页查询活动")
def list_activities(service: Service, q: Annotated[str | None, Query(max_length=100)] = None,
                    category: Category | None = None, page: Page = 1, page_size: PageSize = 20):
    return service.list_activities(q.strip() if q else None, category, page, page_size)


@router.get("/activities/{activity_id}", response_model=ActivityOut, summary="查看活动详情和剩余名额")
def get_activity(activity_id: ActivityId, service: Service):
    return service.get_activity(activity_id)


@router.post("/activities/{activity_id}/registrations", response_model=RegistrationOut,
             status_code=201, summary="报名活动")
def register(activity_id: ActivityId, data: RegistrationInput, service: Service):
    return service.register(activity_id, data)
