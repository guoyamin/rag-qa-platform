"""
智能问答平台 - 用量统计服务单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.usage_stats_service import (
    DEFAULT_PRICING,
    MODEL_PRICING,
    UsageStatsService,
)


class TestUsageStats:
    """用量统计测试"""

    def test_usage_log_schema(self):
        """测试用量日志 Schema"""
        from app.schemas.model import UsageLogResponse

        response = UsageLogResponse(
            id="log-1",
            model_id="model-1",
            model_name="GPT-4",
            model_provider="openai",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost=0.03,
            latency_ms=1500,
            user_id="user-1",
            session_id="session-1",
            created_at=datetime.now(),
        )

        assert response.input_tokens == 1000
        assert response.output_tokens == 500
        assert response.total_tokens == 1500
        assert response.cost == 0.03

    def test_daily_aggregation(self):
        """测试日聚合计算"""
        logs = [
            {"input_tokens": 1000, "output_tokens": 500, "cost": 0.03},
            {"input_tokens": 2000, "output_tokens": 1000, "cost": 0.06},
            {"input_tokens": 1500, "output_tokens": 750, "cost": 0.045},
        ]

        total_input = sum(log["input_tokens"] for log in logs)
        total_output = sum(log["output_tokens"] for log in logs)
        total_cost = sum(log["cost"] for log in logs)

        assert total_input == 4500
        assert total_output == 2250
        assert total_cost == 0.135

    def test_cost_calculation(self):
        """测试成本计算"""
        # GPT-4 定价 (输入: $0.03/1K tokens, 输出: $0.06/1K tokens)
        input_price_per_1k = 0.03
        output_price_per_1k = 0.06

        def calculate_cost(input_tokens: int, output_tokens: int) -> float:
            input_cost = (input_tokens / 1000) * input_price_per_1k
            output_cost = (output_tokens / 1000) * output_price_per_1k
            return round(input_cost + output_cost, 6)

        # 测试用例
        assert calculate_cost(1000, 500) == 0.06  # 0.03 + 0.03
        assert calculate_cost(0, 1000) == 0.06  # 仅输出
        assert calculate_cost(1000, 0) == 0.03  # 仅输入

    def test_usage_by_model_aggregation(self):
        """测试按模型聚合"""
        logs = [
            {"model_id": "model-1", "input_tokens": 1000, "cost": 0.03},
            {"model_id": "model-2", "input_tokens": 2000, "cost": 0.06},
            {"model_id": "model-1", "input_tokens": 500, "cost": 0.015},
        ]

        by_model = {}
        for log in logs:
            model_id = log["model_id"]
            if model_id not in by_model:
                by_model[model_id] = {"input_tokens": 0, "cost": 0}
            by_model[model_id]["input_tokens"] += log["input_tokens"]
            by_model[model_id]["cost"] += log["cost"]

        assert by_model["model-1"]["input_tokens"] == 1500
        assert by_model["model-1"]["cost"] == 0.045
        assert by_model["model-2"]["input_tokens"] == 2000


class TestUsageStatsQuery:
    """用量统计查询测试"""

    def test_time_range_filter(self):
        """测试时间范围过滤"""
        logs = [
            {"created_at": datetime(2026, 7, 1)},
            {"created_at": datetime(2026, 7, 15)},
            {"created_at": datetime(2026, 8, 1)},
        ]

        start_date = datetime(2026, 7, 10)
        end_date = datetime(2026, 7, 31)

        filtered = [log for log in logs if start_date <= log["created_at"] <= end_date]

        assert len(filtered) == 1

    def test_model_filter(self):
        """测试模型过滤"""
        logs = [
            {"model_id": "model-1"},
            {"model_id": "model-2"},
            {"model_id": "model-1"},
        ]

        model_logs = [log for log in logs if log["model_id"] == "model-1"]

        assert len(model_logs) == 2

    def test_pagination(self):
        """测试分页"""
        logs = [{"id": str(i)} for i in range(100)]

        def paginate(items: list, page: int, page_size: int) -> tuple:
            start = (page - 1) * page_size
            end = start + page_size
            return items[start:end], len(items)

        page2, total = paginate(logs, 2, 10)

        assert len(page2) == 10
        assert page2[0]["id"] == "10"
        assert total == 100


class TestUsageStatsAggregation:
    """用量聚合测试"""

    def test_hourly_aggregation(self):
        """测试小时聚合"""
        logs = [
            {"created_at": datetime(2026, 8, 1, 10, 15)},
            {"created_at": datetime(2026, 8, 1, 10, 45)},
            {"created_at": datetime(2026, 8, 1, 11, 20)},
        ]

        from collections import defaultdict

        hourly = defaultdict(list)

        for log in logs:
            hour = log["created_at"].replace(minute=0, second=0)
            hourly[hour].append(log)

        assert len(hourly[datetime(2026, 8, 1, 10, 0)]) == 2
        assert len(hourly[datetime(2026, 8, 1, 11, 0)]) == 1

    def test_daily_aggregation(self):
        """测试日聚合"""
        logs = [
            {"created_at": datetime(2026, 7, 15), "cost": 1.0},
            {"created_at": datetime(2026, 7, 15), "cost": 2.0},
            {"created_at": datetime(2026, 7, 16), "cost": 3.0},
        ]

        from collections import defaultdict

        daily = defaultdict(float)

        for log in logs:
            date = log["created_at"].date()
            daily[date] += log["cost"]

        assert daily[logs[0]["created_at"].date()] == 3.0
        assert daily[logs[2]["created_at"].date()] == 3.0

    def test_monthly_aggregation(self):
        """测试月聚合"""
        logs = [
            {"created_at": datetime(2026, 6, 15), "cost": 10.0},
            {"created_at": datetime(2026, 7, 1), "cost": 20.0},
            {"created_at": datetime(2026, 7, 31), "cost": 30.0},
        ]

        from collections import defaultdict

        monthly = defaultdict(float)

        for log in logs:
            month = log["created_at"].strftime("%Y-%m")
            monthly[month] += log["cost"]

        assert monthly["2026-06"] == 10.0
        assert monthly["2026-07"] == 50.0


class TestUsageStatsResponse:
    """用量统计响应测试"""

    def test_stats_summary_response(self):
        """测试统计摘要响应"""
        from app.schemas.model import UsageStatsResponse

        response = UsageStatsResponse(
            total_requests=1000,
            total_input_tokens=500000,
            total_output_tokens=250000,
            total_cost=15.0,
            avg_latency_ms=250,
            by_model=[
                {
                    "model_id": "model-1",
                    "model_name": "模型1",
                    "requests": 600,
                    "total_tokens": 300000,
                    "cost": 9.0,
                },
                {
                    "model_id": "model-2",
                    "model_name": "模型2",
                    "requests": 400,
                    "total_tokens": 200000,
                    "cost": 6.0,
                },
            ],
            by_day=[
                {
                    "date": "2026-07-30",
                    "requests": 50,
                    "input_tokens": 25000,
                    "output_tokens": 12500,
                    "cost": 0.75,
                },
                {
                    "date": "2026-07-31",
                    "requests": 60,
                    "input_tokens": 30000,
                    "output_tokens": 15000,
                    "cost": 0.9,
                },
            ],
        )

        assert response.total_requests == 1000
        assert response.total_cost == 15.0
        assert len(response.by_model) == 2

    def test_cost_summary_response(self):
        """测试成本摘要响应"""
        from app.schemas.model import CostSummaryResponse

        response = CostSummaryResponse(
            total_cost=100.0,
            daily_cost=10.0,
            monthly_cost=50.0,
            budget_limit=200.0,
            budget_used_percent=50.0,
            projected_monthly_cost=150.0,
        )

        assert response.budget_used_percent == 50.0
        assert response.projected_monthly_cost == 150.0


# ========== Service 层单元测试 ==========


def _make_mock_db() -> MagicMock:
    """Create a mock AsyncSession with async methods configured."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


def _make_stats_row(**kwargs: object) -> MagicMock:
    """Create a mock row for get_usage_stats query results."""
    row = MagicMock()
    row.total_tokens = kwargs.get("total_tokens", 0)
    row.input_tokens = kwargs.get("input_tokens", 0)
    row.output_tokens = kwargs.get("output_tokens", 0)
    row.total_cost = kwargs.get("total_cost", Decimal("0"))
    row.total_calls = kwargs.get("total_calls", 0)
    row.success_calls = kwargs.get("success_calls", 0)
    return row


def _make_ranking_row(**kwargs: object) -> MagicMock:
    """Create a mock row for ranking query results."""
    row = MagicMock()
    row.model_id = kwargs.get("model_id", "model-1")
    row.user_id = kwargs.get("user_id", "user-1")
    row.total_tokens = kwargs.get("total_tokens", 1000)
    row.total_cost = kwargs.get("total_cost", Decimal("0.01"))
    row.total_calls = kwargs.get("total_calls", 5)
    return row


def _make_daily_row(**kwargs: object) -> MagicMock:
    """Create a mock row for aggregate_daily_stats query results."""
    row = MagicMock()
    row.model_id = kwargs.get("model_id", "model-1")
    row.total_calls = kwargs.get("total_calls", 10)
    row.success_calls = kwargs.get("success_calls", 8)
    row.failed_calls = kwargs.get("failed_calls", 2)
    row.total_input_tokens = kwargs.get("total_input_tokens", 5000)
    row.total_output_tokens = kwargs.get("total_output_tokens", 2500)
    row.avg_latency_ms = kwargs.get("avg_latency_ms", 200)
    row.estimated_cost = kwargs.get("estimated_cost", Decimal("0.05"))
    return row


class TestCalculateCost:
    """UsageStatsService.calculate_cost 单元测试"""

    def test_calculate_cost_known_model_returns_expected_cost(self):
        """已知模型应按 MODEL_PRICING 计算费用"""
        # Arrange
        service = UsageStatsService(_make_mock_db())

        # Act
        cost = service.calculate_cost("gpt-4o", 1000, 500)

        # Assert
        pricing = MODEL_PRICING["gpt-4o"]
        expected = Decimal(1000) * pricing["input"] + Decimal(500) * pricing["output"]
        assert cost == expected

    def test_calculate_cost_unknown_model_uses_default_pricing(self):
        """未知模型应使用 DEFAULT_PRICING 计算费用"""
        # Arrange
        service = UsageStatsService(_make_mock_db())

        # Act
        cost = service.calculate_cost("unknown-model", 1000, 500)

        # Assert
        expected = (
            Decimal(1000) * DEFAULT_PRICING["input"]
            + Decimal(500) * DEFAULT_PRICING["output"]
        )
        assert cost == expected

    def test_calculate_cost_zero_tokens_returns_zero(self):
        """零 token 应返回零费用"""
        # Arrange
        service = UsageStatsService(_make_mock_db())

        # Act
        cost = service.calculate_cost("gpt-4o", 0, 0)

        # Assert
        assert cost == Decimal("0")

    def test_calculate_cost_embedding_model_zero_output_cost(self):
        """嵌入模型 output 单价为 0 时输出费用应为 0"""
        # Arrange
        service = UsageStatsService(_make_mock_db())

        # Act
        cost = service.calculate_cost("text-embedding-3-small", 1000, 0)

        # Assert
        pricing = MODEL_PRICING["text-embedding-3-small"]
        assert cost == Decimal(1000) * pricing["input"]
        assert pricing["output"] == Decimal("0")


class TestRecordUsage:
    """UsageStatsService.record_usage 单元测试"""

    async def test_record_usage_success_persists_and_returns_log(self):
        """成功调用应持久化日志并返回含费用的记录"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)

        # Act
        log = await service.record_usage(
            model_id="model-1",
            model_name="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            latency_ms=200,
            user_id="user-1",
            session_id="session-1",
            scene="chat",
        )

        # Assert
        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()
        assert log.model_id == "model-1"
        assert log.input_tokens == 1000
        assert log.output_tokens == 500
        assert log.total_tokens == 1500
        assert log.success is True
        assert log.cost == service.calculate_cost("gpt-4o", 1000, 500)

    async def test_record_usage_minimal_params_uses_defaults(self):
        """仅必填参数时应使用默认值 success=True"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)

        # Act
        log = await service.record_usage(
            model_id="model-1",
            model_name="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )

        # Assert
        assert log.success is True
        assert log.error_message is None
        assert log.latency_ms is None
        assert log.user_id is None

    async def test_record_usage_failed_records_error_message(self):
        """失败调用应记录 success=False 和错误信息"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)

        # Act
        log = await service.record_usage(
            model_id="model-1",
            model_name="gpt-4o",
            input_tokens=100,
            output_tokens=0,
            total_tokens=100,
            success=False,
            error_message="timeout",
        )

        # Assert
        assert log.success is False
        assert log.error_message == "timeout"

    async def test_record_usage_commit_failure_propagates_exception(self):
        """db.commit 抛出异常时应向上传播"""
        # Arrange
        db = _make_mock_db()
        db.commit.side_effect = RuntimeError("db error")
        service = UsageStatsService(db)

        # Act / Assert
        with pytest.raises(RuntimeError, match="db error"):
            await service.record_usage(
                model_id="model-1",
                model_name="gpt-4o",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
            )


class TestGetUsageStats:
    """UsageStatsService.get_usage_stats 单元测试"""

    async def test_get_usage_stats_no_filters_returns_aggregated_stats(self):
        """无筛选条件应返回聚合统计"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.one.return_value = _make_stats_row(
            total_tokens=1500,
            input_tokens=1000,
            output_tokens=500,
            total_cost=Decimal("0.02"),
            total_calls=10,
            success_calls=8,
        )
        db.execute.return_value = mock_result

        # Act
        stats = await service.get_usage_stats()

        # Assert
        assert stats["total_tokens"] == 1500
        assert stats["input_tokens"] == 1000
        assert stats["output_tokens"] == 500
        assert stats["total_cost"] == 0.02
        assert stats["total_calls"] == 10
        assert stats["success_calls"] == 8
        assert stats["failed_calls"] == 2

    async def test_get_usage_stats_empty_data_returns_zeros(self):
        """无数据时所有字段应为 0"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.one.return_value = _make_stats_row(
            total_tokens=None,
            input_tokens=None,
            output_tokens=None,
            total_cost=None,
            total_calls=None,
            success_calls=None,
        )
        db.execute.return_value = mock_result

        # Act
        stats = await service.get_usage_stats()

        # Assert
        assert stats["total_tokens"] == 0
        assert stats["input_tokens"] == 0
        assert stats["output_tokens"] == 0
        assert stats["total_cost"] == 0.0
        assert stats["total_calls"] == 0
        assert stats["success_calls"] == 0
        assert stats["failed_calls"] == 0

    async def test_get_usage_stats_with_filters_returns_filtered_stats(self):
        """带筛选条件应执行查询并返回结果"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.one.return_value = _make_stats_row(
            total_tokens=500,
            total_calls=3,
            success_calls=3,
        )
        db.execute.return_value = mock_result

        # Act
        stats = await service.get_usage_stats(
            model_id="model-1",
            user_id="user-1",
            start_date=datetime(2026, 7, 1),
            end_date=datetime(2026, 7, 31),
        )

        # Assert
        db.execute.assert_awaited_once()
        assert stats["total_calls"] == 3
        assert stats["failed_calls"] == 0

    async def test_get_usage_stats_all_failed_calculates_failed_calls(self):
        """全部失败时 failed_calls 应等于 total_calls"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.one.return_value = _make_stats_row(
            total_calls=5,
            success_calls=0,
        )
        db.execute.return_value = mock_result

        # Act
        stats = await service.get_usage_stats()

        # Assert
        assert stats["failed_calls"] == 5

    async def test_get_usage_stats_execute_failure_propagates_exception(self):
        """db.execute 抛出异常时应向上传播"""
        # Arrange
        db = _make_mock_db()
        db.execute.side_effect = RuntimeError("query failed")
        service = UsageStatsService(db)

        # Act / Assert
        with pytest.raises(RuntimeError, match="query failed"):
            await service.get_usage_stats()


class TestGetModelRanking:
    """UsageStatsService.get_model_ranking 单元测试"""

    async def test_get_model_ranking_returns_sorted_models(self):
        """应返回按费用排序的模型列表"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            _make_ranking_row(
                model_id="model-1",
                total_tokens=5000,
                total_cost=Decimal("0.05"),
                total_calls=10,
            ),
            _make_ranking_row(
                model_id="model-2",
                total_tokens=2000,
                total_cost=Decimal("0.02"),
                total_calls=5,
            ),
        ]
        db.execute.return_value = mock_result

        # Act
        ranking = await service.get_model_ranking()

        # Assert
        assert len(ranking) == 2
        assert ranking[0]["model_id"] == "model-1"
        assert ranking[0]["total_tokens"] == 5000
        assert ranking[0]["total_cost"] == 0.05
        assert ranking[0]["total_calls"] == 10

    async def test_get_model_ranking_empty_returns_empty_list(self):
        """无数据时应返回空列表"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        db.execute.return_value = mock_result

        # Act
        ranking = await service.get_model_ranking()

        # Assert
        assert ranking == []

    async def test_get_model_ranking_with_date_filters_calls_execute(self):
        """带日期筛选应执行查询"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.all.return_value = [_make_ranking_row(model_id="model-1")]
        db.execute.return_value = mock_result

        # Act
        ranking = await service.get_model_ranking(
            start_date=datetime(2026, 7, 1),
            end_date=datetime(2026, 7, 31),
            limit=5,
        )

        # Assert
        db.execute.assert_awaited_once()
        assert len(ranking) == 1

    async def test_get_model_ranking_none_cost_converted_to_zero(self):
        """total_cost 为 None 时应转为 0"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            _make_ranking_row(
                model_id="model-1",
                total_cost=None,
                total_tokens=None,
                total_calls=None,
            ),
        ]
        db.execute.return_value = mock_result

        # Act
        ranking = await service.get_model_ranking()

        # Assert
        assert ranking[0]["total_cost"] == 0.0
        assert ranking[0]["total_tokens"] == 0
        assert ranking[0]["total_calls"] == 0


class TestGetUserRanking:
    """UsageStatsService.get_user_ranking 单元测试"""

    async def test_get_user_ranking_returns_sorted_users(self):
        """应返回按费用排序的用户列表"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            _make_ranking_row(
                user_id="user-1",
                total_tokens=3000,
                total_cost=Decimal("0.03"),
                total_calls=8,
            ),
            _make_ranking_row(
                user_id="user-2",
                total_tokens=1000,
                total_cost=Decimal("0.01"),
                total_calls=3,
            ),
        ]
        db.execute.return_value = mock_result

        # Act
        ranking = await service.get_user_ranking()

        # Assert
        assert len(ranking) == 2
        assert ranking[0]["user_id"] == "user-1"
        assert ranking[0]["total_tokens"] == 3000
        assert ranking[0]["total_cost"] == 0.03

    async def test_get_user_ranking_empty_returns_empty_list(self):
        """无数据时应返回空列表"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        db.execute.return_value = mock_result

        # Act
        ranking = await service.get_user_ranking()

        # Assert
        assert ranking == []

    async def test_get_user_ranking_with_date_filters_calls_execute(self):
        """带日期筛选应执行查询"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.all.return_value = [_make_ranking_row(user_id="user-1")]
        db.execute.return_value = mock_result

        # Act
        ranking = await service.get_user_ranking(
            start_date=datetime(2026, 7, 1),
            end_date=datetime(2026, 7, 31),
        )

        # Assert
        db.execute.assert_awaited_once()
        assert len(ranking) == 1


class TestAggregateDailyStats:
    """UsageStatsService.aggregate_daily_stats 单元测试"""

    async def test_aggregate_daily_stats_with_data_creates_daily_records(self):
        """有数据时应为每个模型创建日聚合记录"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            _make_daily_row(
                model_id="model-1",
                total_calls=10,
                success_calls=8,
                failed_calls=2,
            ),
            _make_daily_row(
                model_id="model-2",
                total_calls=5,
                success_calls=5,
                failed_calls=0,
            ),
        ]
        db.execute.return_value = mock_result

        # Act
        await service.aggregate_daily_stats(date=datetime(2026, 7, 15))

        # Assert
        assert db.add.call_count == 2
        db.commit.assert_awaited_once()

    async def test_aggregate_daily_stats_no_data_skips_add(self):
        """无数据时不应调用 db.add 但仍应提交"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.all.return_value = []
        db.execute.return_value = mock_result

        # Act
        await service.aggregate_daily_stats(date=datetime(2026, 7, 15))

        # Assert
        db.add.assert_not_called()
        db.commit.assert_awaited_once()

    async def test_aggregate_daily_stats_zero_calls_success_rate_zero(self):
        """total_calls 为 0 时 success_rate 应为 0"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            _make_daily_row(
                model_id="model-1",
                total_calls=0,
                success_calls=0,
                failed_calls=0,
            ),
        ]
        db.execute.return_value = mock_result

        # Act
        await service.aggregate_daily_stats(date=datetime(2026, 7, 15))

        # Assert
        db.add.assert_called_once()
        added_obj = db.add.call_args[0][0]
        assert added_obj.success_rate == Decimal("0")

    async def test_aggregate_daily_stats_explicit_date_uses_given_date(self):
        """传入显式日期应使用该日期"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        target = datetime(2026, 7, 15, 14, 30)
        mock_result = MagicMock()
        mock_result.all.return_value = [_make_daily_row(model_id="model-1")]
        db.execute.return_value = mock_result

        # Act
        await service.aggregate_daily_stats(date=target)

        # Assert
        added_obj = db.add.call_args[0][0]
        expected_date = target.replace(hour=0, minute=0, second=0, microsecond=0).date()
        assert added_obj.date == expected_date

    async def test_aggregate_daily_stats_calculates_success_rate(self):
        """应正确计算成功率"""
        # Arrange
        db = _make_mock_db()
        service = UsageStatsService(db)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            _make_daily_row(model_id="model-1", total_calls=10, success_calls=8),
        ]
        db.execute.return_value = mock_result

        # Act
        await service.aggregate_daily_stats(date=datetime(2026, 7, 15))

        # Assert
        added_obj = db.add.call_args[0][0]
        assert added_obj.success_rate == Decimal(str(8 / 10 * 100))
