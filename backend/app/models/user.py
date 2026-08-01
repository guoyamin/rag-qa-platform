"""
智能问答平台 - 用户模型
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(str, PyEnum):
    """用户角色"""

    SUPER_ADMIN = "super_admin"  # 超级管理员
    ADMIN = "admin"  # 管理员
    OPERATOR = "operator"  # 业务用户
    STAFF = "staff"  # 内部职工
    GUEST = "guest"  # 访客


class UserStatus(str, PyEnum):
    """用户状态"""

    ACTIVE = "active"  # 正常
    INACTIVE = "inactive"  # 未激活
    LOCKED = "locked"  # 锁定
    DISABLED = "disabled"  # 禁用


class UserAuthType(str, PyEnum):
    """用户认证类型"""

    LOCAL = "local"  # 本地认证
    LDAP = "ldap"  # LDAP认证
    SSO = "sso"  # SSO认证


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    # 基础信息
    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="用户名/工号",
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        comment="邮箱",
    )
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="手机号",
    )
    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="显示名称",
    )
    avatar: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="头像URL",
    )

    # 认证信息
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="密码哈希（本地认证时必填）",
    )
    auth_type: Mapped[UserAuthType] = mapped_column(
        Enum(UserAuthType),
        default=UserAuthType.LOCAL,
        nullable=False,
        comment="认证类型",
    )
    ldap_dn: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="LDAP DN",
    )

    # 角色与状态
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.STAFF,
        nullable=False,
        comment="角色",
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus),
        default=UserStatus.ACTIVE,
        nullable=False,
        comment="状态",
    )

    # 部门信息
    department: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="部门",
    )
    position: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="职位",
    )

    # 登录记录
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后登录时间",
    )
    last_login_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="最后登录IP",
    )
    login_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="登录次数",
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="失败登录次数",
    )

    # 其他
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="备注",
    )
