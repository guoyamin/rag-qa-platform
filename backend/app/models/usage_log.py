"""
智能问答平台 - 模型用量日志

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 版本: V1.0
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelUsageLog(Base):
    """模型用量明细日志"""

    __tablename__ = "model_usage_logs"

    model_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="模型ID",
    )

    user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="用户ID",
    )

    session_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="会话ID",
    )

    scene: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="使用场景",
    )

    input_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="输入Token数",
    )

    output_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="输出Token数",
    )

    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="总Token数",
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="响应时间",
    )

    success: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="是否成功",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息",
    )

    cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        default=Decimal("0"),
        nullable=False,
        comment="预估费用",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
        index=True,
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<ModelUsageLog {self.model_id} {self.total_tokens} tokens>"


class ModelUsageDaily(Base):
    """模型用量日聚合报表"""

    __tablename__ = "model_usage_daily"

    model_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="模型ID",
    )

    date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="统计日期",
    )

    total_calls: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="总调用次数",
    )

    success_calls: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="成功次数",
    )

    failed_calls: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="失败次数",
    )

    total_input_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="总输入Token",
    )

    total_output_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="总输出Token",
    )

    avg_latency_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="平均响应时间",
    )

    success_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0"),
        nullable=False,
        comment="成功率",
    )

    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        default=Decimal("0"),
        nullable=False,
        comment="预估费用",
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
        return f"<ModelUsageDaily {self.model_id} {self.date}>"
