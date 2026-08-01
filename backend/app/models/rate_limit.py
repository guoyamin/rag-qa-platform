"""
智能问答平台 - 限流和熔断模型

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 版本: V1.0
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateLimitConfig(Base):
    """限流配置"""

    __tablename__ = "rate_limit_configs"

    limit_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="限流类型：global/user/model",
    )

    target_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="目标ID（模型ID/用户ID等）",
    )

    max_requests: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="最大请求数",
    )

    window_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="时间窗口（秒）",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否启用",
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
        return f"<RateLimitConfig {self.limit_type} {self.max_requests}/{self.window_seconds}s>"


class CircuitBreakerState(Base):
    """熔断状态"""

    __tablename__ = "circuit_breaker_states"

    model_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        comment="模型ID",
    )

    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="closed",
        comment="状态：closed/open/half_open",
    )

    failure_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="连续失败次数",
    )

    success_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="连续成功次数",
    )

    last_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后失败时间",
    )

    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="熔断开始时间",
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="熔断结束时间",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<CircuitBreakerState {self.model_id} {self.state}>"


class RateLimitRecord(Base):
    """限流记录"""

    __tablename__ = "rate_limit_records"

    limit_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="限流类型",
    )

    target_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="目标ID",
    )

    request_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="本次请求数",
    )

    limited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否被限流",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<RateLimitRecord {self.limit_type} {self.request_count}>"
