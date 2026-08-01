from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_log import ModelUsageDaily, ModelUsageLog

logger = structlog.get_logger(__name__)


# 模型单价配置（可从配置读取）
MODEL_PRICING = {
    "gpt-4o": {
        "input": Decimal("0.000005"),
        "output": Decimal("0.000015"),
    },  # $5/1M in, $15/1M out
    "gpt-4o-mini": {"input": Decimal("0.00000015"), "output": Decimal("0.0000006")},
    "gpt-3.5-turbo": {"input": Decimal("0.0000005"), "output": Decimal("0.0000015")},
    "qwen-plus": {"input": Decimal("0.000004"), "output": Decimal("0.000012")},
    "text-embedding-3-small": {
        "input": Decimal("0.00000002"),
        "output": Decimal("0"),
    },  # per token
    "text-embedding-3-large": {"input": Decimal("0.00000013"), "output": Decimal("0")},
}

DEFAULT_PRICING = {"input": Decimal("0.000001"), "output": Decimal("0.000003")}


class UsageStatsService:
    """用量统计服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def calculate_cost(
        self, model_name: str, input_tokens: int, output_tokens: int
    ) -> Decimal:
        """计算预估费用"""
        pricing = MODEL_PRICING.get(model_name, DEFAULT_PRICING)
        input_cost = Decimal(input_tokens) * pricing["input"]
        output_cost = Decimal(output_tokens) * pricing["output"]
        return input_cost + output_cost

    async def record_usage(
        self,
        model_id: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        latency_ms: int | None = None,
        success: bool = True,
        error_message: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        scene: str | None = None,
    ) -> ModelUsageLog:
        """记录一次用量"""
        cost = self.calculate_cost(model_name, input_tokens, output_tokens)

        log = ModelUsageLog(
            model_id=model_id,
            user_id=user_id,
            session_id=session_id,
            scene=scene,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message,
            cost=cost,
        )

        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)

        logger.info(
            "usage_recorded",
            model_id=model_id,
            tokens=total_tokens,
            cost=float(cost),
        )

        return log

    async def get_usage_stats(
        self,
        model_id: str | None = None,
        user_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """获取用量统计"""
        query = select(
            func.sum(ModelUsageLog.total_tokens).label("total_tokens"),
            func.sum(ModelUsageLog.input_tokens).label("input_tokens"),
            func.sum(ModelUsageLog.output_tokens).label("output_tokens"),
            func.sum(ModelUsageLog.cost).label("total_cost"),
            func.count(ModelUsageLog.id).label("total_calls"),
            func.sum(func.cast(ModelUsageLog.success, Integer)).label("success_calls"),
        ).select_from(ModelUsageLog)

        if model_id:
            query = query.where(ModelUsageLog.model_id == model_id)
        if user_id:
            query = query.where(ModelUsageLog.user_id == user_id)
        if start_date:
            query = query.where(ModelUsageLog.created_at >= start_date)
        if end_date:
            query = query.where(ModelUsageLog.created_at <= end_date)

        result = await self.db.execute(query)
        row = result.one()

        return {
            "total_tokens": row.total_tokens or 0,
            "input_tokens": row.input_tokens or 0,
            "output_tokens": row.output_tokens or 0,
            "total_cost": float(row.total_cost or Decimal("0")),
            "total_calls": row.total_calls or 0,
            "success_calls": row.success_calls or 0,
            "failed_calls": (row.total_calls or 0) - (row.success_calls or 0),
        }

    async def get_model_ranking(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """获取模型使用排行"""
        query = (
            select(
                ModelUsageLog.model_id,
                func.sum(ModelUsageLog.total_tokens).label("total_tokens"),
                func.sum(ModelUsageLog.cost).label("total_cost"),
                func.count(ModelUsageLog.id).label("total_calls"),
            )
            .select_from(ModelUsageLog)
            .group_by(ModelUsageLog.model_id)
            .order_by(func.sum(ModelUsageLog.cost).desc())
            .limit(limit)
        )

        if start_date:
            query = query.where(ModelUsageLog.created_at >= start_date)
        if end_date:
            query = query.where(ModelUsageLog.created_at <= end_date)

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "model_id": row.model_id,
                "total_tokens": row.total_tokens or 0,
                "total_cost": float(row.total_cost or Decimal("0")),
                "total_calls": row.total_calls or 0,
            }
            for row in rows
        ]

    async def get_user_ranking(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """获取用户使用排行"""
        query = (
            select(
                ModelUsageLog.user_id,
                func.sum(ModelUsageLog.total_tokens).label("total_tokens"),
                func.sum(ModelUsageLog.cost).label("total_cost"),
                func.count(ModelUsageLog.id).label("total_calls"),
            )
            .select_from(ModelUsageLog)
            .group_by(ModelUsageLog.user_id)
            .order_by(func.sum(ModelUsageLog.cost).desc())
            .limit(limit)
        )

        if start_date:
            query = query.where(ModelUsageLog.created_at >= start_date)
        if end_date:
            query = query.where(ModelUsageLog.created_at <= end_date)

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "user_id": row.user_id,
                "total_tokens": row.total_tokens or 0,
                "total_cost": float(row.total_cost or Decimal("0")),
                "total_calls": row.total_calls or 0,
            }
            for row in rows
        ]

    async def aggregate_daily_stats(self, date: datetime | None = None) -> None:
        """聚合每日统计数据（定时任务调用）"""
        target_date = date or datetime.now()
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # 按模型聚合
        query = (
            select(
                ModelUsageLog.model_id,
                func.count(ModelUsageLog.id).label("total_calls"),
                func.sum(func.cast(ModelUsageLog.success, Integer)).label(
                    "success_calls"
                ),
                (
                    func.count(ModelUsageLog.id)
                    - func.sum(func.cast(ModelUsageLog.success, Integer))
                ).label("failed_calls"),
                func.sum(ModelUsageLog.input_tokens).label("total_input_tokens"),
                func.sum(ModelUsageLog.output_tokens).label("total_output_tokens"),
                func.avg(ModelUsageLog.latency_ms).label("avg_latency_ms"),
                func.sum(ModelUsageLog.cost).label("estimated_cost"),
            )
            .where(ModelUsageLog.created_at >= start_of_day)
            .where(ModelUsageLog.created_at < end_of_day)
            .group_by(ModelUsageLog.model_id)
        )

        result = await self.db.execute(query)
        rows = result.all()

        for row in rows:
            total_calls = row.total_calls or 0
            success_calls = row.success_calls or 0
            success_rate = (
                Decimal(str(success_calls / total_calls * 100))
                if total_calls > 0
                else Decimal("0")
            )

            daily = ModelUsageDaily(
                model_id=row.model_id,
                date=start_of_day.date(),
                total_calls=total_calls,
                success_calls=success_calls,
                failed_calls=row.failed_calls or 0,
                total_input_tokens=row.total_input_tokens or 0,
                total_output_tokens=row.total_output_tokens or 0,
                avg_latency_ms=int(row.avg_latency_ms or 0),
                success_rate=success_rate,
                estimated_cost=row.estimated_cost or Decimal("0"),
            )

            self.db.add(daily)

        await self.db.commit()
        logger.info(
            "daily_stats_aggregated", date=start_of_day.date(), models=len(rows)
        )
