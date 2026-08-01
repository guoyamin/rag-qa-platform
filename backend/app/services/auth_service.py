from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
    verify_token_type,
)
from app.models.user import User, UserAuthType, UserRole, UserStatus
from app.schemas import LoginRequest, TokenResponse, UserCreate

logger = structlog.get_logger(__name__)


class AuthService:
    """认证服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(
        self,
        login_data: LoginRequest,
        client_ip: str | None = None,
    ) -> TokenResponse:
        """
        用户认证入口
        根据配置和请求自动选择认证方式
        """
        auth_type = login_data.auth_type or settings.AUTH_MODE

        # hybrid模式优先尝试LDAP
        if auth_type == "hybrid":
            # 先尝试本地认证
            user = await self._local_auth(login_data.username, login_data.password)
            if user:
                return await self._create_token_response(user, client_ip)

            # 本地失败则尝试LDAP
            if settings.LDAP_SERVER:
                user = await self._ldap_auth(login_data.username, login_data.password)
                if user:
                    return await self._create_token_response(user, client_ip)

        elif auth_type == "ldap":
            user = await self._ldap_auth(login_data.username, login_data.password)
            if user:
                return await self._create_token_response(user, client_ip)

        else:
            # local模式
            user = await self._local_auth(login_data.username, login_data.password)
            if user:
                return await self._create_token_response(user, client_ip)

        raise AuthenticationError("用户名或密码错误")

    async def _local_auth(self, username: str, password: str) -> User | None:
        """本地认证"""
        result = await self.db.execute(
            select(User).where(
                User.username == username,
                User.is_deleted.is_(False),
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        if user.auth_type != UserAuthType.LOCAL:
            return None

        if not user.hashed_password:
            return None

        # 先检查锁定状态，避免对锁定账号进行密码验证
        if user.status == UserStatus.LOCKED:
            raise AuthorizationError("账号已锁定，请联系管理员")

        if not verify_password(password, user.hashed_password):
            # 更新失败次数
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                user.status = UserStatus.LOCKED
            await self.db.commit()
            return None

        return user

    async def _ldap_auth(self, username: str, password: str) -> User | None:
        """LDAP认证（使用 ldap3 纯 Python 库）"""
        try:
            from ldap3 import SUBTREE, Connection, Server

            server = Server(settings.LDAP_SERVER)
            search_filter = settings.LDAP_USER_SEARCH_FILTER.format(username=username)

            # 1. 先用绑定账号（或匿名）搜索用户 DN
            #    注意：不能用 search filter 当作 DN 直接绑定
            search_conn = Connection(
                server,
                user=settings.LDAP_BIND_DN,
                password=settings.LDAP_BIND_PASSWORD,
                auto_bind=True,
            )
            search_conn.search(
                search_base=settings.LDAP_BASE_DN,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=["cn", "mail"],
            )
            if not search_conn.entries:
                search_conn.unbind()
                return None

            entry = search_conn.entries[0]
            user_dn = entry.entry_dn
            cn_value = str(entry.cn) if hasattr(entry, "cn") and entry.cn else username
            mail_value = (
                str(entry.mail) if hasattr(entry, "mail") and entry.mail else None
            )
            search_conn.unbind()

            # 2. 再用用户 DN + 密码绑定，验证凭据
            auth_conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
            )
            if not auth_conn.bound:
                auth_conn.unbind()
                return None
            auth_conn.unbind()

            # 3. 查找或创建本地用户
            db_result = await self.db.execute(
                select(User).where(
                    User.username == username,
                    User.is_deleted.is_(False),
                )
            )
            user = db_result.scalar_one_or_none()

            if not user:
                # 创建新用户
                user = User(
                    username=username,
                    display_name=cn_value,
                    email=mail_value,
                    auth_type=UserAuthType.LDAP,
                    role=UserRole.STAFF,
                    status=UserStatus.ACTIVE,
                    ldap_dn=user_dn,
                )
                self.db.add(user)
                await self.db.commit()
                await self.db.refresh(user)
            else:
                # 更新用户信息
                user.auth_type = UserAuthType.LDAP
                user.ldap_dn = user_dn
                user.status = UserStatus.ACTIVE
                await self.db.commit()

            return user

        except ImportError:
            logger.warning(
                "ldap3_not_installed", message="ldap3 未安装，LDAP 认证不可用"
            )
            return None
        except Exception:
            logger.exception("ldap_auth_failed", username=username)
            return None

    async def _create_token_response(
        self,
        user: User,
        client_ip: str | None = None,
    ) -> TokenResponse:
        """创建Token响应"""
        # 更新登录信息
        user.last_login_at = datetime.now(UTC)
        user.last_login_ip = client_ip
        user.login_count += 1
        user.failed_login_count = 0
        await self.db.commit()

        # 创建Token
        extra_claims = {
            "username": user.username,
            "role": user.role.value,
            "display_name": user.display_name or user.username,
        }

        access_token = create_access_token(
            subject=user.id,
            extra_claims=extra_claims,
        )
        refresh_token = create_refresh_token(subject=user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """刷新访问Token"""
        payload = decode_token(refresh_token)
        if not payload or not verify_token_type(payload, "refresh"):
            raise AuthenticationError("无效的刷新Token")

        user_id = payload.get("sub")
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.is_deleted.is_(False),
            )
        )
        user = result.scalar_one_or_none()

        if not user or user.status != UserStatus.ACTIVE:
            raise AuthenticationError("用户不存在或已被禁用")

        return await self._create_token_response(user)

    async def create_local_user(self, user_data: UserCreate) -> User:
        """创建本地用户"""
        # 检查用户名是否已存在
        result = await self.db.execute(
            select(User).where(User.username == user_data.username)
        )
        if result.scalar_one_or_none():
            raise ValidationError("用户名已存在")

        user = User(
            username=user_data.username,
            email=user_data.email,
            phone=user_data.phone,
            display_name=user_data.display_name,
            hashed_password=get_password_hash(user_data.password),
            auth_type=UserAuthType.LOCAL,
            role=UserRole(user_data.role),
            department=user_data.department,
            position=user_data.position,
            status=UserStatus.ACTIVE,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(
        self,
        user: User,
        old_password: str,
        new_password: str,
    ) -> bool:
        """修改密码"""
        if user.auth_type != UserAuthType.LOCAL:
            raise ValidationError("LDAP/SSO用户不能修改密码")

        if not verify_password(old_password, user.hashed_password or ""):
            raise ValidationError("原密码错误")

        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
        return True
