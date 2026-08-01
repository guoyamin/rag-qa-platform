"""
智能问答平台 - 健康检查 API 路由

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 版本: V1.0
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import AuthorizationError
from app.models.user import User, UserRole
from app.services.health_check_service import HealthCheckService

router = APIRouter(prefix="/health", tags=["健康检查"])


class HealthStatusResponse(BaseModel):
    """健康状态响应"""

    model_id: str
    status: str
    latency_ms: int | None = None
    error_message: str | None = None
    checked_at: str | None = None


class HealthCheckSummary(BaseModel):
    """健康检查摘要"""

    total_models: int
    healthy_count: int
    degraded_count: int
    unhealthy_count: int
    unknown_count: int


def require_admin(user: User = Depends(get_current_user)) -> User:
    """要求管理员权限"""
    if user.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        raise AuthorizationError("需要管理员权限")
    return user


@router.get(
    "/models", response_model=list[HealthStatusResponse], summary="获取模型健康状态"
)
async def get_models_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[HealthStatusResponse]:
    """
    获取所有模型健康状态

    需要管理员权限
    """
    service = HealthCheckService(db)
    results = await service.check_all_models()

    return [
        HealthStatusResponse(
            model_id=r.model_id,
            status=r.status.value,
            latency_ms=r.latency_ms,
            error_message=r.error_message,
            checked_at=r.checked_at.isoformat() if r.checked_at else None,
        )
        for r in results
    ]


@router.get(
    "/models/{model_id}",
    response_model=HealthStatusResponse,
    summary="获取单个模型健康状态",
)
async def get_model_health(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HealthStatusResponse:
    """
    获取单个模型健康状态

    需要管理员权限
    """
    service = HealthCheckService(db)
    result = await service.quick_check(model_id)

    return HealthStatusResponse(
        model_id=result.model_id,
        status=result.status.value,
        latency_ms=result.latency_ms,
        error_message=result.error_message,
        checked_at=result.checked_at.isoformat() if result.checked_at else None,
    )


@router.get("/summary", response_model=HealthCheckSummary, summary="获取健康检查摘要")
async def get_health_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> HealthCheckSummary:
    """
    获取健康检查摘要统计

    需要管理员权限
    """
    service = HealthCheckService(db)
    results = await service.check_all_models()

    healthy = sum(1 for r in results if r.status.value == "healthy")
    degraded = sum(1 for r in results if r.status.value == "degraded")
    unhealthy = sum(1 for r in results if r.status.value == "unhealthy")
    unknown = sum(1 for r in results if r.status.value == "unknown")

    return HealthCheckSummary(
        total_models=len(results),
        healthy_count=healthy,
        degraded_count=degraded,
        unhealthy_count=unhealthy,
        unknown_count=unknown,
    )
