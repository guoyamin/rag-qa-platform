"""
智能问答平台 - 公告管理 API 路由
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.models.announcement import AnnouncementStatus, AnnouncementType
from app.models.user import User
from app.schemas import PaginationParams
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementListResponse,
    AnnouncementResponse,
    AnnouncementUpdate,
)
from app.services.announcement_service import AnnouncementService

router = APIRouter(prefix="/announcements", tags=["公告管理"])


@router.get("", response_model=AnnouncementListResponse)
async def list_announcements(
    pagination: PaginationParams = Depends(),
    status_filter: AnnouncementStatus | None = Query(default=None, alias="status"),
    type_filter: AnnouncementType | None = Query(default=None, alias="type"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementListResponse:
    """获取公告列表（管理员）"""
    service = AnnouncementService(db)
    items, total = await service.list_items(
        page=pagination.page,
        page_size=pagination.page_size,
        status=status_filter,
        type_=type_filter,
    )
    return AnnouncementListResponse(
        items=[AnnouncementResponse.model_validate(a) for a in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED
)
async def create_announcement(
    data: AnnouncementCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementResponse:
    """创建公告（管理员）"""
    service = AnnouncementService(db)
    announcement = await service.create(
        title=data.title,
        content=data.content,
        type_=AnnouncementType(data.type) if data.type else AnnouncementType.NOTICE,
        pinned=data.pinned,
    )
    return AnnouncementResponse.model_validate(announcement)


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementResponse:
    """获取公告详情（管理员）"""
    service = AnnouncementService(db)
    announcement = await service.get(announcement_id)
    return AnnouncementResponse.model_validate(announcement)


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: str,
    data: AnnouncementUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementResponse:
    """更新公告（管理员）"""
    service = AnnouncementService(db)
    announcement = await service.update(
        announcement_id,
        title=data.title,
        content=data.content,
        type_=AnnouncementType(data.type) if data.type else None,
        status=AnnouncementStatus(data.status) if data.status else None,
        pinned=data.pinned,
    )
    return AnnouncementResponse.model_validate(announcement)


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(
    announcement_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除公告（管理员，软删）"""
    service = AnnouncementService(db)
    await service.delete(announcement_id)


@router.put("/{announcement_id}/publish", response_model=AnnouncementResponse)
async def publish_announcement(
    announcement_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementResponse:
    """发布公告（管理员）"""
    service = AnnouncementService(db)
    announcement = await service.publish(announcement_id)
    return AnnouncementResponse.model_validate(announcement)
