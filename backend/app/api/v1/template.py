"""
智能问答平台 - 模板管理 API 路由

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 版本: V1.0
"""

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import AuthorizationError
from app.models.preset_template import TemplateType
from app.models.user import User, UserRole
from app.services.template_service import TemplateService

router = APIRouter(prefix="/models/templates", tags=["模板管理"])


class TemplateCreate(BaseModel):
    """创建模板请求"""

    name: str
    template_type: str
    template: dict[str, Any]
    description: str | None = None
    is_default: bool = False
    tags: list[str] | None = None
    category: str | None = None


class TemplateUpdate(BaseModel):
    """更新模板请求"""

    name: str | None = None
    template: dict[str, Any] | None = None
    description: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    tags: list[str] | None = None
    category: str | None = None


class TemplateResponse(BaseModel):
    """模板响应"""

    id: str
    name: str
    template_type: str
    description: str | None
    template: dict[str, Any]
    is_default: bool
    is_active: bool
    tags: list[str]
    category: str | None
    version: str
    created_by: str | None
    created_at: str

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    """模板列表响应"""

    items: list[TemplateResponse]
    total: int
    page: int
    page_size: int


def require_admin(user: User = Depends(get_current_user)) -> User:
    """要求管理员权限"""
    if user.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        raise AuthorizationError("需要管理员权限")
    return user


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建模板",
)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> TemplateResponse:
    """创建预设模板"""
    service = TemplateService(db)
    template = await service.create(
        name=data.name,
        template=data.template,
        template_type=TemplateType(data.template_type),
        description=data.description,
        is_default=data.is_default,
        tags=data.tags,
        category=data.category,
        user_id=current_user.id,
    )

    return TemplateResponse(
        id=template.id,
        name=template.name,
        template_type=template.template_type.value,
        description=template.description,
        template=template.template,
        is_default=template.is_default,
        is_active=template.is_active,
        tags=template.tags,
        category=template.category,
        version=template.version,
        created_by=template.created_by,
        created_at=template.created_at.isoformat(),
    )


@router.get("", response_model=TemplateListResponse, summary="列出模板")
async def list_templates(
    template_type: str | None = None,
    category: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> TemplateListResponse:
    """列出所有模板"""
    service = TemplateService(db)

    template_type_enum = TemplateType(template_type) if template_type else None

    items, total = await service.list(
        template_type=template_type_enum,
        category=category,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )

    return TemplateListResponse(
        items=[
            TemplateResponse(
                id=t.id,
                name=t.name,
                template_type=t.template_type.value,
                description=t.description,
                template=t.template,
                is_default=t.is_default,
                is_active=t.is_active,
                tags=t.tags,
                category=t.category,
                version=t.version,
                created_by=t.created_by,
                created_at=t.created_at.isoformat(),
            )
            for t in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{template_id}", response_model=TemplateResponse, summary="获取模板详情")
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> TemplateResponse:
    """获取模板详情"""
    service = TemplateService(db)
    template = await service.get(template_id)

    return TemplateResponse(
        id=template.id,
        name=template.name,
        template_type=template.template_type.value,
        description=template.description,
        template=template.template,
        is_default=template.is_default,
        is_active=template.is_active,
        tags=template.tags,
        category=template.category,
        version=template.version,
        created_by=template.created_by,
        created_at=template.created_at.isoformat(),
    )


@router.put("/{template_id}", response_model=TemplateResponse, summary="更新模板")
async def update_template(
    template_id: str,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> TemplateResponse:
    """更新模板"""
    service = TemplateService(db)
    template = await service.update(
        template_id=template_id,
        name=data.name,
        template=data.template,
        description=data.description,
        is_default=data.is_default,
        is_active=data.is_active,
        tags=data.tags,
        category=data.category,
    )

    return TemplateResponse(
        id=template.id,
        name=template.name,
        template_type=template.template_type.value,
        description=template.description,
        template=template.template,
        is_default=template.is_default,
        is_active=template.is_active,
        tags=template.tags,
        category=template.category,
        version=template.version,
        created_by=template.created_by,
        created_at=template.created_at.isoformat(),
    )


@router.delete(
    "/{template_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除模板"
)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    """删除模板"""
    service = TemplateService(db)
    await service.delete(template_id)
