from __future__ import annotations

import time
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ServiceUnavailableError
from app.models.router import (
    Complexity,
    RouterLog,
    RouterPolicy,
    RouterRule,
    RoutingStrategy,
)
from app.services.circuit_breaker_service import CircuitBreakerService

logger = structlog.get_logger(__name__)


# 复杂度判断关键词
COMPLEXITY_KEYWORDS = {
    "complex": [
        "代码",
        "python",
        "javascript",
        "算法",
        "数学",
        "分析",
        "计算",
        "分析报告",
        "代码实现",
    ],
    "medium": ["解释", "比较", "对比", "说明", "介绍", "总结", "概括"],
}


class RouterService:
    """智能路由服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.circuit_breaker = CircuitBreakerService(db)

    async def route(
        self,
        question: str,
        session_id: str,
        user_id: str | None = None,
        strategy: str | None = None,
    ) -> dict[str, Any]:
        """
        路由请求到合适的模型

        补充设计 S2: 优先使用活跃版本

        Args:
            question: 用户问题
            session_id: 会话ID
            user_id: 用户ID
            strategy: 路由策略

        Returns:
            路由结果
        """
        start_time = time.time()
        complexity = self._classify_complexity(question)

        # 获取路由策略
        policy = await self._get_policy(strategy)
        strategy_type = policy.strategy if policy else RoutingStrategy.BALANCED

        # 根据策略和复杂度选择模型
        rules = await self._get_matching_rules(complexity, strategy_type)

        if not rules:
            raise ServiceUnavailableError("没有可用的路由规则")

        # 按优先级排序
        rules.sort(key=lambda r: r.priority)

        # 选择第一个可用模型
        selected_rule = None
        is_fallback = False

        for rule in rules:
            if not rule.is_active:
                continue

            # 检查熔断状态
            if rule.target_model_id:
                is_available = await self.circuit_breaker.check_availability(
                    rule.target_model_id
                )
                if not is_available:
                    continue

            selected_rule = rule
            break

        if not selected_rule:
            # 使用降级策略
            is_fallback = True
            selected_rule = await self._get_fallback_rule(policy)
            if not selected_rule:
                raise ServiceUnavailableError("所有模型均不可用")

        latency_ms = int((time.time() - start_time) * 1000)

        # 记录路由日志
        await self._log_routing(
            session_id=session_id,
            user_id=user_id,
            question_preview=question[:100],
            complexity=complexity,
            routed_model_id=selected_rule.target_model_id,
            routing_reason=self._build_reason(selected_rule, complexity, strategy_type),
            latency_ms=latency_ms,
            is_fallback=is_fallback,
        )

        return {
            "model_id": selected_rule.target_model_id,
            "version_id": selected_rule.version_id,
            "config_override": selected_rule.config_override,
            "complexity": complexity,
            "routing_reason": self._build_reason(
                selected_rule, complexity, strategy_type
            ),
            "is_fallback": is_fallback,
        }

    def _classify_complexity(self, question: str) -> str:
        """
        判断问题复杂度

        判断维度:
        1. Token 长度
        2. 关键词检测
        3. 历史上下文（需要外部传入）
        """
        # 检查复杂度关键词
        for keyword in COMPLEXITY_KEYWORDS["complex"]:
            if keyword in question:
                return Complexity.COMPLEX

        for keyword in COMPLEXITY_KEYWORDS["medium"]:
            if keyword in question:
                return Complexity.MEDIUM

        # 检查长度
        token_estimate = len(question) // 4  # 粗略估算
        if token_estimate > 500:
            return Complexity.COMPLEX
        elif token_estimate > 200:
            return Complexity.MEDIUM

        return Complexity.SIMPLE

    async def _get_policy(self, strategy: str | None) -> RouterPolicy | None:
        """获取路由策略"""
        if strategy:
            result = await self.db.execute(
                select(RouterPolicy).where(RouterPolicy.strategy == strategy)
            )
        else:
            result = await self.db.execute(
                select(RouterPolicy).where(RouterPolicy.is_default.is_(True))
            )

        return result.scalar_one_or_none()

    async def _get_matching_rules(
        self,
        complexity: str,
        strategy: str,
    ) -> list[RouterRule]:
        """获取匹配的路由规则"""
        result = await self.db.execute(
            select(RouterRule)
            .where(
                RouterRule.complexity == complexity,
                RouterRule.is_active.is_(True),
            )
            .order_by(RouterRule.priority)
        )
        return list(result.scalars().all())

    async def _get_fallback_rule(
        self, policy: RouterPolicy | None
    ) -> RouterRule | None:
        """获取降级规则"""
        fallback_model_id = None

        if policy and policy.fallback_model_id:
            fallback_model_id = policy.fallback_model_id
        else:
            # 获取默认模型
            result = await self.db.execute(
                select(RouterRule)
                .where(RouterRule.is_active.is_(True))
                .order_by(RouterRule.priority.desc())
                .limit(1)
            )
            rule = result.scalar_one_or_none()
            if rule:
                fallback_model_id = rule.target_model_id

        if fallback_model_id:
            result = await self.db.execute(
                select(RouterRule).where(
                    RouterRule.target_model_id == fallback_model_id
                )
            )
            return result.scalar_one_or_none()

        return None

    async def _log_routing(
        self,
        session_id: str,
        user_id: str | None,
        question_preview: str | None,
        complexity: str,
        routed_model_id: str,
        routing_reason: str,
        latency_ms: int,
        is_fallback: bool,
    ) -> None:
        """记录路由日志"""
        log = RouterLog(
            session_id=session_id,
            user_id=user_id,
            question_preview=question_preview,
            complexity=complexity,
            routed_model_id=routed_model_id,
            routing_reason=routing_reason,
            latency_ms=latency_ms,
            is_fallback=is_fallback,
        )
        self.db.add(log)
        await self.db.commit()

    def _build_reason(self, rule: RouterRule, complexity: str, strategy: str) -> str:
        """构建路由原因"""
        reasons = []
        reasons.append(f"复杂度: {complexity}")
        reasons.append(f"规则: {rule.name}")
        reasons.append(f"策略: {strategy}")
        return ", ".join(reasons)

    async def create_rule(
        self,
        name: str,
        complexity: str,
        target_model_id: str,
        conditions: dict[str, Any],
        priority: int = 100,
        version_id: str | None = None,
        config_override: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> RouterRule:
        """创建路由规则"""
        rule = RouterRule(
            name=name,
            complexity=complexity,
            priority=priority,
            target_model_id=target_model_id,
            version_id=version_id,
            config_override=config_override,
            conditions=conditions,
            created_by=user_id,
        )

        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)

        logger.info("router_rule_created", rule_id=rule.id, name=name)
        return rule

    async def preview_route(
        self,
        question: str,
        strategy: str | None = None,
    ) -> dict[str, Any]:
        """预览路由结果"""
        complexity = self._classify_complexity(question)

        return {
            "question_preview": question[:100],
            "estimated_complexity": complexity,
            "recommended_strategy": self._recommend_strategy(complexity),
            "keywords_detected": self._detect_keywords(question),
        }

    def _detect_keywords(self, question: str) -> list[str]:
        """检测问题中的关键词"""
        detected = []
        for level, keywords in COMPLEXITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in question:
                    detected.append(f"{level}:{keyword}")
        return detected

    def _recommend_strategy(self, complexity: str) -> str:
        """推荐路由策略"""
        if complexity == Complexity.COMPLEX:
            return RoutingStrategy.QUALITY_FIRST
        elif complexity == Complexity.SIMPLE:
            return RoutingStrategy.COST_FIRST
        else:
            return RoutingStrategy.BALANCED
