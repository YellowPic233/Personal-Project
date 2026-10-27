from typing import Annotated

from fastapi import APIRouter, Query, Response

from ..schemas import ActivityInput, ActivityOut, ActivityPage, Category, RegistrationPage, StatsOut
from .activities import ActivityId, Page, PageSize, Service

router = APIRouter(prefix="/api/admin", tags=["本地管理"])


@router.get("/activities", response_model=ActivityPage, summary="管理活动列表")
def list_activities(service: Service, q: Annotated[str | None, Query(max_length=100)] = None,
                    category: Category | None = None, page: Page = 1, page_size: PageSize = 20):
    return service.list_activities(q.strip() if q else None, category, page, page_size)


@router.post("/activities", response_model=ActivityOut, status_code=201, summary="创建活动")
def create_activity(data: ActivityInput, service: Service):
    return service.create_activity(data)


@router.put("/activities/{activity_id}", response_model=ActivityOut, summary="完整更新活动")
def update_activity(activity_id: ActivityId, data: ActivityInput, service: Service):
    return service.update_activity(activity_id, data)


@router.delete("/activities/{activity_id}", status_code=204, summary="删除活动及关联报名")
def delete_activity(activity_id: ActivityId, service: Service):
    service.delete_activity(activity_id)
    return Response(status_code=204)


@router.get("/activities/{activity_id}/registrations", response_model=RegistrationPage, summary="分页查看报名名单")
def list_registrations(activity_id: ActivityId, service: Service, page: Page = 1, page_size: PageSize = 20):
    return service.list_registrations(activity_id, page, page_size)


@router.get("/stats", response_model=StatsOut, summary="活动与报名统计")
def stats(service: Service):
    return service.stats()
