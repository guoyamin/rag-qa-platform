from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import cast

import structlog
from sqlalchemy import Table, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RateLimitExceeded

logger = structlog.get_logger(__name__)


class LimitType(str, Enum):
    """限流类型"""

    GLOBAL = "global"  # 全局限流
    USER = "user"  # 单用户限流
    MODEL = "model"  # 单模型限流


class RateLimitService:
    """限流服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def check_limit(
        self,
        limit_type: LimitType,
        target_id: str | None = None,
        max_requests: int | None = None,
        window_seconds: int = 60,
    ) -> bool:
        """
        检查是否超过限流

        Args:
            limit_type: 限流类型
            target_id: 目标ID（用户ID/模型ID）
            max_requests: 最大请求数
            window_seconds: 时间窗口（秒）

        Returns:
            True 表示未超限，False 表示已超限

        Raises:
            RateLimitExceeded: 超过限流
        """
        # 获取限流配置
        if max_requests is None:
            config = await self._get_config(limit_type, target_id)
            if config:
                max_requests = config.get("max_requests", 100)
                window_seconds = config.get("window_seconds", 60)
            else:
                # 默认配置
                max_requests = self._get_default_limit(limit_type)
                window_seconds = 60

        # 查询当前窗口内的请求数
        window_start = datetime.now() - timedelta(seconds=window_seconds)

        query = select(func.count()).select_from(self._get_record_table())

        if limit_type == LimitType.GLOBAL:
            query = query.where(
                self._get_record_table().c.limit_type == LimitType.GLOBAL.value
            )
        elif limit_type == LimitType.USER and target_id:
            query = query.where(self._get_record_table().c.target_id == target_id)
            query = query.where(
                self._get_record_table().c.limit_type == LimitType.USER.value
            )
        elif limit_type == LimitType.MODEL and target_id:
            query = query.where(self._get_record_table().c.target_id == target_id)
            query = query.where(
                self._get_record_table().c.limit_type == LimitType.MODEL.value
            )

        query = query.where(self._get_record_table().c.created_at >= window_start)

        result = await self.db.execute(query)
        current_count = result.scalar() or 0

        if current_count >= max_requests:
            logger.warning(
                "rate_limit_exceeded",
                limit_type=limit_type.value,
                target_id=target_id,
                current=current_count,
                max=max_requests,
            )
            raise RateLimitExceeded(f"请求过于频繁，请等待 {window_seconds} 秒后再试")

        # 记录本次请求
        await self._record_request(limit_type, target_id)

        return True

    async def _get_config(
        self, limit_type: LimitType, target_id: str | None
    ) -> dict[str, int] | None:
        """获取限流配置"""
        # 从数据库或缓存获取配置
        # 简化实现，返回 None 使用默认配置
        return None

    def _get_default_limit(self, limit_type: LimitType) -> int:
        """获取默认限流配置"""
        defaults = {
            LimitType.GLOBAL: 100,  # 每分钟全局 100 次
            LimitType.USER: 10,  # 每分钟单用户 10 次
            LimitType.MODEL: 50,  # 每分钟单模型 50 次
        }
        return defaults.get(limit_type, 100)

    def _get_record_table(self) -> Table:
        """获取记录表（简化实现）"""
        from app.models.rate_limit import RateLimitRecord

        return cast(Table, RateLimitRecord.__table__)

    async def _record_request(
        self,
        limit_type: LimitType,
        target_id: str | None,
    ) -> None:
        """记录请求"""
        from app.models.rate_limit import RateLimitRecord

        record = RateLimitRecord(
            limit_type=limit_type.value,
            target_id=target_id,
            request_count=1,
            limited=False,
        )
        self.db.add(record)
        await self.db.commit()

    async def cleanup_old_records(self, days: int = 7) -> int:
        """清理过期限流记录"""
        cutoff = datetime.now() - timedelta(days=days)
        table = self._get_record_table()
        query = table.delete().where(table.c.created_at < cutoff)
        result = await self.db.execute(query)
        await self.db.commit()

        deleted = int(result.rowcount or 0)
        logger.info("rate_limit_records_cleaned", deleted=deleted)
        return deleted
