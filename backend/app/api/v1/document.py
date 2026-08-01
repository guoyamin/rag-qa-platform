"""
智能问答平台 - 文档管理API路由
"""

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db, require_admin
from app.models.user import User
from app.schemas import (
    DataResponse,
    DocumentUploadResponse,
    ListResponse,
    PaginationParams,
    ResponseBase,
)

router = APIRouter(prefix="/documents", tags=["文档管理"])


@router.get("", response_model=ListResponse)
async def list_documents(
    kb_id: str | None = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ListResponse:
    """获取文档列表"""
    # TODO: 实现查询
    return ListResponse(data=[], total=0)


@router.post("/upload", response_model=DataResponse)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DataResponse:
    """上传文档到知识库"""
    # TODO: 实现上传和处理
    return DataResponse(
        data=DocumentUploadResponse(
            id="temp",
            title=file.filename or "未命名",
            status="pending",
            message="文档已接收，正在处理中",
        )
    )


@router.get("/{doc_id}", response_model=DataResponse)
async def get_document(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DataResponse:
    """获取文档详情"""
    # TODO: 实现查询
    return DataResponse(data=None)


@router.delete("/{doc_id}", response_model=ResponseBase)
async def delete_document(
    doc_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ResponseBase:
    """删除文档"""
    # TODO: 实现删除
    return ResponseBase(message="删除成功")


@router.post("/{doc_id}/reindex", response_model=ResponseBase)
async def reindex_document(
    doc_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ResponseBase:
    """重新索引文档"""
    # TODO: 实现重新索引
    return ResponseBase(message="重新索引任务已提交")
