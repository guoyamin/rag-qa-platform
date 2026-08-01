from __future__ import annotations

import time
from datetime import datetime
from enum import Enum

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_instance import ModelInstance, ModelStatus

logger = structlog.get_logger(__name__)


class HealthStatus(str, Enum):
    """健康状态"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(str, Enum):
    """检查类型"""

    QUICK = "quick"  # 30秒：只检查 API 可达性
    FULL = "full"  # 5分钟：发送测试请求
    COMPREHENSIVE = "comprehensive"  # 15分钟：综合评估


class HealthCheckResult:
    """健康检查结果"""

    def __init__(
        self,
        model_id: str,
        status: HealthStatus,
        check_type: CheckType,
        latency_ms: int | None = None,
        error_message: str | None = None,
        checked_at: datetime | None = None,
    ):
        self.model_id = model_id
        self.status = status
        self.check_type = check_type
        self.latency_ms = latency_ms
        self.error_message = error_message
        self.checked_at = checked_at or datetime.now()


class HealthCheckService:
    """健康检查服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.scheduler: AsyncIOScheduler | None = None
        self._running = False

    async def quick_check(self, model_id: str) -> HealthCheckResult:
        """
        快速探测：只检查 API 可达性

        适用于高频检查场景，开销最小
        """
        model = await self._get_model(model_id)
        if not model:
            return HealthCheckResult(
                model_id=model_id,
                status=HealthStatus.UNKNOWN,
                check_type=CheckType.QUICK,
                error_message="模型不存在",
            )

        start_time = time.time()

        try:
            # 根据提供商执行探测
            if model.provider.value == "local":
                # 本地模型：检查 endpoint 可达性
                await self._ping_local(model)
            else:
                # 云端模型：检查 API 可达性
                await self._ping_cloud(model)

            latency_ms = int((time.time() - start_time) * 1000)

            return HealthCheckResult(
                model_id=model_id,
                status=HealthStatus.HEALTHY,
                check_type=CheckType.QUICK,
                latency_ms=latency_ms,
            )

        except Exception as e:
            return HealthCheckResult(
                model_id=model_id,
                status=HealthStatus.UNHEALTHY,
                check_type=CheckType.QUICK,
                error_message=str(e),
            )

    async def full_check(self, model_id: str) -> HealthCheckResult:
        """
        完整探测：发送测试请求验证功能

        验证模型能正常响应
        """
        model = await self._get_model(model_id)
        if not model:
            return HealthCheckResult(
                model_id=model_id,
                status=HealthStatus.UNKNOWN,
                check_type=CheckType.FULL,
                error_message="模型不存在",
            )

        start_time = time.time()

        try:
            # 发送测试请求
            response = await self._call_model_test(model)
            latency_ms = int((time.time() - start_time) * 1000)

            if response:
                return HealthCheckResult(
                    model_id=model_id,
                    status=HealthStatus.HEALTHY,
                    check_type=CheckType.FULL,
                    latency_ms=latency_ms,
                )
            else:
                return HealthCheckResult(
                    model_id=model_id,
                    status=HealthStatus.DEGRADED,
                    check_type=CheckType.FULL,
                    latency_ms=latency_ms,
                    error_message="响应无效",
                )

        except Exception as e:
            return HealthCheckResult(
                model_id=model_id,
                status=HealthStatus.UNHEALTHY,
                check_type=CheckType.FULL,
                error_message=str(e),
            )

    async def comprehensive_check(self, model_id: str) -> HealthCheckResult:
        """
        综合评估：多指标评估

        综合响应时间、成功率等指标
        """
        # 执行多次快速探测
        results = []
        for _ in range(3):
            result = await self.quick_check(model_id)
            results.append(result)
            if result.status != HealthStatus.HEALTHY:
                break

        # 分析结果
        healthy_count = sum(1 for r in results if r.status == HealthStatus.HEALTHY)
        total = len(results)

        if healthy_count == total:
            avg_latency = sum(r.latency_ms or 0 for r in results) // total
            return HealthCheckResult(
                model_id=model_id,
                status=HealthStatus.HEALTHY,
                check_type=CheckType.COMPREHENSIVE,
                latency_ms=avg_latency,
            )
        elif healthy_count >= total / 2:
            return HealthCheckResult(
                model_id=model_id,
                status=HealthStatus.DEGRADED,
                check_type=CheckType.COMPREHENSIVE,
                error_message=f"{healthy_count}/{total} 次检查成功",
            )
        else:
            return HealthCheckResult(
                model_id=model_id,
                status=HealthStatus.UNHEALTHY,
                check_type=CheckType.COMPREHENSIVE,
                error_message=f"仅 {healthy_count}/{total} 次检查成功",
            )

    async def check_all_models(self) -> list[HealthCheckResult]:
        """检查所有活跃模型"""
        result = await self.db.execute(
            select(ModelInstance).where(ModelInstance.status == ModelStatus.ACTIVE)
        )
        models = list(result.scalars().all())

        results = []
        for model in models:
            health_result = await self.quick_check(model.id)
            results.append(health_result)

            # 记录到数据库
            await self._record_health_log(health_result)

        await self.db.commit()

        logger.info("health_check_completed", models=len(models), results=len(results))
        return results

    async def _get_model(self, model_id: str) -> ModelInstance | None:
        """获取模型实例"""
        result = await self.db.execute(
            select(ModelInstance).where(ModelInstance.id == model_id)
        )
        return result.scalar_one_or_none()

    async def _ping_local(self, model: ModelInstance) -> None:
        """探测本地模型"""
        import httpx

        api_base = model.config.get("api_base") or "http://localhost:8000/v1"
        timeout = model.config.get("timeout", 5)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{api_base}/health")
            response.raise_for_status()

    async def _ping_cloud(self, model: ModelInstance) -> None:
        """探测云端模型"""
        import httpx

        api_base = model.config.get("api_base") or "https://api.openai.com/v1"
        api_key = await self._get_api_key(model.api_key_id)

        headers = {"Authorization": f"Bearer {api_key}"}

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{api_base}/models",
                headers=headers,
            )
            response.raise_for_status()

    async def _call_model_test(self, model: ModelInstance) -> bool:
        """调用模型测试请求"""
        from app.llm.base import Message
        from app.services.llm_manager import LLMManager

        llm_manager = LLMManager.get_instance()

        try:
            llm = await llm_manager.get_llm(model.id)
            response = await llm.chat(
                messages=[Message(role="user", content="Hi")],
                system_prompt=None,
            )
            return bool(response.content)
        except Exception:
            return False

    async def _get_api_key(self, api_key_id: str | None) -> str:
        """获取 API Key"""
        if not api_key_id:
            return ""

        from app.services.api_key_service import ApiKeyService

        service = ApiKeyService(self.db)
        return await service.get_decrypted_key(api_key_id)

    async def _record_health_log(self, result: HealthCheckResult) -> None:
        """记录健康检查日志"""
        from app.models.health_log import ModelHealthLog

        log = ModelHealthLog(
            model_id=result.model_id,
            check_type=result.check_type.value,
            status=result.status.value,
            latency_ms=result.latency_ms,
            error_message=result.error_message,
        )
        self.db.add(log)

    def start_scheduler(self) -> None:
        """启动定时任务调度器"""
        if self.scheduler:
            return

        self.scheduler = AsyncIOScheduler()

        # 快速探测：每 30 秒
        self.scheduler.add_job(
            self._scheduled_quick_check,
            trigger=IntervalTrigger(seconds=30),
            id="quick_health_check",
            replace_existing=True,
        )

        # 完整探测：每 5 分钟
        self.scheduler.add_job(
            self._scheduled_full_check,
            trigger=IntervalTrigger(minutes=5),
            id="full_health_check",
            replace_existing=True,
        )

        self.scheduler.start()
        self._running = True
        logger.info("health_check_scheduler_started")

    def stop_scheduler(self) -> None:
        """停止定时任务调度器"""
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None
            self._running = False
            logger.info("health_check_scheduler_stopped")

    async def _scheduled_quick_check(self) -> None:
        """定时快速检查"""
        try:
            await self.check_all_models()
        except Exception as e:
            logger.error("scheduled_quick_check_failed", error=str(e))

    async def _scheduled_full_check(self) -> None:
        """定时完整检查"""
        try:
            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                service = HealthCheckService(db)
                result = await self.db.execute(
                    select(ModelInstance).where(
                        ModelInstance.status == ModelStatus.ACTIVE
                    )
                )
                models = list(result.scalars().all())

                for model in models:
                    health_result = await self.full_check(model.id)
                    await service._record_health_log(health_result)

                await db.commit()

        except Exception as e:
            logger.error("scheduled_full_check_failed", error=str(e))
