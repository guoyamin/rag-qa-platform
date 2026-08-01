"""
智能问答平台 - 审计日志

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 功能描述: 审计日志（等保三级合规）
- 版本: V1.0
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditAction(str, PyEnum):
    """审计操作类型"""

    # 认证相关
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"  # nosec B105 -- 审计动作枚举值,非密码

    # 用户管理
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_DISABLED = "user_disabled"

    # 模型管理
    MODEL_CREATED = "model_created"
    MODEL_UPDATED = "model_updated"
    MODEL_DELETED = "model_deleted"
    MODEL_ENABLED = "model_enabled"
    MODEL_DISABLED = "model_disabled"

    # API Key 管理
    API_KEY_CREATED = "api_key_created"
    API_KEY_UPDATED = "api_key_updated"
    API_KEY_DELETED = "api_key_deleted"
    API_KEY_ROTATED = "api_key_rotated"

    # 配置变更
    CONFIG_UPDATED = "config_updated"

    # 知识库
    KB_CREATED = "kb_created"
    KB_UPDATED = "kb_updated"
    KB_DELETED = "kb_deleted"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_DELETED = "document_deleted"

    # RAG 操作
    QUERY_EXECUTED = "query_executed"


class AuditLevel(str, PyEnum):
    """审计级别"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(Base):
    """审计日志（等保三级合规）"""

    __tablename__ = "audit_logs"

    # 操作信息
    action: Mapped[AuditAction] = mapped_column(
        nullable=False,
        index=True,
        comment="操作类型",
    )

    level: Mapped[AuditLevel] = mapped_column(
        default=AuditLevel.INFO,
        nullable=False,
        comment="日志级别",
    )

    # 主体信息
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="操作用户ID",
    )

    username: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="操作用户名",
    )

    user_role: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="操作用户角色",
    )

    # 客体信息
    target_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="目标类型（如: user, model, api_key）",
    )

    target_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="目标ID",
    )

    target_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="目标名称",
    )

    # 操作详情
    method: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="HTTP方法",
    )

    path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="请求路径",
    )

    request_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="请求数据（脱敏）",
    )

    response_status: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="响应状态码",
    )

    # 结果信息
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

    # 上下文
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="客户端IP",
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="User-Agent",
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now,
        nullable=False,
        index=True,
        comment="操作时间",
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.username}>"
