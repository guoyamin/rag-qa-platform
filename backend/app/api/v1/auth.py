"""
智能问答平台 - 认证API路由
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas import (
    ChangePasswordRequest,
    DataResponse,
    LoginRequest,
    RefreshTokenRequest,
    ResponseBase,
    UserProfileResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=DataResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> DataResponse:
    """
    用户登录

    - **username**: 用户名/工号
    - **password**: 密码
    - **auth_type**: 认证类型(local/ldap)，留空自动判断
    """
    client_ip = request.client.host if request.client else None
    auth_service = AuthService(db)
    token_data = await auth_service.authenticate(login_data, client_ip)

    return DataResponse(data=token_data)


@router.post("/refresh", response_model=DataResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> DataResponse:
    """刷新访问Token"""
    auth_service = AuthService(db)
    token_data = await auth_service.refresh_token(refresh_data.refresh_token)

    return DataResponse(data=token_data)


@router.get("/me", response_model=DataResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> DataResponse:
    """获取当前登录用户信息"""
    return DataResponse(data=UserProfileResponse.model_validate(current_user))


@router.post("/logout", response_model=ResponseBase)
async def logout() -> ResponseBase:
    """用户登出（前端清除Token即可）"""
    return ResponseBase(message="登出成功")


@router.post("/password/change", response_model=ResponseBase)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ResponseBase:
    """修改密码（仅本地认证用户可用）"""
    auth_service = AuthService(db)
    await auth_service.change_password(
        current_user,
        password_data.old_password,
        password_data.new_password,
    )
    return ResponseBase(message="密码修改成功")
