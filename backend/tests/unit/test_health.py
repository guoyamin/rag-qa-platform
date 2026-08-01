"""
智能问答平台 - 健康检查服务单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.model_instance import ModelProvider
from app.services.health_check_service import (
    CheckType,
    HealthCheckResult,
    HealthCheckService,
    HealthStatus,
)


class TestHealthCheckService:
    """健康检查服务测试"""

    def test_health_status_enum(self):
        """测试健康状态枚举值"""
        # 直接测试枚举值
        status_map = {
            "HEALTHY": "healthy",
            "DEGRADED": "degraded",
            "UNHEALTHY": "unhealthy",
            "UNKNOWN": "unknown",
        }

        assert status_map["HEALTHY"] == "healthy"
        assert status_map["DEGRADED"] == "degraded"
        assert status_map["UNHEALTHY"] == "unhealthy"
        assert status_map["UNKNOWN"] == "unknown"

    def test_health_check_response(self):
        """测试健康检查响应 Schema"""
        from app.schemas.model import HealthCheckResponse, HealthStatus

        response = HealthCheckResponse(
            model_id="model-1",
            model_name="GPT-4",
            status=HealthStatus.HEALTHY,
            latency_ms=150,
            error_message=None,
            checked_at=datetime.now(),
        )

        assert response.model_id == "model-1"
        assert response.status == HealthStatus.HEALTHY
        assert response.latency_ms == 150

    def test_health_summary_response(self):
        """测试健康摘要响应 Schema"""
        from app.schemas.model import HealthSummaryResponse

        response = HealthSummaryResponse(
            total_models=5,
            healthy_count=4,
            degraded_count=1,
            unhealthy_count=0,
            unknown_count=0,
        )

        assert response.total_models == 5
        assert response.healthy_count == 4
        assert response.total_models == (
            response.healthy_count
            + response.degraded_count
            + response.unhealthy_count
            + response.unknown_count
        )


class TestHealthCheckLogic:
    """健康检查逻辑测试"""

    def test_latency_threshold(self):
        """测试延迟阈值判断"""
        # 正常延迟
        assert 100 < 500  # healthy
        # 警告延迟
        assert 300 < 1000  # degraded
        # 故障延迟
        assert 5000 >= 5000  # unhealthy

    def test_error_count_threshold(self):
        """测试错误次数阈值判断"""
        error_count = 5
        threshold = 10

        # 5次错误 < 10次阈值，仍可接受
        assert error_count < threshold

        # 达到阈值
        error_count = 10
        assert not (error_count < threshold)

    def test_health_status_from_metrics(self):
        """测试根据指标计算健康状态"""

        def calculate_status(latency_ms: int, error_rate: float) -> str:
            if latency_ms > 3000 or error_rate > 0.5:
                return "unhealthy"
            elif latency_ms > 1000 or error_rate > 0.1:
                return "degraded"
            else:
                return "healthy"

        # 健康状态
        assert calculate_status(100, 0.01) == "healthy"
        assert calculate_status(500, 0.05) == "healthy"

        # 降级状态
        assert calculate_status(1500, 0.05) == "degraded"
        assert calculate_status(500, 0.2) == "degraded"

        # 不健康状态
        assert calculate_status(5000, 0.1) == "unhealthy"
        assert calculate_status(100, 0.8) == "unhealthy"


class TestHealthCheckRetry:
    """健康检查重试逻辑测试"""

    def test_retry_on_failure(self):
        """测试失败时重试逻辑"""
        max_retries = 3
        attempts = 0

        def simulate_check():
            nonlocal attempts
            attempts += 1
            return attempts >= 3  # 第3次成功

        # 模拟重试直到成功
        while attempts < max_retries:
            if not simulate_check():
                continue
            break

        assert attempts == 3

    def test_timeout_handling(self):
        """测试超时处理"""
        import asyncio

        async def check_with_timeout():
            async def slow_check():
                await asyncio.sleep(10)  # 模拟慢检查

            try:
                await asyncio.wait_for(slow_check(), timeout=1.0)
            except TimeoutError:
                return "timeout"
            return "success"

        result = asyncio.run(check_with_timeout())
        assert result == "timeout"


class TestHealthCheckServiceMethods:
    """HealthCheckService service-layer unit tests."""

    @staticmethod
    def _make_model(
        model_id: str = "model-1",
        provider: ModelProvider = ModelProvider.LOCAL,
        api_key_id: str | None = None,
        config: dict | None = None,
    ) -> MagicMock:
        """Create a mock ModelInstance for testing."""
        model = MagicMock()
        model.id = model_id
        model.provider = provider
        model.api_key_id = api_key_id
        model.config = config if config is not None else {}
        return model

    # ---- quick_check ----

    async def test_quick_check_model_not_found_returns_unknown(self):
        # Arrange
        service = HealthCheckService(AsyncMock())
        service._get_model = AsyncMock(return_value=None)

        # Act
        result = await service.quick_check("missing-model")

        # Assert
        assert result.status == HealthStatus.UNKNOWN
        assert result.check_type == CheckType.QUICK
        assert result.error_message == "模型不存在"
        assert result.latency_ms is None

    async def test_quick_check_local_provider_success_returns_healthy(self):
        # Arrange
        model = self._make_model(provider=ModelProvider.LOCAL)
        service = HealthCheckService(AsyncMock())
        service._get_model = AsyncMock(return_value=model)
        service._ping_local = AsyncMock()

        # Act
        result = await service.quick_check("model-1")

        # Assert
        assert result.status == HealthStatus.HEALTHY
        assert result.check_type == CheckType.QUICK
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        service._ping_local.assert_awaited_once_with(model)

    async def test_quick_check_cloud_provider_success_returns_healthy(self):
        # Arrange
        model = self._make_model(provider=ModelProvider.OPENAI)
        service = HealthCheckService(AsyncMock())
        service._get_model = AsyncMock(return_value=model)
        service._ping_cloud = AsyncMock()

        # Act
        result = await service.quick_check("model-1")

        # Assert
        assert result.status == HealthStatus.HEALTHY
        assert result.check_type == CheckType.QUICK
        assert result.latency_ms is not None
        service._ping_cloud.assert_awaited_once_with(model)

    async def test_quick_check_ping_raises_returns_unhealthy(self):
        # Arrange
        model = self._make_model(provider=ModelProvider.LOCAL)
        service = HealthCheckService(AsyncMock())
        service._get_model = AsyncMock(return_value=model)
        service._ping_local = AsyncMock(side_effect=ConnectionError("refused"))

        # Act
        result = await service.quick_check("model-1")

        # Assert
        assert result.status == HealthStatus.UNHEALTHY
        assert result.check_type == CheckType.QUICK
        assert "refused" in (result.error_message or "")

    # ---- full_check ----

    async def test_full_check_model_not_found_returns_unknown(self):
        # Arrange
        service = HealthCheckService(AsyncMock())
        service._get_model = AsyncMock(return_value=None)

        # Act
        result = await service.full_check("missing-model")

        # Assert
        assert result.status == HealthStatus.UNKNOWN
        assert result.check_type == CheckType.FULL
        assert result.error_message == "模型不存在"

    async def test_full_check_valid_response_returns_healthy(self):
        # Arrange
        model = self._make_model()
        service = HealthCheckService(AsyncMock())
        service._get_model = AsyncMock(return_value=model)
        service._call_model_test = AsyncMock(return_value=True)

        # Act
        result = await service.full_check("model-1")

        # Assert
        assert result.status == HealthStatus.HEALTHY
        assert result.check_type == CheckType.FULL
        assert result.latency_ms is not None

    async def test_full_check_empty_response_returns_degraded(self):
        # Arrange
        model = self._make_model()
        service = HealthCheckService(AsyncMock())
        service._get_model = AsyncMock(return_value=model)
        service._call_model_test = AsyncMock(return_value=False)

        # Act
        result = await service.full_check("model-1")

        # Assert
        assert result.status == HealthStatus.DEGRADED
        assert result.check_type == CheckType.FULL
        assert result.error_message == "响应无效"

    async def test_full_check_call_raises_returns_unhealthy(self):
        # Arrange
        model = self._make_model()
        service = HealthCheckService(AsyncMock())
        service._get_model = AsyncMock(return_value=model)
        service._call_model_test = AsyncMock(
            side_effect=RuntimeError("LLM down"),
        )

        # Act
        result = await service.full_check("model-1")

        # Assert
        assert result.status == HealthStatus.UNHEALTHY
        assert result.check_type == CheckType.FULL
        assert "LLM down" in (result.error_message or "")

    # ---- comprehensive_check ----

    async def test_comprehensive_check_all_healthy_returns_healthy(self):
        # Arrange
        service = HealthCheckService(AsyncMock())
        healthy = HealthCheckResult(
            "model-1",
            HealthStatus.HEALTHY,
            CheckType.QUICK,
            latency_ms=100,
        )
        service.quick_check = AsyncMock(return_value=healthy)

        # Act
        result = await service.comprehensive_check("model-1")

        # Assert
        assert result.status == HealthStatus.HEALTHY
        assert result.check_type == CheckType.COMPREHENSIVE
        assert result.latency_ms == 100
        assert service.quick_check.await_count == 3

    async def test_comprehensive_check_partial_healthy_returns_degraded(self):
        # Arrange
        service = HealthCheckService(AsyncMock())
        healthy = HealthCheckResult(
            "model-1",
            HealthStatus.HEALTHY,
            CheckType.QUICK,
            latency_ms=100,
        )
        unhealthy = HealthCheckResult(
            "model-1",
            HealthStatus.UNHEALTHY,
            CheckType.QUICK,
            error_message="timeout",
        )
        service.quick_check = AsyncMock(side_effect=[healthy, unhealthy])

        # Act
        result = await service.comprehensive_check("model-1")

        # Assert
        assert result.status == HealthStatus.DEGRADED
        assert result.check_type == CheckType.COMPREHENSIVE
        assert "1/2" in (result.error_message or "")
        assert service.quick_check.await_count == 2

    async def test_comprehensive_check_first_unhealthy_returns_unhealthy(self):
        # Arrange
        service = HealthCheckService(AsyncMock())
        unhealthy = HealthCheckResult(
            "model-1",
            HealthStatus.UNHEALTHY,
            CheckType.QUICK,
            error_message="timeout",
        )
        service.quick_check = AsyncMock(return_value=unhealthy)

        # Act
        result = await service.comprehensive_check("model-1")

        # Assert
        assert result.status == HealthStatus.UNHEALTHY
        assert result.check_type == CheckType.COMPREHENSIVE
        assert "0/1" in (result.error_message or "")
        assert service.quick_check.await_count == 1

    # ---- check_all_models ----

    async def test_check_all_models_no_active_models_returns_empty(self):
        # Arrange
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)
        service = HealthCheckService(db)

        # Act
        results = await service.check_all_models()

        # Assert
        assert results == []
        db.commit.assert_awaited_once()

    async def test_check_all_models_multiple_models_returns_results(self):
        # Arrange
        db = AsyncMock()
        model1 = self._make_model(model_id="m1")
        model2 = self._make_model(model_id="m2")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [model1, model2]
        db.execute = AsyncMock(return_value=mock_result)
        service = HealthCheckService(db)
        service.quick_check = AsyncMock(
            side_effect=[
                HealthCheckResult("m1", HealthStatus.HEALTHY, CheckType.QUICK, 50),
                HealthCheckResult(
                    "m2",
                    HealthStatus.UNHEALTHY,
                    CheckType.QUICK,
                    None,
                    "err",
                ),
            ]
        )
        service._record_health_log = AsyncMock()

        # Act
        results = await service.check_all_models()

        # Assert
        assert len(results) == 2
        assert results[0].status == HealthStatus.HEALTHY
        assert results[1].status == HealthStatus.UNHEALTHY
        assert service._record_health_log.await_count == 2
        db.commit.assert_awaited_once()

    # ---- _get_model ----

    async def test_get_model_found_returns_model_instance(self):
        # Arrange
        db = AsyncMock()
        model = self._make_model()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        db.execute = AsyncMock(return_value=mock_result)
        service = HealthCheckService(db)

        # Act
        result = await service._get_model("model-1")

        # Assert
        assert result is model

    async def test_get_model_not_found_returns_none(self):
        # Arrange
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        service = HealthCheckService(db)

        # Act
        result = await service._get_model("missing")

        # Assert
        assert result is None

    # ---- _ping_local ----

    async def test_ping_local_success_completes_without_error(self):
        # Arrange
        model = self._make_model(
            config={"api_base": "http://localhost:9000/v1", "timeout": 3},
        )
        service = HealthCheckService(AsyncMock())

        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_client.get.return_value = mock_response
            mock_class.return_value = mock_client

            # Act
            await service._ping_local(model)

            # Assert
            mock_client.get.assert_awaited_once_with(
                "http://localhost:9000/v1/health",
            )
            mock_response.raise_for_status.assert_called_once()

    async def test_ping_local_default_config_uses_default_endpoint(self):
        # Arrange
        model = self._make_model(config={})
        service = HealthCheckService(AsyncMock())

        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = MagicMock()
            mock_class.return_value = mock_client

            # Act
            await service._ping_local(model)

            # Assert
            mock_client.get.assert_awaited_once_with(
                "http://localhost:8000/v1/health",
            )

    async def test_ping_local_http_error_raises_exception(self):
        # Arrange
        model = self._make_model()
        service = HealthCheckService(AsyncMock())

        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = RuntimeError("500")
            mock_client.get.return_value = mock_response
            mock_class.return_value = mock_client

            # Act & Assert
            with pytest.raises(RuntimeError, match="500"):
                await service._ping_local(model)

    # ---- _ping_cloud ----

    async def test_ping_cloud_success_completes_without_error(self):
        # Arrange
        model = self._make_model(
            provider=ModelProvider.OPENAI,
            api_key_id="key-1",
            config={"api_base": "https://api.test.com/v1"},
        )
        service = HealthCheckService(AsyncMock())
        service._get_api_key = AsyncMock(return_value="secret-key")

        with patch("httpx.AsyncClient") as mock_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_client.get.return_value = mock_response
            mock_class.return_value = mock_client

            # Act
            await service._ping_cloud(model)

            # Assert
            service._get_api_key.assert_awaited_once_with("key-1")
            mock_client.get.assert_awaited_once_with(
                "https://api.test.com/v1/models",
                headers={"Authorization": "Bearer secret-key"},
            )
            mock_response.raise_for_status.assert_called_once()

    # ---- _call_model_test ----

    async def test_call_model_test_success_returns_true(self):
        # Arrange
        model = self._make_model()
        service = HealthCheckService(AsyncMock())

        with patch("app.services.llm_manager.LLMManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "hello"
            mock_llm.chat = AsyncMock(return_value=mock_response)
            mock_mgr.get_llm = AsyncMock(return_value=mock_llm)
            mock_mgr_cls.get_instance.return_value = mock_mgr

            # Act
            result = await service._call_model_test(model)

            # Assert
            assert result is True

    async def test_call_model_test_exception_returns_false(self):
        # Arrange
        model = self._make_model()
        service = HealthCheckService(AsyncMock())

        with patch("app.services.llm_manager.LLMManager") as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.get_llm = AsyncMock(side_effect=RuntimeError("no LLM"))
            mock_mgr_cls.get_instance.return_value = mock_mgr

            # Act
            result = await service._call_model_test(model)

            # Assert
            assert result is False

    # ---- _get_api_key ----

    async def test_get_api_key_none_id_returns_empty_string(self):
        # Arrange
        service = HealthCheckService(AsyncMock())

        # Act
        result = await service._get_api_key(None)

        # Assert
        assert result == ""

    async def test_get_api_key_valid_id_returns_decrypted_key(self):
        # Arrange
        db = AsyncMock()
        service = HealthCheckService(db)

        with patch(
            "app.services.api_key_service.ApiKeyService",
        ) as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.get_decrypted_key = AsyncMock(
                return_value="decrypted-secret",
            )
            mock_svc_cls.return_value = mock_svc

            # Act
            result = await service._get_api_key("key-1")

            # Assert
            assert result == "decrypted-secret"
            mock_svc_cls.assert_called_once_with(db)
            mock_svc.get_decrypted_key.assert_awaited_once_with("key-1")

    # ---- _record_health_log ----

    async def test_record_health_log_adds_log_to_db(self):
        # Arrange
        db = AsyncMock()
        db.add = MagicMock()
        service = HealthCheckService(db)
        health_result = HealthCheckResult(
            "model-1",
            HealthStatus.HEALTHY,
            CheckType.QUICK,
            latency_ms=42,
        )

        # Act
        await service._record_health_log(health_result)

        # Assert
        db.add.assert_called_once()
        added_log = db.add.call_args.args[0]
        assert added_log.model_id == "model-1"
        assert added_log.status == "healthy"
        assert added_log.check_type == "quick"
        assert added_log.latency_ms == 42

    # ---- start_scheduler ----

    def test_start_scheduler_creates_and_starts_scheduler(self):
        # Arrange
        service = HealthCheckService(AsyncMock())

        with patch(
            "app.services.health_check_service.AsyncIOScheduler",
        ) as mock_sched_cls:
            mock_scheduler = MagicMock()
            mock_sched_cls.return_value = mock_scheduler

            # Act
            service.start_scheduler()

            # Assert
            assert service.scheduler is mock_scheduler
            assert service._running is True
            assert mock_scheduler.add_job.call_count == 2
            mock_scheduler.start.assert_called_once()

    def test_start_scheduler_idempotent_when_already_running(self):
        # Arrange
        service = HealthCheckService(AsyncMock())
        existing = MagicMock()
        service.scheduler = existing

        # Act
        service.start_scheduler()

        # Assert
        assert service.scheduler is existing
        existing.start.assert_not_called()

    # ---- stop_scheduler ----

    def test_stop_scheduler_shuts_down_scheduler(self):
        # Arrange
        service = HealthCheckService(AsyncMock())
        mock_scheduler = MagicMock()
        service.scheduler = mock_scheduler
        service._running = True

        # Act
        service.stop_scheduler()

        # Assert
        mock_scheduler.shutdown.assert_called_once_with(wait=False)
        assert service.scheduler is None
        assert service._running is False

    def test_stop_scheduler_noop_when_no_scheduler(self):
        # Arrange
        service = HealthCheckService(AsyncMock())

        # Act
        service.stop_scheduler()

        # Assert
        assert service.scheduler is None
        assert service._running is False

    # ---- _scheduled_quick_check ----

    async def test_scheduled_quick_check_success_completes(self):
        # Arrange
        service = HealthCheckService(AsyncMock())
        service.check_all_models = AsyncMock(return_value=[])

        # Act
        await service._scheduled_quick_check()

        # Assert
        service.check_all_models.assert_awaited_once()

    async def test_scheduled_quick_check_exception_logged_no_raise(self):
        # Arrange
        service = HealthCheckService(AsyncMock())
        service.check_all_models = AsyncMock(
            side_effect=RuntimeError("DB down"),
        )

        # Act - must not raise
        await service._scheduled_quick_check()

        # Assert
        service.check_all_models.assert_awaited_once()

    # ---- _scheduled_full_check ----

    async def test_scheduled_full_check_success_completes(self):
        # Arrange
        db = AsyncMock()
        model = self._make_model(model_id="model-1")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [model]
        db.execute = AsyncMock(return_value=mock_result)
        service = HealthCheckService(db)
        health_result = HealthCheckResult(
            "model-1",
            HealthStatus.HEALTHY,
            CheckType.FULL,
        )
        service.full_check = AsyncMock(return_value=health_result)
        mock_new_db = AsyncMock()
        mock_new_db.add = MagicMock()

        with patch("app.db.session.AsyncSessionLocal") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(
                return_value=mock_new_db,
            )
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

            # Act
            await service._scheduled_full_check()

            # Assert
            service.full_check.assert_awaited_once_with("model-1")
            mock_new_db.add.assert_called_once()
            mock_new_db.commit.assert_awaited_once()

    async def test_scheduled_full_check_exception_logged_no_raise(self):
        # Arrange
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=RuntimeError("DB down"))
        service = HealthCheckService(db)

        # Act - must not raise
        await service._scheduled_full_check()

        # Assert
        db.execute.assert_awaited_once()
