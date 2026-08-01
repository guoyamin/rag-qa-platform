from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.ab_test import ABExperiment, ABGroup, ABResult, ExperimentStatus
from app.services.circuit_breaker_service import CircuitBreakerService
from app.services.llm_manager import LLMManager

logger = structlog.get_logger(__name__)


class ABTestService:
    """A/B 测试服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.circuit_breaker = CircuitBreakerService(db)
        self.llm_manager = LLMManager.get_instance()

    async def create_experiment(
        self,
        name: str,
        experiment_type: str,
        description: str | None = None,
        target_model_id: str | None = None,
        user_id: str | None = None,
    ) -> ABExperiment:
        """创建实验"""
        experiment = ABExperiment(
            name=name,
            description=description,
            experiment_type=experiment_type,
            target_model_id=target_model_id,
            status=ExperimentStatus.DRAFT,
            created_by=user_id,
        )

        self.db.add(experiment)
        await self.db.commit()
        await self.db.refresh(experiment)

        logger.info("ab_experiment_created", experiment_id=experiment.id, name=name)
        return experiment

    async def add_group(
        self,
        experiment_id: str,
        name: str,
        model_id: str | None = None,
        config_snapshot: dict[str, Any] | None = None,
        traffic_percentage: int = 50,
    ) -> ABGroup:
        """添加分组"""
        # 验证实验存在且为草稿状态
        experiment = await self.get_experiment(experiment_id)
        if experiment.status != ExperimentStatus.DRAFT:
            raise ValidationError("只能向草稿状态的实验添加分组")

        group = ABGroup(
            experiment_id=experiment_id,
            name=name,
            model_id=model_id,
            config_snapshot=config_snapshot,
            traffic_percentage=traffic_percentage,
        )

        self.db.add(group)
        await self.db.commit()
        await self.db.refresh(group)

        return group

    async def start_experiment(self, experiment_id: str) -> ABExperiment:
        """启动实验"""
        experiment = await self.get_experiment(experiment_id)

        if experiment.status not in (ExperimentStatus.DRAFT, ExperimentStatus.PAUSED):
            raise ValidationError("只能启动草稿或暂停状态的实验")

        # 检查分组
        groups = await self.list_groups(experiment_id)
        if len(groups) < 2:
            raise ValidationError("实验至少需要2个分组")

        experiment.status = ExperimentStatus.RUNNING
        experiment.start_at = datetime.now()

        await self.db.commit()
        await self.db.refresh(experiment)

        logger.info("ab_experiment_started", experiment_id=experiment_id)
        return experiment

    async def pause_experiment(self, experiment_id: str) -> ABExperiment:
        """暂停实验"""
        experiment = await self.get_experiment(experiment_id)

        if experiment.status != ExperimentStatus.RUNNING:
            raise ValidationError("只能暂停运行中的实验")

        experiment.status = ExperimentStatus.PAUSED

        await self.db.commit()
        await self.db.refresh(experiment)

        return experiment

    async def complete_experiment(
        self,
        experiment_id: str,
        winner_group_id: str,
        conclusion: str | None = None,
    ) -> ABExperiment:
        """完成实验，指定获胜分组"""
        experiment = await self.get_experiment(experiment_id)

        if experiment.status != ExperimentStatus.RUNNING:
            raise ValidationError("只能完成运行中的实验")

        # 验证获胜分组存在
        winner = await self.get_group(winner_group_id)
        if winner.experiment_id != experiment_id:
            raise ValidationError("获胜分组不属于该实验")

        experiment.status = ExperimentStatus.COMPLETED
        experiment.end_at = datetime.now()
        experiment.winner_group_id = winner_group_id
        experiment.conclusion = conclusion

        await self.db.commit()
        await self.db.refresh(experiment)

        # 补充设计 S1: 采纳获胜版本后刷新 LLMManager 缓存
        if winner.model_id:
            await self.llm_manager.reload_llm(winner.model_id)

        logger.info(
            "ab_experiment_completed",
            experiment_id=experiment_id,
            winner_group_id=winner_group_id,
        )
        return experiment

    async def record_result(
        self,
        experiment_id: str,
        group_id: str,
        session_id: str,
        question: str,
        answer: str | None = None,
        model_id: str | None = None,
        latency_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        success: bool = True,
        user_id: str | None = None,
    ) -> ABResult:
        """记录实验结果"""
        result = ABResult(
            experiment_id=experiment_id,
            group_id=group_id,
            session_id=session_id,
            user_id=user_id,
            question=question,
            answer=answer,
            model_id=model_id,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            is_success=success,
        )

        self.db.add(result)
        await self.db.commit()
        await self.db.refresh(result)

        return result

    async def get_analysis(self, experiment_id: str) -> dict[str, Any]:
        """获取实验分析报告"""
        experiment = await self.get_experiment(experiment_id)

        # 统计每个分组的结果
        groups = await self.list_groups(experiment_id)
        analysis: dict[str, Any] = {
            "experiment_id": experiment_id,
            "name": experiment.name,
            "status": experiment.status,
            "groups": [],
        }

        for group in groups:
            # 查询该分组的结果
            result = await self.db.execute(
                select(
                    func.count(ABResult.id).label("total"),
                    func.avg(ABResult.latency_ms).label("avg_latency"),
                    func.avg(ABResult.input_tokens).label("avg_input_tokens"),
                    func.avg(ABResult.output_tokens).label("avg_output_tokens"),
                    func.sum(func.cast(ABResult.is_success, Integer)).label(
                        "success_count"
                    ),
                    func.avg(ABResult.feedback_score).label("avg_feedback"),
                ).where(ABResult.group_id == group.id)
            )
            stats = result.one()

            group_analysis = {
                "group_id": group.id,
                "name": group.name,
                "model_id": group.model_id,
                "total_requests": stats.total or 0,
                "success_rate": (
                    stats.success_count / stats.total * 100
                    if stats.total and stats.total > 0
                    else 0
                ),
                "avg_latency_ms": int(stats.avg_latency or 0),
                "avg_input_tokens": int(stats.avg_input_tokens or 0),
                "avg_output_tokens": int(stats.avg_output_tokens or 0),
                "avg_feedback": (
                    float(stats.avg_feedback or 0) if stats.avg_feedback else None
                ),
            }

            analysis["groups"].append(group_analysis)

        return analysis

    async def route_request(
        self,
        experiment_id: str,
        session_id: str,
    ) -> tuple[ABGroup | None, bool]:
        """
        分流请求到实验分组

        补充设计 S3: 检查熔断状态

        Returns:
            (分组, 是否可用) 元组
        """
        experiment = await self.get_experiment(experiment_id)

        if experiment.status != ExperimentStatus.RUNNING:
            return None, False

        groups = await self.list_groups(experiment_id)

        # 补充设计 S3: 过滤熔断分组
        available_groups = []
        total_traffic = 0

        for group in groups:
            if not group.skip_on_circuit_open:
                available_groups.append((group, group.traffic_percentage))
                total_traffic += group.traffic_percentage
                continue

            # 检查熔断状态
            if group.model_id:
                is_available = await self.circuit_breaker.check_availability(
                    group.model_id
                )
                if is_available:
                    available_groups.append((group, group.traffic_percentage))
                    total_traffic += group.traffic_percentage
            else:
                available_groups.append((group, group.traffic_percentage))
                total_traffic += group.traffic_percentage

        if not available_groups:
            return None, False

        # 按流量比例分流
        hash_value = int(
            hashlib.md5(
                f"{session_id}{experiment_id}".encode(), usedforsecurity=False
            ).hexdigest(),
            16,
        )
        position = (hash_value % total_traffic) + 1

        cumulative = 0
        for group, traffic in available_groups:
            cumulative += traffic
            if position <= cumulative:
                return group, True

        return available_groups[0][0], True

    async def get_experiment(self, experiment_id: str) -> ABExperiment:
        """获取实验"""
        result = await self.db.execute(
            select(ABExperiment).where(ABExperiment.id == experiment_id)
        )
        experiment = result.scalar_one_or_none()
        if not experiment:
            raise NotFoundError("实验不存在")
        return experiment

    async def list_experiments(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ABExperiment], int]:
        """列出实验"""
        query = select(ABExperiment)

        if status:
            query = query.where(ABExperiment.status == status)

        # 统计
        count_result = await self.db.execute(
            select(func.count(ABExperiment.id)).select_from(ABExperiment)
        )
        total = count_result.scalar() or 0

        # 分页
        query = query.order_by(ABExperiment.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_group(self, group_id: str) -> ABGroup:
        """获取分组"""
        result = await self.db.execute(select(ABGroup).where(ABGroup.id == group_id))
        group = result.scalar_one_or_none()
        if not group:
            raise NotFoundError("分组不存在")
        return group

    async def list_groups(self, experiment_id: str) -> list[ABGroup]:
        """列出实验的所有分组"""
        result = await self.db.execute(
            select(ABGroup)
            .where(ABGroup.experiment_id == experiment_id)
            .order_by(ABGroup.created_at)
        )
        return list(result.scalars().all())
