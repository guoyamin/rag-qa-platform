"""
智能问答平台 - 成本告警服务单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

from datetime import datetime
from decimal import Decimal, DivisionByZero
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.models.cost_alert import AlertLevel, AlertStatus, CostAlert
from app.services.cost_alert_service import CostAlertService


def _make_mock_db() -> MagicMock:
    """构造隔离 DB 的 mock AsyncSession。"""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.execute = AsyncMock()
    return db


def _make_alert(
    *,
    alert_id: str = "alert-1",
    alert_name: str = "test-alert",
    target_type: str = "global",
    target_id: str | None = None,
    threshold_type: str = "total",
    threshold_value: Decimal = Decimal("100"),
    level: str = AlertLevel.WARNING,
    status: str = AlertStatus.PENDING,
    current_value: Decimal = Decimal("0"),
    is_enabled: bool = True,
) -> MagicMock:
    """构造带默认属性的 mock CostAlert。"""
    alert = MagicMock()
    alert.id = alert_id
    alert.alert_name = alert_name
    alert.target_type = target_type
    alert.target_id = target_id
    alert.threshold_type = threshold_type
    alert.threshold_value = threshold_value
    alert.level = level
    alert.status = status
    alert.current_value = current_value
    alert.message = None
    alert.auto_resolve = False
    alert.is_enabled = is_enabled
    alert.triggered_at = datetime.now()
    alert.resolved_at = None
    alert.resolved_by = None
    return alert


def _make_list_result(alerts: list) -> MagicMock:
    """构造 list_alerts 的 db.execute 返回结果。"""
    result = MagicMock()
    result.scalars.return_value.all.return_value = alerts
    return result


def _make_cost_result(cost) -> MagicMock:
    """构造 _calculate_current_cost 的 db.execute 返回结果。"""
    result = MagicMock()
    result.scalar.return_value = cost
    return result


class TestCostAlertServiceCreateAlert:
    """CostAlertService.create_alert 方法测试"""

    async def test_create_alert_success_persists_and_returns_alert(self):
        """正常: 创建告警写入 DB 并返回带传入字段的对象"""
        # Arrange
        db = _make_mock_db()
        service = CostAlertService(db)
        # Act
        result = await service.create_alert(
            alert_name="daily-budget",
            target_type="model",
            threshold_type="daily",
            threshold_value=Decimal("50.00"),
            level=AlertLevel.ERROR,
            target_id="model-1",
            description="daily cap",
            auto_resolve=True,
        )
        # Assert
        db.add.assert_called_once()
        added = db.add.call_args.args[0]
        assert isinstance(added, CostAlert)
        assert added.alert_name == "daily-budget"
        assert added.target_type == "model"
        assert added.target_id == "model-1"
        assert added.threshold_type == "daily"
        assert added.threshold_value == Decimal("50.00")
        assert added.level == AlertLevel.ERROR
        assert added.status == AlertStatus.PENDING
        assert added.current_value == Decimal("0")
        assert added.message == "daily cap"
        assert added.auto_resolve is True
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(added)
        assert result is added

    async def test_create_alert_defaults_applied_when_omitted(self):
        """边界: 省略可选参数时使用默认值"""
        # Arrange
        db = _make_mock_db()
        service = CostAlertService(db)
        # Act
        await service.create_alert(
            alert_name="minimal",
            target_type="global",
            threshold_type="total",
            threshold_value=Decimal("10"),
        )
        # Assert
        added = db.add.call_args.args[0]
        assert added.level == AlertLevel.WARNING
        assert added.target_id is None
        assert added.message is None
        assert added.auto_resolve is False
        assert added.status == AlertStatus.PENDING
        assert added.current_value == Decimal("0")

    async def test_create_alert_commit_failure_propagates_exception(self):
        """异常: 提交失败时异常向上传播且不刷新"""
        # Arrange
        db = _make_mock_db()
        db.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
        service = CostAlertService(db)
        # Act / Assert
        with pytest.raises(RuntimeError, match="commit failed"):
            await service.create_alert("n", "global", "total", Decimal("1"))
        db.add.assert_called_once()
        db.refresh.assert_not_awaited()


class TestCostAlertServiceGetAlert:
    """CostAlertService.get_alert 方法测试"""

    async def test_get_alert_found_returns_alert(self):
        """正常: 命中返回告警对象"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = alert
        db.execute = AsyncMock(return_value=result_mock)
        service = CostAlertService(db)
        # Act
        result = await service.get_alert("alert-1")
        # Assert
        assert result is alert

    async def test_get_alert_not_found_raises_validation_error(self):
        """异常: 未命中抛 ValidationError"""
        # Arrange
        db = _make_mock_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)
        service = CostAlertService(db)
        # Act / Assert
        with pytest.raises(ValidationError, match="告警不存在"):
            await service.get_alert("missing")

    async def test_get_alert_execute_failure_propagates_exception(self):
        """异常: 查询失败时异常向上传播"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(side_effect=RuntimeError("db down"))
        service = CostAlertService(db)
        # Act / Assert
        with pytest.raises(RuntimeError, match="db down"):
            await service.get_alert("alert-1")


class TestCostAlertServiceListAlerts:
    """CostAlertService.list_alerts 方法测试"""

    async def test_list_alerts_no_filters_returns_list(self):
        """正常: 无过滤返回列表且查询无 WHERE"""
        # Arrange
        db = _make_mock_db()
        alerts = [_make_alert(alert_id="a1"), _make_alert(alert_id="a2")]
        db.execute = AsyncMock(return_value=_make_list_result(alerts))
        service = CostAlertService(db)
        # Act
        result = await service.list_alerts()
        # Assert
        assert result == alerts
        sql = str(db.execute.call_args.args[0])
        assert "WHERE" not in sql
        assert "ORDER BY" in sql

    async def test_list_alerts_empty_returns_empty_list(self):
        """边界: 无数据返回空列表"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_list_result([]))
        service = CostAlertService(db)
        # Act
        result = await service.list_alerts()
        # Assert
        assert result == []

    async def test_list_alerts_all_filters_applies_where(self):
        """正常: 全部过滤条件均附加 WHERE"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_list_result([]))
        service = CostAlertService(db)
        # Act
        await service.list_alerts(
            target_type="model",
            target_id="m1",
            status=AlertStatus.PENDING,
            is_enabled=True,
        )
        # Assert
        sql = str(db.execute.call_args.args[0])
        assert "WHERE" in sql
        assert "target_type" in sql
        assert "target_id" in sql
        assert "status" in sql
        assert "is_enabled" in sql

    async def test_list_alerts_is_enabled_false_applies_filter(self):
        """边界: is_enabled=False(非None)仍附加过滤"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_list_result([]))
        service = CostAlertService(db)
        # Act
        await service.list_alerts(is_enabled=False)
        # Assert
        sql = str(db.execute.call_args.args[0])
        assert "is_enabled" in sql

    async def test_list_alerts_execute_failure_propagates_exception(self):
        """异常: 查询失败时异常向上传播"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(side_effect=RuntimeError("db down"))
        service = CostAlertService(db)
        # Act / Assert
        with pytest.raises(RuntimeError, match="db down"):
            await service.list_alerts()


class TestCostAlertServiceCheckCosts:
    """CostAlertService.check_costs 方法测试"""

    async def test_check_costs_no_alerts_returns_empty_no_commit(self):
        """边界: 无启用告警返回空且不提交"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_list_result([]))
        service = CostAlertService(db)
        # Act
        result = await service.check_costs()
        # Assert
        assert result == []
        db.commit.assert_not_awaited()

    async def test_check_costs_below_threshold_not_triggered(self):
        """正常: 成本低于阈值不触发且不提交"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert(
            threshold_value=Decimal("100"),
            status=AlertStatus.RESOLVED,
        )
        db.execute = AsyncMock(
            side_effect=[
                _make_list_result([alert]),
                _make_cost_result(Decimal("50")),
            ]
        )
        service = CostAlertService(db)
        # Act
        result = await service.check_costs()
        # Assert
        assert result == []
        assert alert.current_value == Decimal("50")
        assert alert.status == AlertStatus.RESOLVED
        db.commit.assert_not_awaited()

    async def test_check_costs_exceeds_threshold_resolved_triggers(self):
        """正常: 超阈值且状态为 RESOLVED 触发告警并提交"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert(
            threshold_value=Decimal("100"),
            status=AlertStatus.RESOLVED,
        )
        db.execute = AsyncMock(
            side_effect=[
                _make_list_result([alert]),
                _make_cost_result(Decimal("150")),
            ]
        )
        service = CostAlertService(db)
        # Act
        result = await service.check_costs()
        # Assert
        assert len(result) == 1
        assert result[0] is alert
        assert alert.status == AlertStatus.PENDING
        assert alert.triggered_at is not None
        assert alert.message is not None
        assert "test-alert" in alert.message
        db.commit.assert_awaited_once()

    async def test_check_costs_exceeds_threshold_pending_skipped(self):
        """边界: 超阈值但状态为 PENDING 跳过且不提交"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert(
            threshold_value=Decimal("100"),
            status=AlertStatus.PENDING,
        )
        db.execute = AsyncMock(
            side_effect=[
                _make_list_result([alert]),
                _make_cost_result(Decimal("150")),
            ]
        )
        service = CostAlertService(db)
        # Act
        result = await service.check_costs()
        # Assert
        assert result == []
        assert alert.status == AlertStatus.PENDING
        db.commit.assert_not_awaited()

    async def test_check_costs_exceeds_threshold_notified_skipped(self):
        """边界: 超阈值但状态为 NOTIFIED 跳过且不提交"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert(
            threshold_value=Decimal("100"),
            status=AlertStatus.NOTIFIED,
        )
        db.execute = AsyncMock(
            side_effect=[
                _make_list_result([alert]),
                _make_cost_result(Decimal("150")),
            ]
        )
        service = CostAlertService(db)
        # Act
        result = await service.check_costs()
        # Assert
        assert result == []
        assert alert.status == AlertStatus.NOTIFIED
        db.commit.assert_not_awaited()

    async def test_check_costs_equal_threshold_triggers(self):
        """边界: 成本等于阈值(>=)触发告警"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert(
            threshold_value=Decimal("100"),
            status=AlertStatus.ACKNOWLEDGED,
        )
        db.execute = AsyncMock(
            side_effect=[
                _make_list_result([alert]),
                _make_cost_result(Decimal("100")),
            ]
        )
        service = CostAlertService(db)
        # Act
        result = await service.check_costs()
        # Assert
        assert len(result) == 1
        assert alert.status == AlertStatus.PENDING
        db.commit.assert_awaited_once()

    async def test_check_costs_multiple_alerts_partial_triggered(self):
        """正常: 多告警混合仅触发符合条件的子集"""
        # Arrange
        db = _make_mock_db()
        triggered = _make_alert(
            alert_id="a1",
            threshold_value=Decimal("100"),
            status=AlertStatus.RESOLVED,
        )
        skipped = _make_alert(
            alert_id="a2",
            threshold_value=Decimal("100"),
            status=AlertStatus.PENDING,
        )
        below = _make_alert(
            alert_id="a3",
            threshold_value=Decimal("200"),
            status=AlertStatus.RESOLVED,
        )
        db.execute = AsyncMock(
            side_effect=[
                _make_list_result([triggered, skipped, below]),
                _make_cost_result(Decimal("150")),
                _make_cost_result(Decimal("150")),
                _make_cost_result(Decimal("50")),
            ]
        )
        service = CostAlertService(db)
        # Act
        result = await service.check_costs()
        # Assert
        assert len(result) == 1
        assert result[0] is triggered
        db.commit.assert_awaited_once()

    async def test_check_costs_calculate_failure_propagates_exception(self):
        """异常: 成本计算失败时异常向上传播且不提交"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert(
            threshold_value=Decimal("100"),
            status=AlertStatus.RESOLVED,
        )
        db.execute = AsyncMock(
            side_effect=[
                _make_list_result([alert]),
                RuntimeError("calc failed"),
            ]
        )
        service = CostAlertService(db)
        # Act / Assert
        with pytest.raises(RuntimeError, match="calc failed"):
            await service.check_costs()
        db.commit.assert_not_awaited()


class TestCostAlertServiceResolveAlert:
    """CostAlertService.resolve_alert 方法测试"""

    async def test_resolve_alert_manual_sets_resolved(self):
        """正常: 手动解决设置 RESOLVED 并记录解决人"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert(status=AlertStatus.PENDING)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = alert
        db.execute = AsyncMock(return_value=result_mock)
        service = CostAlertService(db)
        # Act
        result = await service.resolve_alert("alert-1", resolved_by="admin")
        # Assert
        assert alert.status == AlertStatus.RESOLVED
        assert alert.resolved_by == "admin"
        assert alert.resolved_at is not None
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(alert)
        assert result is alert

    async def test_resolve_alert_auto_sets_auto_resolved(self):
        """正常: 自动解决设置 AUTO_RESOLVED 且无解决人"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert(status=AlertStatus.PENDING)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = alert
        db.execute = AsyncMock(return_value=result_mock)
        service = CostAlertService(db)
        # Act
        result = await service.resolve_alert("alert-1", auto=True)
        # Assert
        assert result.status == AlertStatus.AUTO_RESOLVED
        assert result.resolved_by is None

    async def test_resolve_alert_not_found_raises_validation_error(self):
        """异常: 告警不存在抛 ValidationError"""
        # Arrange
        db = _make_mock_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)
        service = CostAlertService(db)
        # Act / Assert
        with pytest.raises(ValidationError, match="告警不存在"):
            await service.resolve_alert("missing")


class TestCostAlertServiceAcknowledgeAlert:
    """CostAlertService.acknowledge_alert 方法测试"""

    async def test_acknowledge_alert_success_sets_acknowledged(self):
        """正常: 确认告警设置 ACKNOWLEDGED"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert(status=AlertStatus.PENDING)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = alert
        db.execute = AsyncMock(return_value=result_mock)
        service = CostAlertService(db)
        # Act
        result = await service.acknowledge_alert("alert-1")
        # Assert
        assert alert.status == AlertStatus.ACKNOWLEDGED
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(alert)
        assert result is alert

    async def test_acknowledge_alert_not_found_raises_validation_error(self):
        """异常: 告警不存在抛 ValidationError"""
        # Arrange
        db = _make_mock_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)
        service = CostAlertService(db)
        # Act / Assert
        with pytest.raises(ValidationError, match="告警不存在"):
            await service.acknowledge_alert("missing")


class TestCostAlertServiceDeleteAlert:
    """CostAlertService.delete_alert 方法测试"""

    async def test_delete_alert_success_calls_delete_and_commit(self):
        """正常: 删除调用 db.delete 并提交"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = alert
        db.execute = AsyncMock(return_value=result_mock)
        service = CostAlertService(db)
        # Act
        await service.delete_alert("alert-1")
        # Assert
        db.delete.assert_awaited_once_with(alert)
        db.commit.assert_awaited_once()

    async def test_delete_alert_not_found_raises_validation_error(self):
        """异常: 告警不存在抛 ValidationError 且不删除"""
        # Arrange
        db = _make_mock_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)
        service = CostAlertService(db)
        # Act / Assert
        with pytest.raises(ValidationError, match="告警不存在"):
            await service.delete_alert("missing")
        db.delete.assert_not_awaited()

    async def test_delete_alert_commit_failure_propagates_exception(self):
        """异常: 提交失败时异常向上传播"""
        # Arrange
        db = _make_mock_db()
        alert = _make_alert()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = alert
        db.execute = AsyncMock(return_value=result_mock)
        db.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
        service = CostAlertService(db)
        # Act / Assert
        with pytest.raises(RuntimeError, match="commit failed"):
            await service.delete_alert("alert-1")
        db.delete.assert_awaited_once()


class TestCostAlertServiceCalculateCost:
    """CostAlertService._calculate_current_cost 方法测试"""

    async def test_calculate_cost_daily_applies_time_filter(self):
        """正常: daily 阈值附加时间过滤并返回 Decimal"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_cost_result(Decimal("42.5")))
        service = CostAlertService(db)
        alert = _make_alert(threshold_type="daily", target_type="global")
        # Act
        cost = await service._calculate_current_cost(alert)
        # Assert
        assert cost == Decimal("42.5")
        assert isinstance(cost, Decimal)
        sql = str(db.execute.call_args.args[0])
        assert "created_at" in sql
        assert "model_usage_logs" in sql

    async def test_calculate_cost_monthly_applies_time_filter(self):
        """正常: monthly 阈值附加时间过滤"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_cost_result(Decimal("10")))
        service = CostAlertService(db)
        alert = _make_alert(threshold_type="monthly", target_type="global")
        # Act
        cost = await service._calculate_current_cost(alert)
        # Assert
        assert cost == Decimal("10")
        sql = str(db.execute.call_args.args[0])
        assert "created_at" in sql

    async def test_calculate_cost_total_no_time_filter(self):
        """正常: total 阈值不附加时间过滤"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_cost_result(Decimal("10")))
        service = CostAlertService(db)
        alert = _make_alert(threshold_type="total", target_type="global")
        # Act
        await service._calculate_current_cost(alert)
        # Assert
        sql = str(db.execute.call_args.args[0])
        assert "created_at" not in sql

    async def test_calculate_cost_model_target_filters_model_id(self):
        """正常: model 目标附加 model_id 过滤"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_cost_result(Decimal("10")))
        service = CostAlertService(db)
        alert = _make_alert(
            target_type="model",
            target_id="model-1",
            threshold_type="total",
        )
        # Act
        await service._calculate_current_cost(alert)
        # Assert
        sql = str(db.execute.call_args.args[0])
        assert "model_id" in sql
        assert "user_id" not in sql

    async def test_calculate_cost_user_target_filters_user_id(self):
        """正常: user 目标附加 user_id 过滤"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_cost_result(Decimal("10")))
        service = CostAlertService(db)
        alert = _make_alert(
            target_type="user",
            target_id="user-1",
            threshold_type="total",
        )
        # Act
        await service._calculate_current_cost(alert)
        # Assert
        sql = str(db.execute.call_args.args[0])
        assert "user_id" in sql
        assert "model_id" not in sql

    async def test_calculate_cost_global_no_target_filter(self):
        """正常: global 目标不附加目标过滤"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_cost_result(Decimal("10")))
        service = CostAlertService(db)
        alert = _make_alert(
            target_type="global",
            target_id=None,
            threshold_type="total",
        )
        # Act
        await service._calculate_current_cost(alert)
        # Assert
        sql = str(db.execute.call_args.args[0])
        assert "model_id" not in sql
        assert "user_id" not in sql

    async def test_calculate_cost_model_without_target_id_no_filter(self):
        """边界: target_type=model 但 target_id 为 None 时不附加过滤"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_cost_result(Decimal("10")))
        service = CostAlertService(db)
        alert = _make_alert(
            target_type="model",
            target_id=None,
            threshold_type="total",
        )
        # Act
        await service._calculate_current_cost(alert)
        # Assert
        sql = str(db.execute.call_args.args[0])
        assert "model_id" not in sql
        assert "user_id" not in sql

    async def test_calculate_cost_none_scalar_returns_zero(self):
        """边界: scalar 返回 None 时归零"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_cost_result(None))
        service = CostAlertService(db)
        alert = _make_alert(threshold_type="total", target_type="global")
        # Act
        cost = await service._calculate_current_cost(alert)
        # Assert
        assert cost == Decimal("0")

    async def test_calculate_cost_zero_scalar_returns_zero(self):
        """边界: scalar 返回 0(falsy) 时归零"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=_make_cost_result(0))
        service = CostAlertService(db)
        alert = _make_alert(threshold_type="total", target_type="global")
        # Act
        cost = await service._calculate_current_cost(alert)
        # Assert
        assert cost == Decimal("0")

    async def test_calculate_cost_execute_failure_propagates_exception(self):
        """异常: 查询失败时异常向上传播"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(side_effect=RuntimeError("db down"))
        service = CostAlertService(db)
        alert = _make_alert(threshold_type="total", target_type="global")
        # Act / Assert
        with pytest.raises(RuntimeError, match="db down"):
            await service._calculate_current_cost(alert)


class TestCostAlertServiceGenerateMessage:
    """CostAlertService._generate_alert_message 方法测试"""

    def test_generate_message_normal_returns_formatted(self):
        """正常: 返回包含名称/当前值/阈值/占比的格式化消息"""
        # Arrange
        service = CostAlertService(MagicMock())
        alert = _make_alert(
            alert_name="budget",
            threshold_value=Decimal("100"),
        )
        # Act
        msg = service._generate_alert_message(alert, Decimal("150"))
        # Assert
        assert "budget" in msg
        assert "150.0000" in msg
        assert "100.0000" in msg
        assert "150.0%" in msg

    def test_generate_message_equal_threshold_returns_100_percent(self):
        """边界: 当前值等于阈值时占比 100.0%"""
        # Arrange
        service = CostAlertService(MagicMock())
        alert = _make_alert(threshold_value=Decimal("100"))
        # Act
        msg = service._generate_alert_message(alert, Decimal("100"))
        # Assert
        assert "100.0%" in msg

    def test_generate_message_zero_threshold_raises_division_by_zero(self):
        """异常: 阈值为零时触发除零异常"""
        # Arrange
        service = CostAlertService(MagicMock())
        alert = _make_alert(threshold_value=Decimal("0"))
        # Act / Assert
        with pytest.raises(DivisionByZero):
            service._generate_alert_message(alert, Decimal("10"))
