"""
智能问答平台 - 智能路由模型

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


class Complexity(str):
    """复杂度级别"""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class RoutingStrategy(str):
    """路由策略"""

    COST_FIRST = "cost_first"
    QUALITY_FIRST = "quality_first"
    BALANCED = "balanced"
    LATENCY_FIRST = "latency_first"


class RouterRule(Base):
    """路由规则"""

    __tablename__ = "router_rules"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="规则名称",
    )

    complexity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="复杂度：simple/medium/complex",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False,
        comment="优先级",
    )

    target_model_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="目标模型ID",
    )

    version_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="指定版本ID（空则使用活跃版本）",
    )

    config_override: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="配置覆盖",
    )

    conditions: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="触发条件",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否启用",
    )

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
        return f"<RouterRule {self.name}>"


class RouterPolicy(Base):
    """路由策略"""

    __tablename__ = "router_policies"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="策略名称",
    )

    strategy: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="策略类型",
    )

    fallback_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="启用降级",
    )

    fallback_model_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="降级模型ID",
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="默认策略",
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
        return f"<RouterPolicy {self.name}>"


class RouterLog(Base):
    """路由日志"""

    __tablename__ = "router_logs"

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

    question_preview: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="问题预览",
    )

    complexity: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="判定复杂度",
    )

    routed_model_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="路由到的模型",
    )

    routing_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="路由原因",
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="路由决策耗时",
    )

    is_fallback: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否降级",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<RouterLog {self.session_id} -> {self.routed_model_id}>"
