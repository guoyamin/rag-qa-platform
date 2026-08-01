from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceUnavailableError

if TYPE_CHECKING:
    from app.models.rate_limit import CircuitBreakerState

logger = structlog.get_logger(__name__)


class CircuitState(str, Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 关闭：正常调用
    OPEN = "open"  # 打开：拒绝调用
    HALF_OPEN = "half_open"  # 半开：尝试恢复


class CircuitBreakerService:
    """
    熔断器服务

    实现熔断器模式，保护服务不被连续故障拖垮。

    状态转换:
    - 关闭(Closed) → 打开(Open): 连续失败达到阈值
    - 打开(Open) → 半开(Half-Open): 熔断超时后
    - 半开(Half-Open) → 关闭(Closed): 连续成功达到阈值
    - 半开(Half-Open) → 打开(Open): 尝试仍然失败
    """

    # 熔断配置
    FAILURE_THRESHOLD = 5  # 连续失败次数阈值
    SUCCESS_THRESHOLD = 3  # 连续成功次数阈值（恢复）
    OPEN_DURATION = 30  # 熔断持续时间（秒）
    HALF_OPEN_RETRY = 30  # 半开状态下重试间隔（秒）

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_state(self, model_id: str) -> CircuitState:
        """获取熔断器状态"""
        state = await self._get_state_record(model_id)

        if state is None:
            return CircuitState.CLOSED

        # 检查是否需要从 OPEN 转换到 HALF_OPEN
        if state.state == CircuitState.OPEN.value:
            opened_at = state.opened_at
            if opened_at:
                elapsed = (datetime.now() - opened_at).total_seconds()
                if elapsed >= self.OPEN_DURATION:
                    await self._transition_to_half_open(model_id)
                    return CircuitState.HALF_OPEN

        return CircuitState(state.state)

    async def record_success(self, model_id: str) -> CircuitState:
        """记录成功调用"""
        state = await self._get_state_record(model_id)

        if state is None:
            return CircuitState.CLOSED

        if state.state == CircuitState.HALF_OPEN.value:
            # 半开状态下成功，连续成功计数 +1
            state.success_count += 1
            state.failure_count = 0

            if state.success_count >= self.SUCCESS_THRESHOLD:
                # 恢复关闭状态
                await self._transition_to_closed(model_id)
                logger.info("circuit_breaker_recovered", model_id=model_id)
        else:
            # 正常状态，重置计数
            state.failure_count = 0
            state.success_count = 0

        await self.db.commit()
        return CircuitState(state.state)

    async def record_failure(self, model_id: str) -> CircuitState:
        """记录失败调用"""
        state = await self._get_state_record(model_id)

        if state is None:
            # 首次失败，创建记录
            state = await self._create_state_record(model_id)

        if state.state == CircuitState.HALF_OPEN.value:
            # 半开状态下失败，回到打开状态
            await self._transition_to_open(model_id)
            logger.warning("circuit_breaker_half_open_failed", model_id=model_id)
        else:
            # 正常状态下的失败计数
            state.failure_count += 1
            state.success_count = 0
            state.last_failure_at = datetime.now()

            if state.failure_count >= self.FAILURE_THRESHOLD:
                await self._transition_to_open(model_id)
                logger.warning(
                    "circuit_breaker_opened",
                    model_id=model_id,
                    failures=state.failure_count,
                )

        await self.db.commit()
        return await self.get_state(model_id)

    async def check_availability(self, model_id: str) -> bool:
        """
        检查模型是否可用

        Returns:
            True 表示可用，False 表示不可用（熔断中）
        """
        state = await self.get_state(model_id)
        return state != CircuitState.OPEN

    async def get_or_raise(self, model_id: str) -> None:
        """
        检查可用性，不可用则抛出异常

        Raises:
            ServiceUnavailableError: 模型不可用（熔断中）
        """
        if not await self.check_availability(model_id):
            raise ServiceUnavailableError(
                f"模型 {model_id} 当前不可用（熔断中），请稍后重试"
            )

    async def reset(self, model_id: str) -> CircuitState:
        """手动重置熔断器"""
        await self._transition_to_closed(model_id)
        logger.info("circuit_breaker_reset", model_id=model_id)
        return CircuitState.CLOSED

    async def get_all_states(self) -> list[dict[str, Any]]:
        """获取所有熔断器状态"""
        from app.models.rate_limit import CircuitBreakerState

        result = await self.db.execute(
            select(CircuitBreakerState).where(
                CircuitBreakerState.state != CircuitState.CLOSED.value
            )
        )
        states = result.scalars().all()

        return [
            {
                "model_id": s.model_id,
                "state": s.state,
                "failure_count": s.failure_count,
                "success_count": s.success_count,
                "last_failure_at": (
                    s.last_failure_at.isoformat() if s.last_failure_at else None
                ),
                "opened_at": s.opened_at.isoformat() if s.opened_at else None,
            }
            for s in states
        ]

    async def _get_state_record(self, model_id: str) -> CircuitBreakerState | None:
        """获取熔断器状态记录"""
        from app.models.rate_limit import CircuitBreakerState

        result = await self.db.execute(
            select(CircuitBreakerState).where(CircuitBreakerState.model_id == model_id)
        )
        return result.scalar_one_or_none()

    async def _create_state_record(self, model_id: str) -> CircuitBreakerState:
        """创建熔断器状态记录"""
        from app.models.rate_limit import CircuitBreakerState

        state = CircuitBreakerState(
            model_id=model_id,
            state=CircuitState.CLOSED.value,
            failure_count=1,
            success_count=0,
        )
        self.db.add(state)
        await self.db.commit()
        await self.db.refresh(state)
        return state

    async def _transition_to_open(self, model_id: str) -> None:
        """转换到打开状态"""
        state = await self._get_state_record(model_id)
        if state:
            state.state = CircuitState.OPEN.value
            state.opened_at = datetime.now()
            state.failure_count = 0

    async def _transition_to_half_open(self, model_id: str) -> None:
        """转换到半开状态"""
        state = await self._get_state_record(model_id)
        if state:
            state.state = CircuitState.HALF_OPEN.value
            state.closed_at = None

    async def _transition_to_closed(self, model_id: str) -> None:
        """转换到关闭状态"""
        state = await self._get_state_record(model_id)
        if state:
            state.state = CircuitState.CLOSED.value
            state.failure_count = 0
            state.success_count = 0
            state.opened_at = None
            state.closed_at = datetime.now()
