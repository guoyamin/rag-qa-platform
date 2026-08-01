"""
智能问答平台 - 成本告警模型

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 版本: V1.0
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AlertLevel(str):
    """告警级别"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str):
    """告警状态"""

    PENDING = "pending"  # 待处理
    NOTIFIED = "notified"  # 已通知
    ACKNOWLEDGED = "acknowledged"  # 已确认
    RESOLVED = "resolved"  # 已解决
    AUTO_RESOLVED = "auto_resolved"  # 自动解决


class CostAlert(Base):
    """成本告警"""

    __tablename__ = "cost_alerts"

    # 告警条件
    alert_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="告警名称",
    )

    target_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="目标类型：global/model/user",
    )

    target_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="目标ID",
    )

    # 阈值配置
    threshold_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="阈值类型：daily/monthly/total",
    )

    threshold_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
        comment="阈值金额",
    )

    # 告警状态
    level: Mapped[str] = mapped_column(
        String(20),
        default=AlertLevel.WARNING,
        nullable=False,
        comment="告警级别",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=AlertStatus.PENDING,
        nullable=False,
        comment="状态",
    )

    # 当前值
    current_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        default=Decimal("0"),
        nullable=False,
        comment="当前金额",
    )

    # 告警详情
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="告警消息",
    )

    # 时间范围
    period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="统计周期开始",
    )

    period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="统计周期结束",
    )

    # 触发时间
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
        comment="触发时间",
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="解决时间",
    )

    resolved_by: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="解决人",
    )

    # 配置
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否启用",
    )

    auto_resolve: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否自动解决",
    )

    notify_channels: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="通知渠道",
    )

    def __repr__(self) -> str:
        return f"<CostAlert {self.alert_name} {self.status}>"
