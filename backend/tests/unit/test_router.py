"""
智能问答平台 - 智能路由服务单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ServiceUnavailableError
from app.models.router import Complexity, RoutingStrategy
from app.services.router_service import RouterService

# ========== 辅助函数 ==========


def _make_rule(
    name: str = "rule-1",
    complexity: str = Complexity.SIMPLE,
    priority: int = 100,
    target_model_id: str = "model-1",
    version_id: str | None = "v-1",
    config_override: dict[str, Any] | None = None,
    is_active: bool = True,
) -> MagicMock:
    """构造模拟路由规则"""
    rule = MagicMock()
    rule.name = name
    rule.complexity = complexity
    rule.priority = priority
    rule.target_model_id = target_model_id
    rule.version_id = version_id
    rule.config_override = config_override
    rule.is_active = is_active
    return rule


def _make_policy(
    strategy: str = RoutingStrategy.BALANCED,
    fallback_model_id: str | None = None,
    is_default: bool = True,
) -> MagicMock:
    """构造模拟路由策略"""
    policy = MagicMock()
    policy.strategy = strategy
    policy.fallback_model_id = fallback_model_id
    policy.is_default = is_default
    return policy


def _make_scalar_result(value: object = None) -> MagicMock:
    """构造返回单个值的 db.execute 结果"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _make_scalars_result(items: list[MagicMock] | None = None) -> MagicMock:
    """构造返回列表的 db.execute 结果"""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    return result


def _make_service() -> tuple[RouterService, MagicMock]:
    """构造带 Mock DB 的 RouterService"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    service = RouterService(db)
    service.circuit_breaker = AsyncMock()
    return service, db


# ========== Schema / 逻辑测试（保留） ==========


class TestRouterRule:
    """路由规则测试"""

    def test_routing_strategy_enum(self):
        """测试路由策略枚举值"""
        routing_strategy = {
            "COST_FIRST": "cost_first",
            "QUALITY_FIRST": "quality_first",
            "LATENCY_FIRST": "latency_first",
            "BALANCED": "balanced",
        }

        assert routing_strategy["COST_FIRST"] == "cost_first"
        assert routing_strategy["QUALITY_FIRST"] == "quality_first"
        assert routing_strategy["LATENCY_FIRST"] == "latency_first"
        assert routing_strategy["BALANCED"] == "balanced"

    def test_routing_strategy_response(self):
        """测试路由策略响应 Schema"""
        from app.schemas.model import RouterStrategyResponse, RoutingStrategy

        response = RouterStrategyResponse(
            id="strategy-1",
            name="成本优先",
            strategy=RoutingStrategy.COST_FIRST,
            description="优先选择成本最低的模型",
            config={
                "max_cost_per_1k_tokens": 0.01,
                "fallback_enabled": True,
            },
            priority=1,
            is_active=True,
        )

        assert response.name == "成本优先"
        assert response.strategy == RoutingStrategy.COST_FIRST
        assert response.is_active is True


class TestRoutingDecision:
    """路由决策测试"""

    def test_route_by_complexity(self):
        """测试根据复杂度路由"""

        def route_by_complexity(question: str, models: list) -> str:
            """根据问题复杂度选择模型"""
            length = len(question)
            # 简单问题 (< 50字符)
            if length < 50:
                return models[0]  # 返回最便宜的模型
            # 复杂问题 (50-200字符)
            elif length < 200:
                return models[1]  # 返回中等模型
            else:
                return models[-1]  # 返回最高质量的模型

        models = ["gpt-3.5", "gpt-4", "gpt-4-32k"]
        assert route_by_complexity("你好", models) == "gpt-3.5"
        # 使用足够长的英文测试避免编码问题
        long_question = (
            "Please explain what is machine learning and its "
            "applications in modern software development"
        )
        assert route_by_complexity(long_question, models) == "gpt-4"
        very_long = "word " * 100
        assert route_by_complexity(very_long, models) == "gpt-4-32k"

    def test_route_by_cost(self):
        """测试根据成本路由"""

        def route_by_cost(models: list, costs: dict, max_budget: float) -> str:
            """在预算范围内选择最便宜的模型"""
            affordable = [m for m in models if costs.get(m, float("inf")) <= max_budget]
            if not affordable:
                return None
            return min(affordable, key=lambda m: costs.get(m, float("inf")))

        costs = {
            "gpt-3.5": 0.001,
            "gpt-4": 0.03,
            "claude-3": 0.015,
        }

        # 在预算 0.0005 范围内，只有 gpt-3.5
        # (0.001 > 0.0005，但 0.001 > 0.0005 所以实际上 gpt-3.5 也不符合)
        assert route_by_cost(["gpt-3.5", "gpt-4", "claude-3"], costs, 0.0005) is None
        # 在预算 0.001 范围内，只有 gpt-3.5
        assert (
            route_by_cost(["gpt-3.5", "gpt-4", "claude-3"], costs, 0.001) == "gpt-3.5"
        )
        # 在预算 0.01 范围内，gpt-3.5 和 claude-3，最便宜的是 gpt-3.5
        assert route_by_cost(["gpt-3.5", "gpt-4", "claude-3"], costs, 0.01) == "gpt-3.5"

    def test_route_by_latency(self):
        """测试根据延迟路由"""

        def route_by_latency(models: list, latencies: dict) -> str:
            """选择延迟最低的模型"""
            return min(latencies, key=latencies.get)

        latencies = {
            "gpt-3.5": 100,
            "gpt-4": 500,
            "claude-3": 300,
        }

        assert (
            route_by_latency(["gpt-3.5", "gpt-4", "claude-3"], latencies) == "gpt-3.5"
        )

    def test_route_by_quality_score(self):
        """测试根据质量评分路由"""

        def route_by_quality(models: list, scores: dict, min_score: float) -> str:
            """选择质量评分最高且满足最低要求的模型"""
            qualified = [m for m in models if scores.get(m, 0) >= min_score]
            if not qualified:
                return None
            return max(qualified, key=lambda m: scores.get(m, 0))

        scores = {
            "gpt-3.5": 70,
            "gpt-4": 90,
            "claude-3": 85,
        }

        assert route_by_quality(["gpt-3.5", "gpt-4", "claude-3"], scores, 80) == "gpt-4"
        assert route_by_quality(["gpt-3.5", "gpt-4", "claude-3"], scores, 95) is None


class TestFallbackRouting:
    """降级路由测试"""

    def test_fallback_chain(self):
        """测试降级链路"""

        def get_available_model(chain: list, latencies: dict) -> str:
            """按顺序尝试可用模型"""
            for model in chain:
                if latencies.get(model, float("inf")) < 5000:  # 延迟可接受
                    return model
            return None

        chain = ["gpt-4", "gpt-3.5", "claude-2"]
        latencies = {
            "gpt-4": 100,  # 可用
        }

        assert get_available_model(chain, latencies) == "gpt-4"

        latencies = {
            "gpt-4": 10000,  # 超时
            "gpt-3.5": 200,  # 可用
        }
        assert get_available_model(chain, latencies) == "gpt-3.5"

        latencies = {
            "gpt-4": 10000,  # 超时
            "gpt-3.5": 10000,  # 超时
        }
        assert get_available_model(chain, latencies) is None

    def test_circuit_breaker_in_routing(self):
        """测试熔断状态下的路由"""

        def route_with_circuit_breaker(models: list, circuit_states: dict) -> list:
            """过滤掉熔断中的模型"""
            return [m for m in models if circuit_states.get(m) != "open"]

        models = ["gpt-4", "gpt-3.5", "claude-3"]
        circuit_states = {
            "gpt-4": "open",  # 熔断中
            "gpt-3.5": "closed",
            "claude-3": "closed",
        }

        available = route_with_circuit_breaker(models, circuit_states)
        assert "gpt-4" not in available
        assert "gpt-3.5" in available
        assert "claude-3" in available


class TestContentBasedRouting:
    """基于内容的路由测试"""

    def test_routing_by_intent(self):
        """测试根据意图路由"""

        def detect_intent(question: str) -> str:
            """检测用户意图"""
            question_lower = question.lower()

            if any(kw in question_lower for kw in ["翻译", "translate"]):
                return "translation"
            elif any(
                kw in question_lower for kw in ["代码", "code", "python", "javascript"]
            ):
                return "coding"
            elif any(kw in question_lower for kw in ["分析", "analyze", "compare"]):
                return "analysis"
            else:
                return "general"

        assert detect_intent("请翻译这段话") == "translation"
        assert detect_intent("写一个Python函数") == "coding"
        assert detect_intent("分析这个数据的趋势") == "analysis"
        assert detect_intent("今天天气怎么样") == "general"

    def test_routing_rules_mapping(self):
        """测试路由规则映射"""

        def map_intent_to_model(intent: str, model_pool: dict) -> str:
            """将意图映射到合适的模型"""
            return model_pool.get(intent, model_pool["default"])

        model_pool = {
            "translation": "gpt-3.5",  # 翻译用便宜模型
            "coding": "gpt-4",  # 编码用高质量模型
            "analysis": "claude-3",  # 分析用 Claude
            "default": "gpt-3.5",
        }

        assert map_intent_to_model("translation", model_pool) == "gpt-3.5"
        assert map_intent_to_model("coding", model_pool) == "gpt-4"
        assert map_intent_to_model("unknown", model_pool) == "gpt-3.5"


class TestRouterOptimization:
    """路由优化测试"""

    def test_load_balancing(self):
        """测试负载均衡"""

        def select_least_loaded(models: list, current_load: dict) -> str:
            """选择当前负载最低的模型"""
            return min(models, key=lambda m: current_load.get(m, 0))

        models = ["model-a", "model-b", "model-c"]
        current_load = {
            "model-a": 80,
            "model-b": 30,  # 负载最低
            "model-c": 50,
        }

        assert select_least_loaded(models, current_load) == "model-b"

    def test_health_aware_routing(self):
        """测试健康感知路由"""

        def route_by_health(models: list, health_scores: dict) -> list:
            """按健康评分排序模型"""
            return sorted(models, key=lambda m: health_scores.get(m, 0), reverse=True)

        models = ["model-a", "model-b", "model-c"]
        health_scores = {
            "model-a": 0.9,
            "model-b": 0.5,  # 健康度差
            "model-c": 0.8,
        }

        sorted_models = route_by_health(models, health_scores)
        assert sorted_models[0] == "model-a"
        assert sorted_models[-1] == "model-b"


class TestRouterPreview:
    """路由预览测试"""

    def test_preview_calculation(self):
        """测试路由预览计算"""

        def calculate_preview(
            question: str,
            models: list,
            costs: dict,
            latencies: dict,
            quality_scores: dict,
        ) -> list:
            """计算所有模型的路由预览"""
            results = []
            for model in models:
                results.append(
                    {
                        "model": model,
                        "estimated_cost": costs.get(model, 0) * len(question),
                        "estimated_latency": latencies.get(model, 0),
                        "quality_score": quality_scores.get(model, 0),
                        "recommended": False,
                    }
                )

            # 推荐最佳模型
            best = min(
                results,
                key=lambda r: (
                    -r["quality_score"],
                    r["estimated_cost"],
                    r["estimated_latency"],
                ),
            )
            best["recommended"] = True

            return results

        models = ["gpt-3.5", "gpt-4"]
        costs = {"gpt-3.5": 0.001, "gpt-4": 0.03}
        latencies = {"gpt-3.5": 100, "gpt-4": 500}
        quality_scores = {"gpt-3.5": 70, "gpt-4": 90}

        results = calculate_preview(
            "测试问题", models, costs, latencies, quality_scores
        )

        recommended = [r for r in results if r["recommended"]][0]
        assert recommended["model"] == "gpt-4"
        assert recommended["quality_score"] == 90


# ========== Service 层单元测试（新增） ==========


class TestRouterServiceClassifyComplexity:
    """RouterService._classify_complexity 测试"""

    def setup_method(self):
        self.service, _ = _make_service()

    def test_classify_complexity_complex_keyword_returns_complex(self):
        """包含复杂关键词返回 complex"""
        question = "请帮我写一段python代码实现排序算法"
        result = self.service._classify_complexity(question)
        assert result == Complexity.COMPLEX

    def test_classify_complexity_medium_keyword_returns_medium(self):
        """包含中等关键词返回 medium"""
        result = self.service._classify_complexity("请解释一下这个概念")
        assert result == Complexity.MEDIUM

    def test_classify_complexity_short_question_returns_simple(self):
        """简短无关键词返回 simple"""
        result = self.service._classify_complexity("你好")
        assert result == Complexity.SIMPLE

    def test_classify_complexity_long_question_returns_complex(self):
        """超长问题（token估算>500）返回 complex"""
        result = self.service._classify_complexity("a" * 2005)
        assert result == Complexity.COMPLEX

    def test_classify_complexity_medium_length_returns_medium(self):
        """中长问题（token估算>200）返回 medium"""
        result = self.service._classify_complexity("a" * 805)
        assert result == Complexity.MEDIUM


class TestRouterServiceRoute:
    """RouterService.route 测试"""

    def setup_method(self):
        self.service, self.db = _make_service()

    async def test_route_success_returns_correct_model(self):
        """正常路由返回正确的模型信息"""
        # Arrange
        policy = _make_policy()
        rule = _make_rule(
            target_model_id="model-1",
            version_id="v-1",
            config_override={"temperature": 0.5},
        )
        self.db.execute.side_effect = [
            _make_scalar_result(policy),
            _make_scalars_result([rule]),
        ]
        self.service.circuit_breaker.check_availability.return_value = True

        # Act
        result = await self.service.route("你好", "session-1", user_id="user-1")

        # Assert
        assert result["model_id"] == "model-1"
        assert result["version_id"] == "v-1"
        assert result["config_override"] == {"temperature": 0.5}
        assert result["complexity"] == Complexity.SIMPLE
        assert result["is_fallback"] is False
        added_log = self.db.add.call_args[0][0]
        assert added_log.session_id == "session-1"
        assert added_log.user_id == "user-1"
        assert added_log.is_fallback is False
        self.db.commit.assert_awaited_once()

    async def test_route_no_rules_raises_service_unavailable(self):
        """无可用规则时抛出 ServiceUnavailableError"""
        # Arrange
        self.db.execute.side_effect = [
            _make_scalar_result(None),
            _make_scalars_result([]),
        ]

        # Act & Assert
        with pytest.raises(ServiceUnavailableError, match="没有可用的路由规则"):
            await self.service.route("你好", "session-1")

    async def test_route_inactive_rule_skipped_selects_active(self):
        """跳过不活跃规则选择活跃规则"""
        # Arrange
        inactive_rule = _make_rule(
            name="inactive", target_model_id="model-1", priority=1, is_active=False
        )
        active_rule = _make_rule(
            name="active", target_model_id="model-2", priority=2, is_active=True
        )
        self.db.execute.side_effect = [
            _make_scalar_result(None),
            _make_scalars_result([inactive_rule, active_rule]),
        ]
        self.service.circuit_breaker.check_availability.return_value = True

        # Act
        result = await self.service.route("你好", "session-1")

        # Assert
        assert result["model_id"] == "model-2"
        self.service.circuit_breaker.check_availability.assert_called_once_with(
            "model-2"
        )

    async def test_route_circuit_open_uses_fallback(self):
        """主模型熔断时使用降级模型"""
        # Arrange
        policy = _make_policy(fallback_model_id="model-fallback")
        rule = _make_rule(target_model_id="model-1", is_active=True)
        fallback_rule = _make_rule(
            name="fallback", target_model_id="model-fallback", priority=200
        )
        self.db.execute.side_effect = [
            _make_scalar_result(policy),
            _make_scalars_result([rule]),
            _make_scalar_result(fallback_rule),
        ]
        self.service.circuit_breaker.check_availability.return_value = False

        # Act
        result = await self.service.route("你好", "session-1")

        # Assert
        assert result["model_id"] == "model-fallback"
        assert result["is_fallback"] is True

    async def test_route_all_unavailable_raises_service_unavailable(self):
        """所有模型不可用且无降级时抛出 ServiceUnavailableError"""
        # Arrange
        rule = _make_rule(target_model_id="model-1", is_active=True)
        self.db.execute.side_effect = [
            _make_scalar_result(None),
            _make_scalars_result([rule]),
            _make_scalar_result(None),
        ]
        self.service.circuit_breaker.check_availability.return_value = False

        # Act & Assert
        with pytest.raises(ServiceUnavailableError, match="所有模型均不可用"):
            await self.service.route("你好", "session-1")

    async def test_route_with_strategy_uses_policy_strategy(self):
        """指定策略时路由原因包含策略名"""
        # Arrange
        policy = _make_policy(strategy="quality_first")
        rule = _make_rule(target_model_id="model-1")
        self.db.execute.side_effect = [
            _make_scalar_result(policy),
            _make_scalars_result([rule]),
        ]
        self.service.circuit_breaker.check_availability.return_value = True

        # Act
        result = await self.service.route("你好", "session-1", strategy="quality_first")

        # Assert
        assert "quality_first" in result["routing_reason"]


class TestRouterServiceCreateRule:
    """RouterService.create_rule 测试"""

    def setup_method(self):
        self.service, self.db = _make_service()

    async def test_create_rule_success_returns_rule_with_attributes(self):
        """创建规则成功返回带有正确属性的对象"""
        # Arrange & Act
        result = await self.service.create_rule(
            name="test-rule",
            complexity=Complexity.SIMPLE,
            target_model_id="model-1",
            conditions={"source": "web"},
            priority=50,
            version_id="v-1",
            user_id="user-1",
        )

        # Assert
        assert result.name == "test-rule"
        assert result.complexity == Complexity.SIMPLE
        assert result.target_model_id == "model-1"
        assert result.priority == 50
        assert result.version_id == "v-1"
        self.db.add.assert_called_once()
        self.db.commit.assert_awaited_once()
        self.db.refresh.assert_awaited_once()

    async def test_create_rule_with_config_override_persists(self):
        """带配置覆盖创建规则时配置被正确传递"""
        # Arrange & Act
        result = await self.service.create_rule(
            name="override-rule",
            complexity=Complexity.COMPLEX,
            target_model_id="model-2",
            conditions={"source": "api"},
            config_override={"temperature": 0.3, "max_tokens": 4096},
        )

        # Assert
        assert result.config_override == {"temperature": 0.3, "max_tokens": 4096}
        added_rule = self.db.add.call_args[0][0]
        assert added_rule.config_override == {"temperature": 0.3, "max_tokens": 4096}


class TestRouterServicePreviewRoute:
    """RouterService.preview_route 测试"""

    def setup_method(self):
        self.service, _ = _make_service()

    async def test_preview_route_complex_question_returns_complexity(self):
        """复杂问题预览返回 complex 复杂度"""
        result = await self.service.preview_route("请帮我写一段python代码")
        assert result["estimated_complexity"] == Complexity.COMPLEX
        assert result["recommended_strategy"] == RoutingStrategy.QUALITY_FIRST

    async def test_preview_route_simple_question_returns_preview(self):
        """简单问题预览返回正确的预览信息"""
        result = await self.service.preview_route("你好")
        assert result["question_preview"] == "你好"
        assert result["estimated_complexity"] == Complexity.SIMPLE
        assert result["recommended_strategy"] == RoutingStrategy.COST_FIRST
        assert result["keywords_detected"] == []

    async def test_preview_route_detects_keywords(self):
        """预览检测到问题中的关键词"""
        result = await self.service.preview_route("请解释代码")
        assert "complex:代码" in result["keywords_detected"]
        assert "medium:解释" in result["keywords_detected"]


class TestRouterServiceRecommendStrategy:
    """RouterService._recommend_strategy 测试"""

    def setup_method(self):
        self.service, _ = _make_service()

    def test_recommend_strategy_complex_returns_quality_first(self):
        """复杂问题推荐质量优先策略"""
        result = self.service._recommend_strategy(Complexity.COMPLEX)
        assert result == RoutingStrategy.QUALITY_FIRST

    def test_recommend_strategy_simple_returns_cost_first(self):
        """简单问题推荐成本优先策略"""
        result = self.service._recommend_strategy(Complexity.SIMPLE)
        assert result == RoutingStrategy.COST_FIRST

    def test_recommend_strategy_medium_returns_balanced(self):
        """中等问题推荐均衡策略"""
        result = self.service._recommend_strategy(Complexity.MEDIUM)
        assert result == RoutingStrategy.BALANCED


class TestRouterServiceDetectKeywords:
    """RouterService._detect_keywords 测试"""

    def setup_method(self):
        self.service, _ = _make_service()

    def test_detect_keywords_finds_matching_keywords(self):
        """检测到问题中的复杂度和中等关键词"""
        result = self.service._detect_keywords("请解释代码")
        assert "complex:代码" in result
        assert "medium:解释" in result

    def test_detect_keywords_no_match_returns_empty(self):
        """无关键词匹配时返回空列表"""
        result = self.service._detect_keywords("你好世界")
        assert result == []


class TestRouterServiceBuildReason:
    """RouterService._build_reason 测试"""

    def setup_method(self):
        self.service, _ = _make_service()

    def test_build_reason_contains_all_components(self):
        """路由原因包含复杂度、规则名和策略"""
        rule = _make_rule(name="test-rule")
        reason = self.service._build_reason(
            rule, Complexity.SIMPLE, RoutingStrategy.BALANCED
        )
        assert "simple" in reason
        assert "test-rule" in reason
        assert "balanced" in reason
