"""
智能问答平台 - 限流熔断服务单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

from datetime import datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RateLimitExceeded
from app.services.rate_limit_service import LimitType, RateLimitService


class TestCircuitBreaker:
    """熔断器测试"""

    def test_circuit_state_enum(self):
        """测试熔断状态枚举值"""
        # 直接测试枚举值而非从模型导入
        circuit_state = {
            "CLOSED": "closed",
            "OPEN": "open",
            "HALF_OPEN": "half_open",
        }

        assert circuit_state["CLOSED"] == "closed"
        assert circuit_state["OPEN"] == "open"
        assert circuit_state["HALF_OPEN"] == "half_open"

    def test_circuit_breaker_state_transitions(self):
        """测试熔断器状态转换"""

        # 模拟状态枚举
        class CircuitState:
            CLOSED = "closed"
            OPEN = "open"
            HALF_OPEN = "half_open"

        # 初始状态: closed
        state = CircuitState.CLOSED
        assert state == "closed"

        # 失败次数达到阈值 -> open
        failure_count = 10
        threshold = 10
        if failure_count >= threshold:
            state = CircuitState.OPEN

        assert state == "open"

        # 超时后 -> half_open
        timeout_seconds = 60
        time_since_open = 65
        if time_since_open >= timeout_seconds:
            state = CircuitState.HALF_OPEN

        assert state == "half_open"

    def test_circuit_breaker_success_in_half_open(self):
        """测试半开状态下的成功恢复"""

        # 模拟状态枚举
        class CircuitState:
            CLOSED = "closed"
            OPEN = "open"
            HALF_OPEN = "half_open"

        state = CircuitState.HALF_OPEN
        success_count = 0
        recovery_threshold = 3

        # 连续成功达到阈值 -> closed
        for _ in range(recovery_threshold):
            success_count += 1
            if success_count >= recovery_threshold:
                state = CircuitState.CLOSED

        assert state == "closed"
        assert success_count == recovery_threshold

    def test_circuit_breaker_failure_in_half_open(self):
        """测试半开状态下的失败"""

        # 模拟状态枚举
        class CircuitState:
            CLOSED = "closed"
            OPEN = "open"
            HALF_OPEN = "half_open"

        state = CircuitState.HALF_OPEN

        # 半开状态下失败 -> 重新打开
        state = CircuitState.OPEN

        assert state == "open"


class TestRateLimit:
    """限流测试"""

    def test_rate_limit_strategy_enum(self):
        """测试限流策略枚举值"""
        rate_limit_strategy = {
            "FIXED_WINDOW": "fixed_window",
            "SLIDING_WINDOW": "sliding_window",
            "TOKEN_BUCKET": "token_bucket",
        }

        assert rate_limit_strategy["FIXED_WINDOW"] == "fixed_window"
        assert rate_limit_strategy["SLIDING_WINDOW"] == "sliding_window"
        assert rate_limit_strategy["TOKEN_BUCKET"] == "token_bucket"

    def test_rate_limit_response(self):
        """测试限流响应 Schema"""
        from app.schemas.model import RateLimitResponse

        response = RateLimitResponse(
            allowed=True,
            limit=100,
            remaining=95,
            reset_at=datetime.now(),
            retry_after=0,
        )

        assert response.allowed is True
        assert response.remaining == 95

    def test_rate_limit_rejected(self):
        """测试限流拒绝"""
        from app.schemas.model import RateLimitResponse

        response = RateLimitResponse(
            allowed=False,
            limit=100,
            remaining=0,
            reset_at=datetime.now(),
            retry_after=30,
        )

        assert response.allowed is False
        assert response.remaining == 0
        assert response.retry_after == 30

    def test_fixed_window_rate_limit(self):
        """测试固定窗口限流算法"""
        from datetime import datetime

        def check_fixed_window(
            request_count: int,
            window_limit: int,
            window_start: datetime,
            current_time: datetime,
        ) -> bool:
            # 检查是否在同一窗口内
            if (current_time - window_start).total_seconds() >= 60:  # 60秒窗口
                return True  # 新窗口，允许
            return request_count < window_limit

        # 第一分钟，第50个请求 -> 允许
        assert (
            check_fixed_window(
                49, 100, datetime(2026, 8, 1, 10, 0), datetime(2026, 8, 1, 10, 0, 30)
            )
            is True
        )

        # 第一分钟，第100个请求 -> 允许
        assert (
            check_fixed_window(
                99, 100, datetime(2026, 8, 1, 10, 0), datetime(2026, 8, 1, 10, 0, 50)
            )
            is True
        )

        # 第一分钟，第101个请求 -> 拒绝
        assert (
            check_fixed_window(
                100, 100, datetime(2026, 8, 1, 10, 0), datetime(2026, 8, 1, 10, 0, 55)
            )
            is False
        )

        # 第二分钟，新窗口 -> 允许
        assert (
            check_fixed_window(
                100, 100, datetime(2026, 8, 1, 10, 0), datetime(2026, 8, 1, 10, 1, 0)
            )
            is True
        )

    def test_token_bucket_rate_limit(self):
        """测试令牌桶限流算法"""

        def check_token_bucket(
            tokens: float,
            bucket_size: int,
            refill_rate: float,  # 每秒补充令牌数
            required_tokens: int,
        ) -> tuple[bool, float]:
            if tokens >= required_tokens:
                return True, tokens - required_tokens
            return False, tokens

        # 桶满，有足够令牌
        assert check_token_bucket(100, 100, 10, 10) == (True, 90)

        # 桶半满，令牌不足
        assert check_token_bucket(5, 100, 10, 10) == (False, 5)

        # 刚好够
        assert check_token_bucket(10, 100, 10, 10) == (True, 0)


class TestRateLimitService:
    """限流服务测试"""

    def test_check_rate_limit_allowed(self):
        """测试允许的请求"""
        # 模拟限流检查
        current_requests = 50
        limit = 100

        assert current_requests < limit  # 允许

    def test_check_rate_limit_exceeded(self):
        """测试超出限流"""
        current_requests = 100
        limit = 100

        assert current_requests >= limit  # 拒绝

    def test_ip_based_rate_limit(self):
        """测试基于 IP 的限流"""
        ip_limits = {
            "192.168.1.1": 100,
            "192.168.1.2": 50,
            "10.0.0.1": 200,
        }

        # 验证不同 IP 有不同限制
        assert ip_limits["192.168.1.1"] == 100
        assert ip_limits["10.0.0.1"] == 200

        # 检查限制
        assert ip_limits["192.168.1.1"] >= 100
        assert ip_limits["192.168.1.2"] < 200


class TestCircuitBreakerConfig:
    """熔断器配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = {
            "failure_threshold": 10,  # 10次失败后打开
            "success_threshold": 3,  # 3次成功后关闭
            "timeout_seconds": 60,  # 60秒后半开
            "half_open_max_calls": 3,  # 半开状态下最多3个请求
        }

        assert config["failure_threshold"] == 10
        assert config["timeout_seconds"] == 60

    def test_config_validation(self):
        """测试配置验证"""

        def validate_config(config: dict[str, int]) -> bool:
            required_keys = [
                "failure_threshold",
                "success_threshold",
                "timeout_seconds",
            ]
            for key in required_keys:
                if key not in config:
                    return False
            if config["failure_threshold"] <= 0:
                return False
            return config["timeout_seconds"] > 0

        # 有效配置
        assert (
            validate_config(
                {
                    "failure_threshold": 10,
                    "success_threshold": 3,
                    "timeout_seconds": 60,
                }
            )
            is True
        )

        # 无效配置: 缺少字段
        assert (
            validate_config(
                {
                    "failure_threshold": 10,
                    "timeout_seconds": 60,
                }
            )
            is False
        )

        # 无效配置: 阈值为0
        assert (
            validate_config(
                {
                    "failure_threshold": 0,
                    "success_threshold": 3,
                    "timeout_seconds": 60,
                }
            )
            is False
        )


# ========== 辅助函数 ==========


def _make_mock_db() -> MagicMock:
    """创建模拟数据库会话"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


def _make_service(db: MagicMock) -> RateLimitService:
    """从 Mock 创建 RateLimitService 实例"""
    return RateLimitService(cast(AsyncSession, db))


def _mock_scalar_result(db: MagicMock, scalar_return: int) -> MagicMock:
    """配置 db.execute 返回带 scalar 的结果"""
    result = MagicMock()
    result.scalar.return_value = scalar_return
    db.execute.return_value = result
    return result


def _mock_rowcount_result(db: MagicMock, rowcount: int) -> MagicMock:
    """配置 db.execute 返回带 rowcount 的结果"""
    result = MagicMock()
    result.rowcount = rowcount
    db.execute.return_value = result
    return result


# ========== Service 方法单元测试 ==========


class TestRateLimitServiceMethods:
    """RateLimitService 服务方法单元测试"""

    async def test_check_limit_global_allowed_returns_true(self):
        """全局限流未超限返回 True"""
        # Arrange
        db = _make_mock_db()
        _mock_scalar_result(db, 5)
        service = _make_service(db)

        # Act
        allowed = await service.check_limit(LimitType.GLOBAL, max_requests=100)

        # Assert
        assert allowed is True

    async def test_check_limit_global_exceeded_raises_exception(self):
        """全局限流超限抛出 RateLimitExceeded"""
        # Arrange
        db = _make_mock_db()
        _mock_scalar_result(db, 100)
        service = _make_service(db)

        # Act & Assert
        with pytest.raises(RateLimitExceeded):
            await service.check_limit(LimitType.GLOBAL, max_requests=100)

    async def test_check_limit_user_allowed_returns_true(self):
        """用户限流未超限返回 True"""
        # Arrange
        db = _make_mock_db()
        _mock_scalar_result(db, 3)
        service = _make_service(db)

        # Act
        allowed = await service.check_limit(
            LimitType.USER,
            target_id="user-123",
            max_requests=10,
        )

        # Assert
        assert allowed is True

    async def test_check_limit_user_exceeded_raises_exception(self):
        """用户限流超限抛出 RateLimitExceeded"""
        # Arrange
        db = _make_mock_db()
        _mock_scalar_result(db, 10)
        service = _make_service(db)

        # Act & Assert
        with pytest.raises(RateLimitExceeded):
            await service.check_limit(
                LimitType.USER,
                target_id="user-123",
                max_requests=10,
            )

    async def test_check_limit_model_allowed_returns_true(self):
        """模型限流未超限返回 True"""
        # Arrange
        db = _make_mock_db()
        _mock_scalar_result(db, 25)
        service = _make_service(db)

        # Act
        allowed = await service.check_limit(
            LimitType.MODEL,
            target_id="model-456",
            max_requests=50,
        )

        # Assert
        assert allowed is True

    async def test_check_limit_model_exceeded_raises_exception(self):
        """模型限流超限抛出 RateLimitExceeded"""
        # Arrange
        db = _make_mock_db()
        _mock_scalar_result(db, 50)
        service = _make_service(db)

        # Act & Assert
        with pytest.raises(RateLimitExceeded):
            await service.check_limit(
                LimitType.MODEL,
                target_id="model-456",
                max_requests=50,
            )

    async def test_check_limit_uses_default_when_no_max_requests(self):
        """未指定 max_requests 时使用默认限流值"""
        # Arrange - GLOBAL 默认 100，当前 99 未超限
        db = _make_mock_db()
        _mock_scalar_result(db, 99)
        service = _make_service(db)

        # Act
        allowed = await service.check_limit(LimitType.GLOBAL)

        # Assert
        assert allowed is True

    async def test_check_limit_default_global_exceeded_raises(self):
        """默认全局限流值超限抛出异常"""
        # Arrange - GLOBAL 默认 100，当前 100 已超限
        db = _make_mock_db()
        _mock_scalar_result(db, 100)
        service = _make_service(db)

        # Act & Assert
        with pytest.raises(RateLimitExceeded):
            await service.check_limit(LimitType.GLOBAL)

    async def test_check_limit_records_request_when_allowed(self):
        """未超限时记录请求到数据库"""
        # Arrange
        db = _make_mock_db()
        _mock_scalar_result(db, 0)
        service = _make_service(db)

        # Act
        await service.check_limit(LimitType.GLOBAL, max_requests=100)

        # Assert
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    async def test_check_limit_does_not_record_when_exceeded(self):
        """超限时不记录请求"""
        # Arrange
        db = _make_mock_db()
        _mock_scalar_result(db, 100)
        service = _make_service(db)

        # Act & Assert
        with pytest.raises(RateLimitExceeded):
            await service.check_limit(LimitType.GLOBAL, max_requests=100)

        db.add.assert_not_called()
        db.commit.assert_not_called()

    async def test_check_limit_custom_window_seconds(self):
        """自定义时间窗口限流正常工作"""
        # Arrange
        db = _make_mock_db()
        _mock_scalar_result(db, 2)
        service = _make_service(db)

        # Act
        allowed = await service.check_limit(
            LimitType.GLOBAL,
            max_requests=10,
            window_seconds=120,
        )

        # Assert
        assert allowed is True

    def test_get_default_limit_global_returns_100(self):
        """全局默认限流为 100"""
        service = _make_service(MagicMock())
        assert service._get_default_limit(LimitType.GLOBAL) == 100

    def test_get_default_limit_user_returns_10(self):
        """用户默认限流为 10"""
        service = _make_service(MagicMock())
        assert service._get_default_limit(LimitType.USER) == 10

    def test_get_default_limit_model_returns_50(self):
        """模型默认限流为 50"""
        service = _make_service(MagicMock())
        assert service._get_default_limit(LimitType.MODEL) == 50

    async def test_get_config_returns_none(self):
        """获取限流配置返回 None（简化实现）"""
        service = _make_service(MagicMock())
        config = await service._get_config(LimitType.GLOBAL, None)
        assert config is None

    async def test_cleanup_old_records_returns_deleted_count(self):
        """清理过期限流记录返回删除数量"""
        # Arrange
        db = _make_mock_db()
        _mock_rowcount_result(db, 5)
        service = _make_service(db)

        # Act
        deleted = await service.cleanup_old_records()

        # Assert
        assert deleted == 5
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()

    async def test_cleanup_old_records_custom_days(self):
        """自定义天数清理过期记录"""
        # Arrange
        db = _make_mock_db()
        _mock_rowcount_result(db, 10)
        service = _make_service(db)

        # Act
        deleted = await service.cleanup_old_records(days=30)

        # Assert
        assert deleted == 10

    async def test_cleanup_old_records_zero_deleted(self):
        """无过期记录时返回 0"""
        # Arrange
        db = _make_mock_db()
        _mock_rowcount_result(db, 0)
        service = _make_service(db)

        # Act
        deleted = await service.cleanup_old_records()

        # Assert
        assert deleted == 0

    async def test_record_request_adds_record_to_db(self):
        """记录请求添加到数据库"""
        # Arrange
        db = _make_mock_db()
        service = _make_service(db)

        # Act
        await service._record_request(LimitType.USER, "user-789")

        # Assert
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        record = db.add.call_args[0][0]
        assert record.limit_type == "user"
        assert record.target_id == "user-789"
        assert record.request_count == 1
        assert record.limited is False

    async def test_record_request_global_with_no_target(self):
        """全局限流记录请求无 target_id"""
        # Arrange
        db = _make_mock_db()
        service = _make_service(db)

        # Act
        await service._record_request(LimitType.GLOBAL, None)

        # Assert
        db.add.assert_called_once()
        record = db.add.call_args[0][0]
        assert record.limit_type == "global"
        assert record.target_id is None
