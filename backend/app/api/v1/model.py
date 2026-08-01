"""
智能问答平台 - 模型管理 API 路由

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 功能描述: API Key 和模型实例管理 API
- 版本: V1.0

修订记录:
- 2026-08-01 V1.0 初始版本（AI生成）
"""

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import AuthorizationError
from app.models.user import User, UserRole
from app.schemas.model import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyUpdate,
    ModelCompareRequest,
    ModelCompareResponse,
    ModelInstanceCreate,
    ModelInstanceListResponse,
    ModelInstanceResponse,
    ModelInstanceUpdate,
)
from app.services.api_key_service import ApiKeyService
from app.services.model_service import ModelService

router = APIRouter(prefix="/models", tags=["模型管理"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    """要求管理员权限"""
    if user.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        raise AuthorizationError("需要管理员权限")
    return user


# ========== API Key 管理 ==========


@router.post(
    "/keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建 API Key",
)
async def create_api_key(
    data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ApiKeyCreateResponse:
    """
    创建新的 API Key

    - Key 会加密存储到 Vault
    - 返回明文 Key（仅此次可见，请妥善保存）
    - 需要管理员权限
    """
    service = ApiKeyService(db)
    return await service.create(data, user_id=current_user.id)


@router.get("/keys", response_model=list[ApiKeyResponse], summary="列出 API Keys")
async def list_api_keys(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    provider: str | None = Query(default=None, description="提供商筛选"),
    usage: str | None = Query(default=None, description="用途筛选"),
    status_filter: str | None = Query(
        default=None, alias="status", description="状态筛选"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[ApiKeyResponse]:
    """列出所有 API Key 元信息（不含明文）"""
    service = ApiKeyService(db)
    items, _ = await service.list(
        page=page,
        page_size=page_size,
        provider=provider,
        usage=usage,
        status=status_filter,
    )
    return [ApiKeyResponse.model_validate(item) for item in items]


@router.get(
    "/keys/{key_id}", response_model=ApiKeyResponse, summary="获取 API Key 详情"
)
async def get_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ApiKeyResponse:
    """获取 API Key 详情（不含明文）"""
    service = ApiKeyService(db)
    item = await service.get(key_id)
    return ApiKeyResponse.model_validate(item)


@router.put("/keys/{key_id}", response_model=ApiKeyResponse, summary="更新 API Key")
async def update_api_key(
    key_id: str,
    data: ApiKeyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ApiKeyResponse:
    """
    更新 API Key

    - 可更新名称、状态、过期时间
    - 如提供新 Key，会重新加密存储
    """
    service = ApiKeyService(db)
    item = await service.update(key_id, data)
    return ApiKeyResponse.model_validate(item)


@router.delete(
    "/keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除 API Key",
)
async def delete_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    """删除 API Key（包括 Vault 中的加密数据）"""
    service = ApiKeyService(db)
    await service.delete(key_id)


@router.post(
    "/keys/{key_id}/rotate",
    response_model=ApiKeyCreateResponse,
    summary="轮换 API Key",
)
async def rotate_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ApiKeyCreateResponse:
    """
    轮换 API Key

    - 生成新的 Key
    - 旧 Key 失效
    - 返回新明文 Key（仅此次可见）
    """
    service = ApiKeyService(db)
    return await service.rotate_key(key_id)


@router.get("/vault/health", summary="Vault 健康检查")
async def check_vault_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    """检查 Vault 服务健康状态"""
    service = ApiKeyService(db)
    return await service.health_check()


# ========== 模型实例管理 ==========


@router.post(
    "",
    response_model=ModelInstanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建模型实例",
)
async def create_model_instance(
    data: ModelInstanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ModelInstanceResponse:
    """
    创建新的模型实例

    - 需要关联 API Key（用于调用模型 API）
    - 配置包括模型名称、温度、超时等参数
    """
    service = ModelService(db)
    instance = await service.create(data, user_id=current_user.id)
    return ModelInstanceResponse.model_validate(instance)


@router.get("", response_model=ModelInstanceListResponse, summary="列出模型实例")
async def list_model_instances(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    provider: str | None = Query(default=None, description="提供商筛选"),
    model_type: str | None = Query(default=None, description="模型类型筛选"),
    status_filter: str | None = Query(
        default=None, alias="status", description="状态筛选"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ModelInstanceListResponse:
    """列出所有模型实例"""
    service = ModelService(db)
    items, total = await service.list(
        page=page,
        page_size=page_size,
        provider=provider,
        model_type=model_type,
        status=status_filter,
    )
    return ModelInstanceListResponse(
        items=[ModelInstanceResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{model_id}", response_model=ModelInstanceResponse, summary="获取模型实例详情"
)
async def get_model_instance(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ModelInstanceResponse:
    """获取模型实例详情"""
    service = ModelService(db)
    item = await service.get(model_id)
    return ModelInstanceResponse.model_validate(item)


@router.put("/{model_id}", response_model=ModelInstanceResponse, summary="更新模型实例")
async def update_model_instance(
    model_id: str,
    data: ModelInstanceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ModelInstanceResponse:
    """
    更新模型实例配置

    - 可更新配置参数、API Key 关联
    - 更新后自动刷新缓存
    """
    service = ModelService(db)
    item = await service.update(model_id, data)
    return ModelInstanceResponse.model_validate(item)


@router.post(
    "/{model_id}/toggle", response_model=ModelInstanceResponse, summary="切换模型状态"
)
async def toggle_model_status(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ModelInstanceResponse:
    """
    启用/禁用模型

    - 禁用后该模型不会被调度使用
    """
    service = ModelService(db)
    item = await service.toggle_status(model_id)
    return ModelInstanceResponse.model_validate(item)


@router.delete(
    "/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除模型实例",
)
async def delete_model_instance(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    """删除模型实例"""
    service = ModelService(db)
    await service.delete(model_id)


@router.post("/compare", response_model=ModelCompareResponse, summary="模型对比")
async def compare_models(
    data: ModelCompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ModelCompareResponse:
    """
    对比多个模型的回答效果

    - 输入同一问题，返回各模型的回答
    - 包含响应时间、Token 消耗等指标
    """
    service = ModelService(db)
    return await service.compare_models(data, current_user.id)
