"""
智能问答平台 - 熔断器服务单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

from datetime import datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceUnavailableError
from app.models.rate_limit import CircuitBreakerState
from app.services.circuit_breaker_service import (
    CircuitBreakerService,
    CircuitState,
)

# ========== 辅助函数 ==========


def _make_mock_db() -> MagicMock:
    """创建模拟数据库会话"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


def _make_state(
    model_id: str = "model-1",
    state: str = CircuitState.CLOSED.value,
    failure_count: int = 0,
    success_count: int = 0,
    last_failure_at: datetime | None = None,
    opened_at: datetime | None = None,
    closed_at: datetime | None = None,
) -> CircuitBreakerState:
    """创建熔断器状态记录实例"""
    return CircuitBreakerState(
        model_id=model_id,
        state=state,
        failure_count=failure_count,
        success_count=success_count,
        last_failure_at=last_failure_at,
        opened_at=opened_at,
        closed_at=closed_at,
    )


def _mock_state_query(db: MagicMock, state: CircuitBreakerState | None) -> MagicMock:
    """配置 db.execute 返回带 scalar_one_or_none 的结果"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = state
    db.execute.return_value = result
    return result


def _mock_states_list(db: MagicMock, states: list) -> MagicMock:
    """配置 db.execute 返回带 scalars().all() 的结果"""
    result = MagicMock()
    result.scalars.return_value.all.return_value = states
    db.execute.return_value = result
    return result


def _make_service(db: MagicMock) -> CircuitBreakerService:
    """从 Mock 创建 CircuitBreakerService 实例"""
    return CircuitBreakerService(cast(AsyncSession, db))


# ========== 配置常量测试 ==========


class TestCircuitBreakerConfig:
    """熔断器配置常量测试"""

    def test_config_default_thresholds_and_durations(self):
        """默认阈值与持续时间配置正确"""
        assert CircuitBreakerService.FAILURE_THRESHOLD == 5
        assert CircuitBreakerService.SUCCESS_THRESHOLD == 3
        assert CircuitBreakerService.OPEN_DURATION == 30
        assert CircuitBreakerService.HALF_OPEN_RETRY == 30


# ========== get_state 方法测试 ==========


class TestGetState:
    """get_state 方法测试"""

    async def test_get_state_no_record_returns_closed(self):
        """无状态记录时返回 CLOSED"""
        # Arrange
        db = _make_mock_db()
        _mock_state_query(db, None)
        service = _make_service(db)

        # Act
        state = await service.get_state("model-1")

        # Assert
        assert state == CircuitState.CLOSED

    async def test_get_state_closed_record_returns_closed(self):
        """状态记录为 closed 时返回 CLOSED"""
        # Arrange
        db = _make_mock_db()
        _mock_state_query(db, _make_state(state="closed"))
        service = _make_service(db)

        # Act
        state = await service.get_state("model-1")

        # Assert
        assert state == CircuitState.CLOSED

    async def test_get_state_half_open_record_returns_half_open(self):
        """状态记录为 half_open 时返回 HALF_OPEN"""
        # Arrange
        db = _make_mock_db()
        _mock_state_query(db, _make_state(state="half_open"))
        service = _make_service(db)

        # Act
        state = await service.get_state("model-1")

        # Assert
        assert state == CircuitState.HALF_OPEN

    async def test_get_state_open_recent_returns_open(self):
        """打开时间未超时返回 OPEN（不转换）"""
        # Arrange
        db = _make_mock_db()
        _mock_state_query(db, _make_state(state="open", opened_at=datetime.now()))
        service = _make_service(db)

        # Act
        state = await service.get_state("model-1")

        # Assert
        assert state == CircuitState.OPEN

    async def test_get_state_open_no_opened_at_returns_open(self):
        """打开状态但 opened_at 为空时返回 OPEN（不转换）"""
        # Arrange
        db = _make_mock_db()
        _mock_state_query(db, _make_state(state="open", opened_at=None))
        service = _make_service(db)

        # Act
        state = await service.get_state("model-1")

        # Assert
        assert state == CircuitState.OPEN

    async def test_get_state_open_expired_transitions_to_half_open(self):
        """打开超时后转换为 HALF_OPEN"""
        # Arrange
        db = _make_mock_db()
        expired = datetime.now() - timedelta(seconds=31)
        _mock_state_query(db, _make_state(state="open", opened_at=expired))
        service = _make_service(db)

        # Act
        state = await service.get_state("model-1")

        # Assert
        assert state == CircuitState.HALF_OPEN

    async def test_get_state_open_at_threshold_transitions_to_half_open(self):
        """打开时间刚好达到阈值时转换为 HALF_OPEN（边界）"""
        # Arrange
        db = _make_mock_db()
        at_threshold = datetime.now() - timedelta(
            seconds=CircuitBreakerService.OPEN_DURATION
        )
        _mock_state_query(db, _make_state(state="open", opened_at=at_threshold))
        service = _make_service(db)

        # Act
        state = await service.get_state("model-1")

        # Assert
        assert state == CircuitState.HALF_OPEN


# ========== record_success 方法测试 ==========


class TestRecordSuccess:
    """record_success 方法测试"""

    async def test_record_success_no_record_returns_closed(self):
        """无状态记录时返回 CLOSED 且不提交"""
        # Arrange
        db = _make_mock_db()
        _mock_state_query(db, None)
        service = _make_service(db)

        # Act
        state = await service.record_success("model-1")

        # Assert
        assert state == CircuitState.CLOSED
        db.commit.assert_not_awaited()

    async def test_record_success_closed_resets_counts(self):
        """CLOSED 状态成功时重置计数并返回 CLOSED"""
        # Arrange
        record = _make_state(state="closed", failure_count=3, success_count=2)
        db = _make_mock_db()
        _mock_state_query(db, record)
        service = _make_service(db)

        # Act
        state = await service.record_success("model-1")

        # Assert
        assert state == CircuitState.CLOSED
        assert record.failure_count == 0
        assert record.success_count == 0
        db.commit.assert_awaited_once()

    async def test_record_success_half_open_below_threshold_returns_half_open(self):
        """HALF_OPEN 成功未达阈值返回 HALF_OPEN"""
        # Arrange
        record = _make_state(state="half_open", success_count=0)
        db = _make_mock_db()
        _mock_state_query(db, record)
        service = _make_service(db)

        # Act
        state = await service.record_success("model-1")

        # Assert
        assert state == CircuitState.HALF_OPEN
        assert record.success_count == 1
        assert record.failure_count == 0

    async def test_record_success_half_open_at_threshold_transitions_to_closed(self):
        """HALF_OPEN 成功达到阈值转换为 CLOSED"""
        # Arrange
        record = _make_state(
            state="half_open",
            success_count=CircuitBreakerService.SUCCESS_THRESHOLD - 1,
        )
        db = _make_mock_db()
        _mock_state_query(db, record)
        service = _make_service(db)

        # Act
        state = await service.record_success("model-1")

        # Assert
        assert state == CircuitState.CLOSED
        assert record.state == CircuitState.CLOSED.value

    async def test_record_success_open_state_stays_open(self):
        """OPEN 状态成功时重置计数但保持 OPEN（边界）"""
        # Arrange
        record = _make_state(state="open", failure_count=2)
        db = _make_mock_db()
        _mock_state_query(db, record)
        service = _make_service(db)

        # Act
        state = await service.record_success("model-1")

        # Assert
        assert state == CircuitState.OPEN
        assert record.failure_count == 0


# ========== record_failure 方法测试 ==========


class TestRecordFailure:
    """record_failure 方法测试"""

    async def test_record_failure_no_record_creates_record_returns_closed(self):
        """无状态记录时创建记录并返回 CLOSED"""
        # Arrange
        db = _make_mock_db()
        _mock_state_query(db, None)
        service = _make_service(db)

        # Act
        state = await service.record_failure("model-1")

        # Assert
        assert state == CircuitState.CLOSED
        db.add.assert_called_once()
        created = db.add.call_args[0][0]
        assert created.model_id == "model-1"

    async def test_record_failure_closed_below_threshold_returns_closed(self):
        """CLOSED 失败未达阈值返回 CLOSED"""
        # Arrange
        record = _make_state(state="closed", failure_count=2)
        db = _make_mock_db()
        _mock_state_query(db, record)
        service = _make_service(db)

        # Act
        state = await service.record_failure("model-1")

        # Assert
        assert state == CircuitState.CLOSED
        assert record.failure_count == 3
        db.add.assert_not_called()

    async def test_record_failure_closed_at_threshold_transitions_to_open(self):
        """CLOSED 失败达到阈值转换为 OPEN"""
        # Arrange
        record = _make_state(
            state="closed",
            failure_count=CircuitBreakerService.FAILURE_THRESHOLD - 1,
        )
        db = _make_mock_db()
        _mock_state_query(db, record)
        service = _make_service(db)

        # Act
        state = await service.record_failure("model-1")

        # Assert
        assert state == CircuitState.OPEN
        assert record.state == CircuitState.OPEN.value
        assert record.opened_at is not None

    async def test_record_failure_half_open_transitions_to_open(self):
        """HALF_OPEN 失败转换为 OPEN"""
        # Arrange
        record = _make_state(state="half_open", success_count=2)
        db = _make_mock_db()
        _mock_state_query(db, record)
        service = _make_service(db)

        # Act
        state = await service.record_failure("model-1")

        # Assert
        assert state == CircuitState.OPEN
        assert record.state == CircuitState.OPEN.value

    async def test_record_failure_open_stays_open(self):
        """OPEN 状态失败保持 OPEN（边界）"""
        # Arrange
        record = _make_state(
            state="open",
            failure_count=CircuitBreakerService.FAILURE_THRESHOLD - 1,
            opened_at=datetime.now(),
        )
        db = _make_mock_db()
        _mock_state_query(db, record)
        service = _make_service(db)

        # Act
        state = await service.record_failure("model-1")

        # Assert
        assert state == CircuitState.OPEN


# ========== check_availability 方法测试 ==========


class TestCheckAvailability:
    """check_availability 方法测试"""

    async def test_check_availability_open_returns_false(self):
        """OPEN 状态返回不可用"""
        db = _make_mock_db()
        _mock_state_query(db, _make_state(state="open", opened_at=datetime.now()))
        service = _make_service(db)
        assert await service.check_availability("model-1") is False

    async def test_check_availability_closed_returns_true(self):
        """CLOSED 状态返回可用"""
        db = _make_mock_db()
        _mock_state_query(db, _make_state(state="closed"))
        service = _make_service(db)
        assert await service.check_availability("model-1") is True

    async def test_check_availability_half_open_returns_true(self):
        """HALF_OPEN 状态返回可用（试探性调用）"""
        db = _make_mock_db()
        _mock_state_query(db, _make_state(state="half_open"))
        service = _make_service(db)
        assert await service.check_availability("model-1") is True

    async def test_check_availability_no_record_returns_true(self):
        """无状态记录返回可用"""
        db = _make_mock_db()
        _mock_state_query(db, None)
        service = _make_service(db)
        assert await service.check_availability("model-1") is True


# ========== get_or_raise 方法测试 ==========


class TestGetOrRaise:
    """get_or_raise 方法测试"""

    async def test_get_or_raise_open_raises_service_unavailable(self):
        """OPEN 状态抛出 ServiceUnavailableError"""
        db = _make_mock_db()
        _mock_state_query(db, _make_state(state="open", opened_at=datetime.now()))
        service = _make_service(db)

        with pytest.raises(ServiceUnavailableError) as exc:
            await service.get_or_raise("model-1")
        assert "model-1" in str(exc.value)

    async def test_get_or_raise_closed_does_not_raise(self):
        """CLOSED 状态不抛异常"""
        db = _make_mock_db()
        _mock_state_query(db, _make_state(state="closed"))
        service = _make_service(db)
        await service.get_or_raise("model-1")  # 无异常即通过

    async def test_get_or_raise_half_open_does_not_raise(self):
        """HALF_OPEN 状态不抛异常"""
        db = _make_mock_db()
        _mock_state_query(db, _make_state(state="half_open"))
        service = _make_service(db)
        await service.get_or_raise("model-1")


# ========== reset 方法测试 ==========


class TestReset:
    """reset 方法测试"""

    async def test_reset_returns_closed(self):
        """重置后返回 CLOSED"""
        db = _make_mock_db()
        _mock_state_query(db, _make_state(state="open", opened_at=datetime.now()))
        service = _make_service(db)

        state = await service.reset("model-1")

        assert state == CircuitState.CLOSED

    async def test_reset_transitions_record_to_closed(self):
        """重置将状态记录置为 CLOSED 并清零计数"""
        record = _make_state(state="open", failure_count=5, opened_at=datetime.now())
        db = _make_mock_db()
        _mock_state_query(db, record)
        service = _make_service(db)

        await service.reset("model-1")

        assert record.state == CircuitState.CLOSED.value
        assert record.failure_count == 0
        assert record.success_count == 0
        assert record.opened_at is None


# ========== get_all_states 方法测试 ==========


class TestGetAllStates:
    """get_all_states 方法测试"""

    async def test_get_all_states_returns_non_closed_states(self):
        """返回所有非 CLOSED 状态记录"""
        db = _make_mock_db()
        now = datetime.now()
        states = [
            _make_state(model_id="m1", state="open", failure_count=5, opened_at=now),
            _make_state(model_id="m2", state="half_open", success_count=1),
        ]
        _mock_states_list(db, states)
        service = _make_service(db)

        result = await service.get_all_states()

        assert len(result) == 2
        assert result[0]["model_id"] == "m1"
        assert result[0]["state"] == "open"
        assert result[0]["failure_count"] == 5
        assert result[0]["opened_at"] == now.isoformat()
        assert result[1]["model_id"] == "m2"
        assert result[1]["state"] == "half_open"
        assert result[1]["success_count"] == 1

    async def test_get_all_states_empty_returns_empty_list(self):
        """无状态记录时返回空列表"""
        db = _make_mock_db()
        _mock_states_list(db, [])
        service = _make_service(db)

        result = await service.get_all_states()

        assert result == []

    async def test_get_all_states_none_dates_serialized_as_none(self):
        """时间为空时序列化为 None"""
        db = _make_mock_db()
        _mock_states_list(db, [_make_state(model_id="m1", state="open")])
        service = _make_service(db)

        result = await service.get_all_states()

        assert result[0]["last_failure_at"] is None
        assert result[0]["opened_at"] is None
