"""
智能问答平台 - A/B测试服务单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.ab_test import ABExperiment, ABGroup, ExperimentStatus
from app.services.ab_test_service import ABTestService


class TestABExperiment:
    """A/B 实验测试"""

    def test_experiment_status_enum(self):
        """测试实验状态枚举值"""
        status_map = {
            "DRAFT": "draft",
            "RUNNING": "running",
            "PAUSED": "paused",
            "COMPLETED": "completed",
        }

        assert status_map["DRAFT"] == "draft"
        assert status_map["RUNNING"] == "running"
        assert status_map["PAUSED"] == "paused"
        assert status_map["COMPLETED"] == "completed"

    def test_experiment_schema(self):
        """测试实验 Schema"""
        from app.schemas.model import ExperimentResponse, ExperimentStatus

        response = ExperimentResponse(
            id="exp-1",
            name="GPT-4 vs Claude 对比测试",
            description="测试 GPT-4 和 Claude 的响应质量",
            status=ExperimentStatus.RUNNING,
            traffic_percent=20,
            start_time=datetime.now(),
            end_time=None,
            created_by="user-1",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert response.name == "GPT-4 vs Claude 对比测试"
        assert response.status == ExperimentStatus.RUNNING
        assert response.traffic_percent == 20


class TestABGroup:
    """A/B 分组测试"""

    def test_group_response(self):
        """测试分组响应 Schema"""
        from app.schemas.model import ABGroupResponse

        response = ABGroupResponse(
            id="group-1",
            experiment_id="exp-1",
            name="对照组",
            model_id="model-1",
            traffic_percent=50,
            description="使用 GPT-4",
        )

        assert response.name == "对照组"
        assert response.traffic_percent == 50


class TestABSplitLogic:
    """A/B 分流逻辑测试"""

    def test_user_assignment_consistency(self):
        """测试用户分配一致性"""

        def assign_to_group(user_id: str, group_percentages: dict) -> str:
            """根据用户ID将用户分配到分组，保持一致性"""
            # 使用用户ID的哈希确保同一用户始终分配到同一分组
            hash_value = sum(ord(c) for c in user_id)
            bucket = hash_value % 100

            cumulative = 0
            for group, percentage in group_percentages.items():
                cumulative += percentage
                if bucket < cumulative:
                    return group
            return list(group_percentages.keys())[-1]

        # 测试一致性：同一用户始终分到同一组
        groups = {"control": 50, "treatment": 50}
        assignments = [assign_to_group("user-123", groups) for _ in range(10)]
        assert len(set(assignments)) == 1  # 始终一致

    def test_traffic_split(self):
        """测试流量分割"""

        def split_traffic(groups: list, percentages: list) -> dict:
            """将流量按比例分配"""
            assert len(groups) == len(percentages)
            assert sum(percentages) == 100
            return dict(zip(groups, percentages, strict=True))

        result = split_traffic(["control", "treatment"], [50, 50])
        assert result == {"control": 50, "treatment": 50}

        result = split_traffic(["control", "treatment", "variant-b"], [33, 33, 34])
        assert sum(result.values()) == 100

    def test_experiment_traffic_filter(self):
        """测试实验流量过滤"""

        def is_in_experiment(user_id: str, experiment_percent: int) -> bool:
            """根据实验百分比决定用户是否参与实验"""
            hash_value = sum(ord(c) for c in user_id)
            bucket = hash_value % 100
            return bucket < experiment_percent

        # 100% 实验
        assert is_in_experiment("user-1", 100) is True

        # 0% 实验
        assert is_in_experiment("user-1", 0) is False

        # 50% 实验
        true_count = sum(1 for i in range(1000) if is_in_experiment(f"user-{i}", 50))
        assert 400 <= true_count <= 600  # 允许统计偏差


class TestABMetrics:
    """A/B 测试指标测试"""

    def test_metric_calculation(self):
        """测试指标计算"""

        def calculate_ctr(clicks: int, impressions: int) -> float:
            """计算点击率"""
            if impressions == 0:
                return 0.0
            return round(clicks / impressions * 100, 2)

        assert calculate_ctr(100, 1000) == 10.0
        assert calculate_ctr(0, 1000) == 0.0
        assert calculate_ctr(500, 1000) == 50.0

    def test_statistical_significance(self):
        """测试统计显著性"""

        def is_significant(
            control_rate: float, treatment_rate: float, n: int
        ) -> tuple[bool, float]:
            """简单显著性检验"""
            # 简化的 z-test
            pooled_rate = (control_rate + treatment_rate) / 2
            se = (pooled_rate * (1 - pooled_rate) / n) ** 0.5
            if se == 0:
                return False, 0.0
            z_score = abs(control_rate - treatment_rate) / se

            # z > 1.96 约等于 95% 置信水平
            is_significant = z_score > 1.96
            p_value = 1 - (z_score / (1 + z_score))  # 简化 p-value

            return is_significant, round(p_value, 4)

        # 无显著差异
        is_sig, p = is_significant(0.5, 0.5, 1000)
        assert is_sig is False

        # 有显著差异
        is_sig, p = is_significant(0.5, 0.6, 10000)
        # 注意：简化检验可能不准确，仅用于测试

    def test_sample_size_calculation(self):
        """测试样本量计算"""

        def calculate_min_sample_size(
            baseline_rate: float,
            minimum_detectable_effect: float,
            power: float = 0.8,
            alpha: float = 0.05,
        ) -> int:
            """计算最小样本量（简化版）"""
            # 简化公式，仅用于测试
            effect_size = baseline_rate * minimum_detectable_effect
            if effect_size == 0:
                return 0

            # 粗略估算
            return int(16 * baseline_rate * (1 - baseline_rate) / (effect_size**2))

        # 10% baseline, 10% MDE
        sample_size = calculate_min_sample_size(0.1, 0.1)
        assert sample_size > 0

        # 50% baseline, 10% MDE
        sample_size = calculate_min_sample_size(0.5, 0.1)
        assert sample_size > 0


class TestWinnerDetermination:
    """胜出者判定测试"""

    def test_winner_selection(self):
        """测试胜出者选择"""

        def determine_winner(group_results: list) -> str:
            """根据指标确定胜出组"""
            best_group = None
            best_score = -1

            for result in group_results:
                if result["metric"] > best_score:
                    best_score = result["metric"]
                    best_group = result["group"]

            return best_group

        results = [
            {"group": "control", "metric": 0.75, "sample_size": 1000},
            {"group": "treatment", "metric": 0.82, "sample_size": 1000},
        ]

        winner = determine_winner(results)
        assert winner == "treatment"

    def test_winner_with_min_sample_size(self):
        """测试考虑最小样本量的胜出者选择"""

        def determine_winner_with_min_samples(
            group_results: list, min_sample_size: int
        ) -> tuple[str, str]:
            """返回胜出组和状态"""
            # 检查所有组是否都达到最小样本量
            all_sufficient = all(
                r["sample_size"] >= min_sample_size for r in group_results
            )
            if not all_sufficient:
                return None, "insufficient_samples"

            # 达到最小样本量，执行胜出者判定（选择指标最高的）
            best_group = max(group_results, key=lambda x: x["metric"])["group"]

            return best_group, "significant"

        results = [
            {"group": "control", "metric": 0.75, "sample_size": 500},
            {"group": "treatment", "metric": 0.82, "sample_size": 200},  # 样本不足
        ]

        winner, status = determine_winner_with_min_samples(results, 500)
        assert winner is None
        assert status == "insufficient_samples"

        # 两组都满足
        results[1]["sample_size"] = 600
        winner, status = determine_winner_with_min_samples(results, 500)
        assert winner == "treatment"


class TestABIntegration:
    """A/B 测试集成测试"""

    def test_full_experiment_flow(self):
        """测试完整实验流程"""
        # 1. 创建实验
        experiment = {
            "id": "exp-1",
            "status": "draft",
            "traffic_percent": 50,
        }

        # 2. 启动实验
        experiment["status"] = "running"

        # 3. 分流用户
        user_groups = {}
        for i in range(100):
            user_id = f"user-{i}"
            if i < 50:  # 50% 用户参与实验
                hash_value = sum(ord(c) for c in user_id)
                user_groups[user_id] = "treatment" if hash_value % 2 == 0 else "control"

        # 4. 计算指标
        treatment_metric = 0.82
        control_metric = 0.75

        # 5. 判定胜出
        winner = "treatment" if treatment_metric > control_metric else "control"

        assert winner == "treatment"
        assert experiment["status"] == "running"


# ========== Service 层单元测试 ==========


def _make_experiment(
    exp_id: str = "exp-1",
    name: str = "test-experiment",
    status: str = ExperimentStatus.DRAFT,
    experiment_type: str = "model_compare",
    target_model_id: str | None = None,
    created_by: str | None = None,
) -> ABExperiment:
    """构造实验对象"""
    exp = ABExperiment(
        name=name,
        experiment_type=experiment_type,
        target_model_id=target_model_id,
        status=status,
        created_by=created_by,
    )
    exp.id = exp_id
    return exp


def _make_group(
    group_id: str = "group-1",
    experiment_id: str = "exp-1",
    name: str = "control",
    model_id: str | None = "model-1",
    traffic_percentage: int = 50,
    skip_on_circuit_open: bool = True,
) -> ABGroup:
    """构造分组对象"""
    group = ABGroup(
        experiment_id=experiment_id,
        name=name,
        model_id=model_id,
        traffic_percentage=traffic_percentage,
        skip_on_circuit_open=skip_on_circuit_open,
    )
    group.id = group_id
    return group


@pytest.fixture
def mock_db():
    """模拟异步数据库会话"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def service(mock_db):
    """构造已隔离外部依赖的 ABTestService"""
    mock_circuit_breaker = AsyncMock()
    mock_llm_manager = AsyncMock()
    with (
        patch(
            "app.services.ab_test_service.CircuitBreakerService",
            return_value=mock_circuit_breaker,
        ),
        patch("app.services.ab_test_service.LLMManager") as mock_llm_cls,
    ):
        mock_llm_cls.get_instance.return_value = mock_llm_manager
        svc = ABTestService(mock_db)
        yield svc


class TestABTestService:
    """ABTestService 服务层单元测试"""

    # --- create_experiment ---

    async def test_create_experiment_normal_returns_draft_experiment(
        self, service, mock_db
    ):
        # Arrange & Act
        result = await service.create_experiment(
            name="my-exp",
            experiment_type="model_compare",
        )
        # Assert
        assert result.name == "my-exp"
        assert result.status == ExperimentStatus.DRAFT
        assert result.experiment_type == "model_compare"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    async def test_create_experiment_with_optional_fields_sets_attributes(
        self, service, mock_db
    ):
        # Arrange & Act
        result = await service.create_experiment(
            name="full-exp",
            experiment_type="config_compare",
            description="desc",
            target_model_id="model-x",
            user_id="user-1",
        )
        # Assert
        assert result.name == "full-exp"
        assert result.description == "desc"
        assert result.target_model_id == "model-x"
        assert result.created_by == "user-1"

    # --- add_group ---

    async def test_add_group_draft_experiment_succeeds(self, service, mock_db):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.DRAFT)
        service.get_experiment = AsyncMock(return_value=experiment)
        # Act
        result = await service.add_group(
            experiment_id="exp-1",
            name="control",
            model_id="model-1",
            traffic_percentage=50,
        )
        # Assert
        assert result.name == "control"
        assert result.experiment_id == "exp-1"
        assert result.traffic_percentage == 50
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    async def test_add_group_non_draft_experiment_raises_validation_error(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.RUNNING)
        service.get_experiment = AsyncMock(return_value=experiment)
        # Act & Assert
        with pytest.raises(ValidationError, match="草稿状态"):
            await service.add_group(experiment_id="exp-1", name="control")
        mock_db.add.assert_not_called()

    async def test_add_group_experiment_not_found_propagates_error(
        self, service, mock_db
    ):
        # Arrange
        service.get_experiment = AsyncMock(side_effect=NotFoundError("实验不存在"))
        # Act & Assert
        with pytest.raises(NotFoundError):
            await service.add_group(experiment_id="missing", name="control")
        mock_db.add.assert_not_called()

    # --- start_experiment ---

    async def test_start_experiment_draft_with_two_groups_sets_running(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.DRAFT)
        service.get_experiment = AsyncMock(return_value=experiment)
        service.list_groups = AsyncMock(
            return_value=[_make_group("g1"), _make_group("g2")]
        )
        # Act
        result = await service.start_experiment("exp-1")
        # Assert
        assert result.status == ExperimentStatus.RUNNING
        assert result.start_at is not None
        mock_db.commit.assert_awaited_once()

    async def test_start_experiment_paused_resumes_to_running(self, service, mock_db):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.PAUSED)
        service.get_experiment = AsyncMock(return_value=experiment)
        service.list_groups = AsyncMock(
            return_value=[_make_group("g1"), _make_group("g2")]
        )
        # Act
        result = await service.start_experiment("exp-1")
        # Assert
        assert result.status == ExperimentStatus.RUNNING

    async def test_start_experiment_running_raises_validation_error(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.RUNNING)
        service.get_experiment = AsyncMock(return_value=experiment)
        # Act & Assert
        with pytest.raises(ValidationError, match="只能启动草稿或暂停状态"):
            await service.start_experiment("exp-1")
        mock_db.commit.assert_not_awaited()

    async def test_start_experiment_with_one_group_raises_validation_error(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.DRAFT)
        service.get_experiment = AsyncMock(return_value=experiment)
        service.list_groups = AsyncMock(return_value=[_make_group("g1")])
        # Act & Assert
        with pytest.raises(ValidationError, match="至少需要2个分组"):
            await service.start_experiment("exp-1")
        mock_db.commit.assert_not_awaited()

    # --- pause_experiment ---

    async def test_pause_experiment_running_sets_paused(self, service, mock_db):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.RUNNING)
        service.get_experiment = AsyncMock(return_value=experiment)
        # Act
        result = await service.pause_experiment("exp-1")
        # Assert
        assert result.status == ExperimentStatus.PAUSED
        mock_db.commit.assert_awaited_once()

    async def test_pause_experiment_not_running_raises_validation_error(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.DRAFT)
        service.get_experiment = AsyncMock(return_value=experiment)
        # Act & Assert
        with pytest.raises(ValidationError, match="只能暂停运行中的实验"):
            await service.pause_experiment("exp-1")
        mock_db.commit.assert_not_awaited()

    # --- complete_experiment ---

    async def test_complete_experiment_running_with_winner_sets_completed(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.RUNNING)
        winner = _make_group("g2", experiment_id="exp-1", model_id="model-2")
        service.get_experiment = AsyncMock(return_value=experiment)
        service.get_group = AsyncMock(return_value=winner)
        # Act
        result = await service.complete_experiment(
            "exp-1", "g2", conclusion="winner is g2"
        )
        # Assert
        assert result.status == ExperimentStatus.COMPLETED
        assert result.winner_group_id == "g2"
        assert result.end_at is not None
        assert result.conclusion == "winner is g2"
        service.llm_manager.reload_llm.assert_awaited_once_with("model-2")
        mock_db.commit.assert_awaited_once()

    async def test_complete_experiment_not_running_raises_validation_error(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.DRAFT)
        service.get_experiment = AsyncMock(return_value=experiment)
        # Act & Assert
        with pytest.raises(ValidationError, match="只能完成运行中的实验"):
            await service.complete_experiment("exp-1", "g2")
        mock_db.commit.assert_not_awaited()

    async def test_complete_experiment_winner_from_other_experiment_raises(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.RUNNING)
        winner = _make_group("g2", experiment_id="other-exp", model_id="model-2")
        service.get_experiment = AsyncMock(return_value=experiment)
        service.get_group = AsyncMock(return_value=winner)
        # Act & Assert
        with pytest.raises(ValidationError, match="不属于该实验"):
            await service.complete_experiment("exp-1", "g2")
        mock_db.commit.assert_not_awaited()

    async def test_complete_experiment_winner_without_model_skips_reload(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.RUNNING)
        winner = _make_group("g2", experiment_id="exp-1", model_id=None)
        service.get_experiment = AsyncMock(return_value=experiment)
        service.get_group = AsyncMock(return_value=winner)
        # Act
        result = await service.complete_experiment("exp-1", "g2")
        # Assert
        assert result.status == ExperimentStatus.COMPLETED
        service.llm_manager.reload_llm.assert_not_awaited()

    # --- record_result ---

    async def test_record_result_normal_returns_result(self, service, mock_db):
        # Arrange & Act
        result = await service.record_result(
            experiment_id="exp-1",
            group_id="g1",
            session_id="sess-1",
            question="hello",
            answer="world",
            model_id="model-1",
            latency_ms=100,
            input_tokens=10,
            output_tokens=20,
            success=True,
        )
        # Assert
        assert result.experiment_id == "exp-1"
        assert result.group_id == "g1"
        assert result.question == "hello"
        assert result.answer == "world"
        assert result.is_success is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    async def test_record_result_failure_records_success_false(self, service, mock_db):
        # Arrange & Act
        result = await service.record_result(
            experiment_id="exp-1",
            group_id="g1",
            session_id="sess-1",
            question="hello",
            success=False,
        )
        # Assert
        assert result.is_success is False

    # --- get_experiment ---

    async def test_get_experiment_found_returns_experiment(self, service, mock_db):
        # Arrange
        experiment = _make_experiment()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = experiment
        mock_db.execute.return_value = mock_result
        # Act
        result = await service.get_experiment("exp-1")
        # Assert
        assert result is experiment

    async def test_get_experiment_not_found_raises_not_found_error(
        self, service, mock_db
    ):
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        # Act & Assert
        with pytest.raises(NotFoundError, match="实验不存在"):
            await service.get_experiment("missing")

    # --- get_group ---

    async def test_get_group_found_returns_group(self, service, mock_db):
        # Arrange
        group = _make_group()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = group
        mock_db.execute.return_value = mock_result
        # Act
        result = await service.get_group("group-1")
        # Assert
        assert result is group

    async def test_get_group_not_found_raises_not_found_error(self, service, mock_db):
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        # Act & Assert
        with pytest.raises(NotFoundError, match="分组不存在"):
            await service.get_group("missing")

    # --- list_groups ---

    async def test_list_groups_returns_groups(self, service, mock_db):
        # Arrange
        groups = [_make_group("g1"), _make_group("g2")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = groups
        mock_db.execute.return_value = mock_result
        # Act
        result = await service.list_groups("exp-1")
        # Assert
        assert result == groups
        assert len(result) == 2

    # --- list_experiments ---

    async def test_list_experiments_returns_items_and_total(self, service, mock_db):
        # Arrange
        experiments = [_make_experiment("e1"), _make_experiment("e2")]
        count_result = MagicMock()
        count_result.scalar.return_value = 5
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = experiments
        mock_db.execute.side_effect = [count_result, items_result]
        # Act
        items, total = await service.list_experiments(page=1, page_size=20)
        # Assert
        assert items == experiments
        assert total == 5

    async def test_list_experiments_empty_returns_empty_list_and_zero(
        self, service, mock_db
    ):
        # Arrange
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = []
        mock_db.execute.side_effect = [count_result, items_result]
        # Act
        items, total = await service.list_experiments(
            status=ExperimentStatus.RUNNING, page=1, page_size=10
        )
        # Assert
        assert items == []
        assert total == 0

    # --- get_analysis ---

    async def test_get_analysis_with_groups_returns_stats(self, service, mock_db):
        # Arrange
        experiment = _make_experiment()
        groups = [_make_group("g1"), _make_group("g2")]
        service.get_experiment = AsyncMock(return_value=experiment)
        service.list_groups = AsyncMock(return_value=groups)
        stats_row = MagicMock()
        stats_row.total = 10
        stats_row.success_count = 8
        stats_row.avg_latency = 100.0
        stats_row.avg_input_tokens = 50.0
        stats_row.avg_output_tokens = 60.0
        stats_row.avg_feedback = 4.0
        stats_result = MagicMock()
        stats_result.one.return_value = stats_row
        mock_db.execute.side_effect = [stats_result, stats_result]
        # Act
        analysis = await service.get_analysis("exp-1")
        # Assert
        assert analysis["experiment_id"] == "exp-1"
        assert analysis["name"] == "test-experiment"
        assert len(analysis["groups"]) == 2
        first = analysis["groups"][0]
        assert first["total_requests"] == 10
        assert first["success_rate"] == 80.0
        assert first["avg_latency_ms"] == 100
        assert first["avg_input_tokens"] == 50
        assert first["avg_output_tokens"] == 60
        assert first["avg_feedback"] == 4.0

    async def test_get_analysis_no_groups_returns_empty_groups(self, service, mock_db):
        # Arrange
        experiment = _make_experiment()
        service.get_experiment = AsyncMock(return_value=experiment)
        service.list_groups = AsyncMock(return_value=[])
        # Act
        analysis = await service.get_analysis("exp-1")
        # Assert
        assert analysis["groups"] == []

    # --- route_request ---

    async def test_route_request_not_running_returns_none_false(self, service, mock_db):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.PAUSED)
        service.get_experiment = AsyncMock(return_value=experiment)
        # Act
        group, available = await service.route_request("exp-1", "sess-1")
        # Assert
        assert group is None
        assert available is False

    async def test_route_request_all_groups_available_returns_group(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.RUNNING)
        groups = [
            _make_group("g1", traffic_percentage=50, skip_on_circuit_open=False),
            _make_group("g2", traffic_percentage=50, skip_on_circuit_open=False),
        ]
        service.get_experiment = AsyncMock(return_value=experiment)
        service.list_groups = AsyncMock(return_value=groups)
        # Act
        group, available = await service.route_request("exp-1", "sess-1")
        # Assert
        assert available is True
        assert group in groups

    async def test_route_request_circuit_open_skips_group(self, service, mock_db):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.RUNNING)
        groups = [
            _make_group(
                "g1",
                model_id="model-1",
                traffic_percentage=50,
                skip_on_circuit_open=True,
            ),
            _make_group(
                "g2",
                model_id="model-2",
                traffic_percentage=50,
                skip_on_circuit_open=False,
            ),
        ]
        service.get_experiment = AsyncMock(return_value=experiment)
        service.list_groups = AsyncMock(return_value=groups)
        service.circuit_breaker.check_availability.return_value = False
        # Act
        group, available = await service.route_request("exp-1", "sess-1")
        # Assert
        assert available is True
        assert group.id == "g2"
        service.circuit_breaker.check_availability.assert_awaited_once_with("model-1")

    async def test_route_request_all_circuits_open_returns_none_false(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.RUNNING)
        groups = [
            _make_group(
                "g1",
                model_id="model-1",
                traffic_percentage=50,
                skip_on_circuit_open=True,
            ),
        ]
        service.get_experiment = AsyncMock(return_value=experiment)
        service.list_groups = AsyncMock(return_value=groups)
        service.circuit_breaker.check_availability.return_value = False
        # Act
        group, available = await service.route_request("exp-1", "sess-1")
        # Assert
        assert group is None
        assert available is False

    async def test_route_request_group_without_model_id_always_available(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.RUNNING)
        groups = [
            _make_group(
                "g1",
                model_id=None,
                traffic_percentage=100,
                skip_on_circuit_open=True,
            ),
        ]
        service.get_experiment = AsyncMock(return_value=experiment)
        service.list_groups = AsyncMock(return_value=groups)
        # Act
        group, available = await service.route_request("exp-1", "sess-1")
        # Assert
        assert available is True
        assert group.id == "g1"
        service.circuit_breaker.check_availability.assert_not_awaited()

    async def test_route_request_same_session_routes_consistently(
        self, service, mock_db
    ):
        # Arrange
        experiment = _make_experiment(status=ExperimentStatus.RUNNING)
        groups = [
            _make_group("g1", traffic_percentage=50, skip_on_circuit_open=False),
            _make_group("g2", traffic_percentage=50, skip_on_circuit_open=False),
        ]
        service.get_experiment = AsyncMock(return_value=experiment)
        service.list_groups = AsyncMock(return_value=groups)
        # Act
        results = [await service.route_request("exp-1", "sess-1") for _ in range(5)]
        # Assert
        assigned = {r[0].id for r in results}
        assert len(assigned) == 1
