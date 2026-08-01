"""
智能问答平台 - 用量统计 API 路由

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 版本: V1.0
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import AuthorizationError
from app.models.user import User, UserRole
from app.services.usage_stats_service import UsageStatsService

router = APIRouter(prefix="/stats", tags=["用量统计"])


class UsageStatsResponse(BaseModel):
    """用量统计响应"""

    total_tokens: int
    input_tokens: int
    output_tokens: int
    total_cost: float
    total_calls: int
    success_calls: int
    failed_calls: int


class RankingItem(BaseModel):
    """排行项"""

    model_id: str | None = None
    user_id: str | None = None
    total_tokens: int
    total_cost: float
    total_calls: int


class RankingResponse(BaseModel):
    """排行响应"""

    items: list[RankingItem]


def require_admin(user: User = Depends(get_current_user)) -> User:
    """要求管理员权限"""
    if user.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        raise AuthorizationError("需要管理员权限")
    return user


@router.get("/usage", response_model=UsageStatsResponse, summary="获取用量统计")
async def get_usage_stats(
    model_id: str | None = Query(default=None, description="模型ID筛选"),
    user_id: str | None = Query(default=None, description="用户ID筛选"),
    days: int = Query(default=7, ge=1, le=90, description="统计天数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> UsageStatsResponse:
    """
    获取用量统计

    需要管理员权限
    """
    service = UsageStatsService(db)

    start_date = datetime.now() - timedelta(days=days)
    end_date = datetime.now()

    stats = await service.get_usage_stats(
        model_id=model_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )

    return UsageStatsResponse(**stats)


@router.get("/models/ranking", response_model=RankingResponse, summary="获取模型排行")
async def get_model_ranking(
    days: int = Query(default=30, ge=1, le=90, description="统计天数"),
    limit: int = Query(default=10, ge=1, le=50, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> RankingResponse:
    """
    获取模型使用排行

    需要管理员权限
    """
    service = UsageStatsService(db)

    start_date = datetime.now() - timedelta(days=days)
    ranking = await service.get_model_ranking(
        start_date=start_date,
        limit=limit,
    )

    return RankingResponse(items=[RankingItem.model_validate(item) for item in ranking])


@router.get("/users/ranking", response_model=RankingResponse, summary="获取用户排行")
async def get_user_ranking(
    days: int = Query(default=30, ge=1, le=90, description="统计天数"),
    limit: int = Query(default=10, ge=1, le=50, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> RankingResponse:
    """
    获取用户使用排行

    需要管理员权限
    """
    service = UsageStatsService(db)

    start_date = datetime.now() - timedelta(days=days)
    ranking = await service.get_user_ranking(
        start_date=start_date,
        limit=limit,
    )

    return RankingResponse(items=[RankingItem.model_validate(item) for item in ranking])
