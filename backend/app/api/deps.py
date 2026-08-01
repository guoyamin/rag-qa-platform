"""
智能问答平台 - API依赖
"""

from fastapi import Depends, Request, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_token, verify_token_type
from app.db.session import AsyncSessionLocal, get_db
from app.models.user import User, UserStatus

# 安全方案
security = HTTPBearer(auto_error=False)

# 显式声明再导出：get_db 定义在 app.db.session，供 API 路由通过 deps 统一导入
__all__ = [
    "get_current_user",
    "get_current_active_user",
    "RoleChecker",
    "require_admin",
    "require_operator",
    "require_staff",
    "get_db",
    "get_ws_user",
    "security",
]


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    """获取当前登录用户"""
    token = None

    # 优先从Header获取
    if credentials:
        token = credentials.credentials
    else:
        # 尝试从Cookie获取
        token = request.cookies.get("access_token")

    if not token:
        raise AuthenticationError("未授权，请先登录")

    payload = decode_token(token)
    if not payload:
        raise AuthenticationError("未授权，请先登录")

    if not verify_token_type(payload, "access"):
        raise AuthenticationError("未授权，请先登录")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("未授权，请先登录")

    # 查询用户
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        )
        user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("未授权，请先登录")

    if user.status != UserStatus.ACTIVE:
        raise AuthorizationError("账号已被禁用或锁定")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前活跃用户"""
    return current_user


class RoleChecker:
    """角色权限检查"""

    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if user.role.value not in self.allowed_roles:
            raise AuthorizationError("权限不足")
        return user


# 常用角色检查器
require_admin = RoleChecker(["super_admin", "admin"])
require_operator = RoleChecker(["super_admin", "admin", "operator"])
require_staff = RoleChecker(["super_admin", "admin", "operator", "staff"])


async def get_ws_user(websocket: WebSocket) -> User | None:
    """从WebSocket获取用户"""
    token = websocket.query_params.get("token")
    if not token:
        return None

    payload = decode_token(token)
    if not payload or not verify_token_type(payload, "access"):
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        )
        user = result.scalar_one_or_none()

    if not user or user.status != UserStatus.ACTIVE:
        return None

    return user
