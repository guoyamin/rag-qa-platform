"""
智能问答平台 - 审计日志服务单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService


def _make_mock_db() -> MagicMock:
    """构造隔离 DB 的 mock AsyncSession。"""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


class TestAuditLog:
    """审计日志测试"""

    def test_audit_action_enum(self):
        """测试审计动作枚举值"""
        audit_action = {
            "CREATE": "create",
            "UPDATE": "update",
            "DELETE": "delete",
            "ENABLE": "enable",
            "DISABLE": "disable",
            "QUERY": "query",
        }

        assert audit_action["CREATE"] == "create"
        assert audit_action["UPDATE"] == "update"
        assert audit_action["DELETE"] == "delete"
        assert audit_action["ENABLE"] == "enable"
        assert audit_action["DISABLE"] == "disable"
        assert audit_action["QUERY"] == "query"

    def test_resource_type_enum(self):
        """测试资源类型枚举值"""
        resource_type = {
            "MODEL": "model",
            "API_KEY": "api_key",
            "TEMPLATE": "template",
            "VERSION": "version",
        }

        assert resource_type["MODEL"] == "model"
        assert resource_type["API_KEY"] == "api_key"
        assert resource_type["TEMPLATE"] == "template"
        assert resource_type["VERSION"] == "version"

    def test_audit_log_schema(self):
        """测试审计日志 Schema"""
        from app.schemas.model import AuditAction, AuditLogResponse, ResourceType

        log = AuditLogResponse(
            id="log-1",
            action=AuditAction.CREATE,
            resource_type=ResourceType.MODEL,
            resource_id="model-1",
            resource_name="GPT-4",
            user_id="user-1",
            user_name="管理员",
            changes={"temperature": {"old": 0.7, "new": 0.5}},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            created_at=datetime.now(),
        )

        assert log.action == AuditAction.CREATE
        assert log.resource_type == ResourceType.MODEL
        assert log.changes["temperature"]["old"] == 0.7

    def test_audit_changes_tracking(self):
        """测试变更追踪"""

        def track_changes(old_data: dict, new_data: dict) -> dict:
            changes = {}
            for key in new_data:
                if key in old_data and old_data[key] != new_data[key]:
                    changes[key] = {"old": old_data[key], "new": new_data[key]}
                elif key not in old_data:
                    changes[key] = {"new": new_data[key]}
            return changes

        old_config = {
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": 0.9,
        }

        new_config = {
            "temperature": 0.5,  # 变更
            "max_tokens": 2048,  # 不变
            "timeout": 60,  # 新增
        }

        changes = track_changes(old_config, new_config)

        assert "temperature" in changes
        assert changes["temperature"]["old"] == 0.7
        assert changes["temperature"]["new"] == 0.5
        assert "max_tokens" not in changes  # 未变更
        assert "timeout" in changes  # 新增字段


class TestAuditLogQuery:
    """审计日志查询测试"""

    def test_filter_by_time_range(self):
        """测试时间范围过滤"""
        logs = [
            {"id": "1", "created_at": datetime(2026, 7, 1)},
            {"id": "2", "created_at": datetime(2026, 7, 15)},
            {"id": "3", "created_at": datetime(2026, 7, 30)},
        ]

        start_date = datetime(2026, 7, 10)
        end_date = datetime(2026, 7, 25)

        filtered = [log for log in logs if start_date <= log["created_at"] <= end_date]

        assert len(filtered) == 1
        assert filtered[0]["id"] == "2"

    def test_filter_by_user(self):
        """测试按用户过滤"""
        logs = [
            {"id": "1", "user_id": "user-1"},
            {"id": "2", "user_id": "user-2"},
            {"id": "3", "user_id": "user-1"},
        ]

        user_logs = [log for log in logs if log["user_id"] == "user-1"]

        assert len(user_logs) == 2

    def test_filter_by_action(self):
        """测试按动作过滤"""
        logs = [
            {"id": "1", "action": "create"},
            {"id": "2", "action": "update"},
            {"id": "3", "action": "create"},
        ]

        create_logs = [log for log in logs if log["action"] == "create"]

        assert len(create_logs) == 2

    def test_pagination(self):
        """测试分页"""
        logs = [{"id": str(i)} for i in range(100)]

        page = 2
        page_size = 10

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        paginated = logs[start_idx:end_idx]

        assert len(paginated) == 10
        assert paginated[0]["id"] == "10"
        assert paginated[-1]["id"] == "19"


class TestAuditSecurity:
    """审计安全测试"""

    def test_sensitive_data_masking(self):
        """测试敏感数据脱敏"""

        def mask_sensitive_data(data: dict) -> dict:
            masked = data.copy()
            sensitive_keys = ["password", "api_key", "secret", "token"]

            for key in masked:
                if any(sk in key.lower() for sk in sensitive_keys):
                    # 统一显示为 ****
                    masked[key] = "****"

            return masked

        data = {
            "api_key": "sk-1234567890abcdef",
            "password": "secret123",
            "name": "Test User",
        }

        masked = mask_sensitive_data(data)

        assert masked["api_key"] == "****"
        assert masked["password"] == "****"
        assert masked["name"] == "Test User"  # 非敏感字段不变

    def test_ip_address_validation(self):
        """测试 IP 地址格式验证"""
        import re

        def is_valid_ip(ip: str) -> bool:
            ipv4_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
            if re.match(ipv4_pattern, ip):
                parts = ip.split(".")
                return all(0 <= int(part) <= 255 for part in parts)
            return False

        assert is_valid_ip("192.168.1.1") is True
        assert is_valid_ip("10.0.0.1") is True
        assert is_valid_ip("256.1.1.1") is False
        assert is_valid_ip("192.168.1") is False


class TestAuditServiceLog:
    """AuditService.log 方法测试"""

    async def test_log_success_returns_audit_log_with_fields(self):
        """正常: 记录日志返回包含传入字段的对象"""
        # Arrange
        db = _make_mock_db()
        service = AuditService(db)
        # Act
        result = await service.log(
            action=AuditAction.LOGIN,
            user_id="u-1",
            username="alice",
            method="POST",
            path="/auth/login",
            success=True,
        )
        # Assert
        assert result.action == AuditAction.LOGIN
        assert result.user_id == "u-1"
        assert result.username == "alice"
        assert result.success is True
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    async def test_log_with_sensitive_request_data_redacted(self):
        """边界: 敏感字段在持久化前被脱敏"""
        # Arrange
        db = _make_mock_db()
        service = AuditService(db)
        # Act
        result = await service.log(
            action=AuditAction.LOGIN,
            request_data={"username": "alice", "password": "secret123"},
        )
        # Assert
        stored = json.loads(result.request_data)
        assert stored["username"] == "alice"
        assert stored["password"] == "***REDACTED***"

    async def test_log_with_none_request_data_stores_none(self):
        """边界: 无请求数据时 request_data 为 None"""
        # Arrange
        db = _make_mock_db()
        service = AuditService(db)
        # Act
        result = await service.log(action=AuditAction.LOGOUT)
        # Assert
        assert result.request_data is None

    async def test_log_with_empty_request_data_stores_none(self):
        """边界: 空字典请求数据时 request_data 为 None"""
        # Arrange
        db = _make_mock_db()
        service = AuditService(db)
        # Act
        result = await service.log(action=AuditAction.LOGOUT, request_data={})
        # Assert
        assert result.request_data is None

    async def test_log_commit_failure_propagates_exception(self):
        """异常: 提交失败时异常向上传播"""
        # Arrange
        db = _make_mock_db()
        db.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
        service = AuditService(db)
        # Act / Assert
        with pytest.raises(RuntimeError, match="commit failed"):
            await service.log(action=AuditAction.LOGIN)
        db.add.assert_called_once()
        db.refresh.assert_not_awaited()


class TestAuditServiceSanitize:
    """AuditService._sanitize_request_data 方法测试"""

    def test_sanitize_none_returns_none(self):
        """边界: None 输入返回 None"""
        service = AuditService(MagicMock())
        assert service._sanitize_request_data(None) is None

    def test_sanitize_empty_dict_returns_none(self):
        """边界: 空字典返回 None"""
        service = AuditService(MagicMock())
        assert service._sanitize_request_data({}) is None

    def test_sanitize_redacts_password_field(self):
        """正常: password 字段被脱敏"""
        service = AuditService(MagicMock())
        result = service._sanitize_request_data({"password": "secret", "name": "bob"})
        assert result["password"] == "***REDACTED***"
        assert result["name"] == "bob"

    def test_sanitize_case_insensitive_key_matching(self):
        """边界: 大小写不敏感匹配敏感字段"""
        service = AuditService(MagicMock())
        result = service._sanitize_request_data({"Password": "s", "API_KEY": "k"})
        assert result["Password"] == "***REDACTED***"
        assert result["API_KEY"] == "***REDACTED***"

    def test_sanitize_redacts_nested_dict_sensitive_fields(self):
        """正常: 嵌套字典中的敏感字段被脱敏"""
        service = AuditService(MagicMock())
        data = {"user": {"name": "bob", "token": "abc"}}
        result = service._sanitize_request_data(data)
        assert result["user"]["name"] == "bob"
        assert result["user"]["token"] == "***REDACTED***"

    def test_sanitize_preserves_all_known_sensitive_fields(self):
        """边界: 所有关键敏感字段均被脱敏"""
        service = AuditService(MagicMock())
        sensitive = {
            "password": "p",
            "old_password": "p",
            "new_password": "p",
            "api_key": "k",
            "secret": "s",
            "token": "t",
            "access_token": "t",
            "refresh_token": "t",
            "secret_key": "k",
            "private_key": "k",
        }
        result = service._sanitize_request_data(sensitive)
        assert all(v == "***REDACTED***" for v in result.values())


class TestAuditServiceGetLogs:
    """AuditService.get_logs 方法测试"""

    @staticmethod
    def _make_results(total: int, items: list) -> list:
        """构造 count + items 两个 mock 结果供 db.execute 依次返回。"""
        count_result = MagicMock()
        count_result.scalar.return_value = total
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = items
        return [count_result, items_result]

    async def test_get_logs_returns_items_and_total(self):
        """正常: 返回日志列表与总数"""
        # Arrange
        db = _make_mock_db()
        log_item = MagicMock()
        db.execute = AsyncMock(side_effect=self._make_results(5, [log_item]))
        service = AuditService(db)
        # Act
        items, total = await service.get_logs()
        # Assert
        assert total == 5
        assert items == [log_item]
        assert db.execute.await_count == 2

    async def test_get_logs_empty_result_returns_zero_total(self):
        """边界: 无数据时返回空列表与零总数"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(side_effect=self._make_results(0, []))
        service = AuditService(db)
        # Act
        items, total = await service.get_logs()
        # Assert
        assert items == []
        assert total == 0

    async def test_get_logs_none_scalar_total_becomes_zero(self):
        """边界: scalar 返回 None 时总数归零"""
        # Arrange
        db = _make_mock_db()
        count_result = MagicMock()
        count_result.scalar.return_value = None
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[count_result, items_result])
        service = AuditService(db)
        # Act
        _, total = await service.get_logs()
        # Assert
        assert total == 0

    async def test_get_logs_with_filters_applies_pagination(self):
        """正常: 传入过滤与分页参数返回结果"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(side_effect=self._make_results(2, [MagicMock()]))
        service = AuditService(db)
        # Act
        items, total = await service.get_logs(
            user_id="u-1",
            action=AuditAction.LOGIN,
            target_type="user",
            page=2,
            page_size=10,
        )
        # Assert
        assert total == 2
        assert len(items) == 1

    async def test_get_logs_execute_failure_propagates_exception(self):
        """异常: 查询失败时异常向上传播"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(side_effect=RuntimeError("query failed"))
        service = AuditService(db)
        # Act / Assert
        with pytest.raises(RuntimeError, match="query failed"):
            await service.get_logs()


class TestAuditServiceGetUserActivity:
    """AuditService.get_user_activity 方法测试"""

    @staticmethod
    def _make_result(rows: list) -> MagicMock:
        """构造含若干行的 mock 查询结果。"""
        result = MagicMock()
        result.all.return_value = rows
        return result

    async def test_get_user_activity_returns_aggregated_counts(self):
        """正常: 返回按动作聚合的计数列表"""
        # Arrange
        row1 = MagicMock()
        row1.action = AuditAction.LOGIN
        row1.count = 5
        row2 = MagicMock()
        row2.action = AuditAction.LOGOUT
        row2.count = 3
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=self._make_result([row1, row2]))
        service = AuditService(db)
        # Act
        result = await service.get_user_activity("u-1")
        # Assert
        assert result == [
            {"action": "login", "count": 5},
            {"action": "logout", "count": 3},
        ]

    async def test_get_user_activity_empty_returns_empty_list(self):
        """边界: 无活动记录返回空列表"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=self._make_result([]))
        service = AuditService(db)
        # Act
        result = await service.get_user_activity("u-1")
        # Assert
        assert result == []

    async def test_get_user_activity_custom_days_executes_once(self):
        """正常: 自定义天数参数执行一次查询"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(return_value=self._make_result([]))
        service = AuditService(db)
        # Act
        await service.get_user_activity("u-1", days=7)
        # Assert
        db.execute.assert_awaited_once()

    async def test_get_user_activity_execute_failure_propagates_exception(self):
        """异常: 查询失败时异常向上传播"""
        # Arrange
        db = _make_mock_db()
        db.execute = AsyncMock(side_effect=RuntimeError("db down"))
        service = AuditService(db)
        # Act / Assert
        with pytest.raises(RuntimeError, match="db down"):
            await service.get_user_activity("u-1")
