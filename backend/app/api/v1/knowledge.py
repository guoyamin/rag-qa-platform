"""
智能问答平台 - 知识库管理API路由
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db, require_admin
from app.models.user import User
from app.schemas import (
    DataResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    ListResponse,
    PaginationParams,
    ResponseBase,
)

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])


@router.get("/bases", response_model=ListResponse)
async def list_knowledge_bases(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ListResponse:
    """获取知识库列表"""
    # TODO: 实现查询
    return ListResponse(data=[], total=0)


@router.post("/bases", response_model=DataResponse)
async def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DataResponse:
    """创建知识库"""
    # TODO: 实现创建
    return DataResponse(data=None)


@router.get("/bases/{kb_id}", response_model=DataResponse)
async def get_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DataResponse:
    """获取知识库详情"""
    # TODO: 实现查询
    return DataResponse(data=None)


@router.put("/bases/{kb_id}", response_model=DataResponse)
async def update_knowledge_base(
    kb_id: str,
    kb_data: KnowledgeBaseUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DataResponse:
    """更新知识库"""
    # TODO: 实现更新
    return DataResponse(data=None)


@router.delete("/bases/{kb_id}", response_model=ResponseBase)
async def delete_knowledge_base(
    kb_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ResponseBase:
    """删除知识库"""
    # TODO: 实现删除
    return ResponseBase(message="删除成功")
