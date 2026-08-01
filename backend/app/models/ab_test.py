"""
智能问答平台 - A/B 测试模型

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 版本: V1.0
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExperimentStatus(str):
    """实验状态"""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ExperimentType(str):
    """实验类型"""

    MODEL_COMPARE = "model_compare"
    CONFIG_COMPARE = "config_compare"
    PROMPT_COMPARE = "prompt_compare"


class ABExperiment(Base):
    """A/B 实验"""

    __tablename__ = "ab_experiments"

    # 实验信息
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="实验名称",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="实验描述",
    )

    experiment_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="实验类型",
    )

    target_model_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="目标模型ID",
    )

    # 状态
    status: Mapped[str] = mapped_column(
        String(20),
        default=ExperimentStatus.DRAFT,
        nullable=False,
        comment="状态",
    )

    # 时间范围
    start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="开始时间",
    )

    end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="结束时间",
    )

    # 结果
    winner_group_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="获胜分组ID",
    )

    conclusion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="实验结论",
    )

    # 元数据
    created_by: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="创建人",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
        comment="创建时间",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<ABExperiment {self.name}>"


class ABGroup(Base):
    """A/B 分组"""

    __tablename__ = "ab_groups"

    experiment_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="实验ID",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="分组名称",
    )

    model_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="使用的模型ID",
    )

    config_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="配置快照",
    )

    traffic_percentage: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
        comment="流量分配",
    )

    skip_on_circuit_open: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="熔断时跳过",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<ABGroup {self.name}>"


class ABResult(Base):
    """A/B 结果"""

    __tablename__ = "ab_results"

    experiment_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="实验ID",
    )

    group_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="分组ID",
    )

    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="会话ID",
    )

    user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="用户ID",
    )

    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="用户问题",
    )

    answer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="模型回答",
    )

    model_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="实际调用的模型ID",
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="响应时间",
    )

    input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="输入Token数",
    )

    output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="输出Token数",
    )

    is_success: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否成功",
    )

    feedback_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="用户反馈：1-5",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<ABResult {self.experiment_id} {self.group_id}>"
