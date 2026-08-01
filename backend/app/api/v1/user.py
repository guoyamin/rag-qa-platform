"""
智能问答平台 - 用户管理API路由
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.models.user import User
from app.schemas import (
    DataResponse,
    ListResponse,
    PaginationParams,
    ResponseBase,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", response_model=ListResponse)
async def list_users(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ListResponse:
    """获取用户列表（管理员）"""
    # TODO: 实现分页查询
    return ListResponse(data=[], total=0)


@router.post("", response_model=DataResponse)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DataResponse:
    """创建用户（管理员）"""
    auth_service = AuthService(db)
    user = await auth_service.create_local_user(user_data)
    return DataResponse(data=UserResponse.model_validate(user))


@router.get("/{user_id}", response_model=DataResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DataResponse:
    """获取用户详情"""
    # TODO: 实现查询
    return DataResponse(data=None)


@router.put("/{user_id}", response_model=DataResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DataResponse:
    """更新用户信息"""
    # TODO: 实现更新
    return DataResponse(data=None)


@router.delete("/{user_id}", response_model=ResponseBase)
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ResponseBase:
    """删除用户（软删除）"""
    # TODO: 实现删除
    return ResponseBase(message="删除成功")


@router.put("/{user_id}/status", response_model=ResponseBase)
async def update_user_status(
    user_id: str,
    status: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ResponseBase:
    """更新用户状态"""
    # TODO: 实现状态更新
    return ResponseBase(message="状态更新成功")
