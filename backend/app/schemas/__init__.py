"""
智能问答平台 - Pydantic Schemas
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# 导出模型管理 schemas
from app.schemas.model import *  # noqa: F401, F403

# ==================== 基础响应 ====================


class ResponseBase(BaseModel):
    """基础响应"""

    code: str = "SUCCESS"
    message: str = "操作成功"


class DataResponse(ResponseBase):
    """带数据的响应"""

    data: Any = None


class ListResponse(ResponseBase):
    """列表响应"""

    data: list[Any] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


class ErrorResponse(BaseModel):
    """错误响应"""

    code: str
    message: str
    detail: str | None = None


# ==================== 分页 ====================


class PaginationParams(BaseModel):
    """分页参数"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ==================== 认证相关 ====================


class TokenResponse(BaseModel):
    """Token响应"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    """登录请求"""

    username: str = Field(..., min_length=1, max_length=64, description="用户名/工号")
    password: str = Field(..., min_length=1, max_length=128, description="密码")
    auth_type: str | None = Field(default=None, description="认证类型: local/ldap")


class RefreshTokenRequest(BaseModel):
    """刷新Token请求"""

    refresh_token: str


# ==================== 用户相关 ====================


class UserBase(BaseModel):
    """用户基础信息"""

    username: str
    email: str | None = None
    phone: str | None = None
    display_name: str | None = None
    avatar: str | None = None
    role: str = "staff"
    department: str | None = None
    position: str | None = None


class UserCreate(UserBase):
    """创建用户"""

    password: str = Field(..., min_length=8, max_length=128)
    auth_type: str = "local"


class UserUpdate(BaseModel):
    """更新用户"""

    email: str | None = None
    phone: str | None = None
    display_name: str | None = None
    avatar: str | None = None
    department: str | None = None
    position: str | None = None
    status: str | None = None
    description: str | None = None


class UserResponse(UserBase):
    """用户响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    auth_type: str
    status: str
    last_login_at: datetime | None = None
    login_count: int = 0
    created_at: datetime


class UserProfileResponse(UserResponse):
    """用户个人信息"""

    pass


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""

    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


# ==================== 聊天相关 ====================


class ChatRequest(BaseModel):
    """聊天请求"""

    message: str = Field(..., min_length=1, max_length=5000, description="用户消息")
    session_id: str | None = Field(default=None, description="会话ID(为空则新建)")
    kb_ids: list[str] | None = Field(default=None, description="指定知识库")
    stream: bool = Field(default=True, description="是否流式输出")


class ChatMessageResponse(BaseModel):
    """聊天消息响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str
    sources: list[dict[str, Any]] | None = None
    created_at: datetime
    tokens_used: int | None = None
    latency_ms: int | None = None


class ChatSessionResponse(BaseModel):
    """会话响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    kb_ids: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ChatFeedbackRequest(BaseModel):
    """聊天反馈请求"""

    message_id: str
    is_liked: bool
    feedback: str | None = None


# ==================== 知识库相关 ====================


class KnowledgeBaseCreate(BaseModel):
    """创建知识库"""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库"""

    name: str | None = None
    description: str | None = None


class KnowledgeBaseResponse(BaseModel):
    """知识库响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    document_count: int
    chunk_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""

    id: str
    title: str
    status: str
    message: str


class DocumentResponse(BaseModel):
    """文档响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    kb_id: str
    title: str
    doc_type: str
    file_size: int | None
    status: str
    chunk_count: int
    vector_count: int
    error_message: str | None
    processed_at: datetime | None
    created_at: datetime
