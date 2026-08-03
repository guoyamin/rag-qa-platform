"""
智能问答平台 - 公告 Schema
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.announcement import AnnouncementStatus, AnnouncementType


class AnnouncementCreate(BaseModel):
    """创建公告"""

    title: str = Field(..., min_length=1, max_length=200, description="公告标题")
    content: str = Field(..., min_length=1, description="公告正文")
    type: AnnouncementType = Field(
        default=AnnouncementType.NOTICE, description="公告类型"
    )
    pinned: bool = Field(default=False, description="是否置顶")


class AnnouncementUpdate(BaseModel):
    """更新公告"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)
    type: AnnouncementType | None = None
    status: AnnouncementStatus | None = None
    pinned: bool | None = None


class AnnouncementResponse(BaseModel):
    """公告响应"""

    model_config = {"from_attributes": True}

    id: str
    title: str
    content: str
    type: AnnouncementType
    status: AnnouncementStatus
    pinned: bool
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AnnouncementListResponse(BaseModel):
    """公告列表响应"""

    items: list[AnnouncementResponse]
    total: int
    page: int
    page_size: int
