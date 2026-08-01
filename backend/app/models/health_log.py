"""
智能问答平台 - 模型健康日志

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 版本: V1.0
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelHealthLog(Base):
    """模型健康检查日志"""

    __tablename__ = "model_health_logs"

    model_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="模型ID",
    )

    check_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="检查类型：quick/full/comprehensive",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="状态：healthy/degraded/unhealthy/unknown",
    )

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="响应延迟",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息",
    )

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
        index=True,
        comment="检查时间",
    )

    def __repr__(self) -> str:
        return f"<ModelHealthLog {self.model_id} {self.status}>"
