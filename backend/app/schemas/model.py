"""
智能问答平台 - 模型管理 API Schema

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 功能描述: 模型管理相关 Pydantic Schema
- 版本: V1.0

修订记录:
- 2026-08-01 V1.0 初始版本（AI生成）
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ========== API Key 相关 ==========


class KeyStatus(str, Enum):
    """Key 状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


class KeyUsage(str, Enum):
    """Key 用途"""

    LLM = "llm"
    EMBEDDING = "embedding"
    BOTH = "both"


class ApiKeyCreate(BaseModel):
    """创建 API Key 请求"""

    name: str = Field(..., min_length=1, max_length=100, description="Key 名称")
    provider: str = Field(..., min_length=1, max_length=50, description="提供商名称")
    api_key: str = Field(..., min_length=1, description="API Key 明文（会被加密存储）")
    usage: KeyUsage = Field(default=KeyUsage.LLM, description="用途")
    expires_at: datetime | None = Field(default=None, description="过期时间")
    description: str | None = Field(default=None, max_length=500, description="描述")


class ApiKeyUpdate(BaseModel):
    """更新 API Key 请求"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    api_key: str | None = Field(
        default=None, min_length=1, description="新 Key（会重新加密存储）"
    )
    status: KeyStatus | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)
    description: str | None = Field(default=None, max_length=500)


class ApiKeyResponse(BaseModel):
    """API Key 响应（不含明文）"""

    id: str
    name: str
    provider: str
    usage: KeyUsage
    status: KeyStatus
    key_preview: str = Field(..., description="Key 预览（显示前后各2位）")
    expires_at: datetime | None
    description: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(BaseModel):
    """创建 API Key 响应（首次显示明文）"""

    id: str
    name: str
    provider: str
    api_key: str = Field(..., description="明文 Key，仅在创建时返回")
    key_preview: str
    created_at: datetime


# ========== 模型实例相关 ==========


class ModelProvider(str, Enum):
    """模型提供商"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    QWEN = "qwen"
    DOUBAO = "doubao"
    LOCAL = "local"
    OTHER = "other"


class ModelStatus(str, Enum):
    """模型状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class ModelConfig(BaseModel):
    """模型配置"""

    model: str = Field(..., description="模型名称")
    api_base: str | None = Field(default=None, description="API 基础地址")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=2048, ge=1, description="最大 Token 数")
    top_p: float | None = Field(default=None, ge=0, le=1, description="Top P 参数")
    timeout: int = Field(default=60, ge=1, description="超时时间（秒）")


class ModelInstanceCreate(BaseModel):
    """创建模型实例请求"""

    name: str = Field(..., min_length=1, max_length=100, description="实例名称")
    provider: ModelProvider = Field(..., description="提供商")
    api_key_id: str | None = Field(default=None, description="关联的 API Key ID")
    model_type: str = Field(default="chat", description="模型类型: chat/embedding")
    config: ModelConfig = Field(..., description="模型配置")
    description: str | None = Field(default=None, max_length=500)


class ModelInstanceUpdate(BaseModel):
    """更新模型实例请求"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    api_key_id: str | None = Field(default=None)
    status: ModelStatus | None = Field(default=None)
    config: ModelConfig | None = Field(default=None)
    description: str | None = Field(default=None, max_length=500)


class ModelInstanceResponse(BaseModel):
    """模型实例响应"""

    id: str
    name: str
    provider: ModelProvider
    api_key_id: str | None
    model_type: str
    config: ModelConfig
    status: ModelStatus
    description: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelInstanceListResponse(BaseModel):
    """模型实例列表响应"""

    items: list[ModelInstanceResponse]
    total: int
    page: int
    page_size: int


# ========== Embedding 配置 ==========


class EmbeddingConfigUpdate(BaseModel):
    """更新 Embedding 配置请求"""

    provider: ModelProvider | None = Field(default=None)
    api_key_id: str | None = Field(default=None)
    model: str | None = Field(default=None, min_length=1, max_length=100)
    api_base: str | None = Field(default=None)
    dimension: int | None = Field(default=None, ge=1, description="向量维度")


class EmbeddingConfigResponse(BaseModel):
    """Embedding 配置响应"""

    provider: ModelProvider
    api_key_id: str | None
    model: str
    api_base: str | None
    dimension: int


# ========== 模型对比 ==========


class ModelCompareRequest(BaseModel):
    """模型对比请求"""

    question: str = Field(..., min_length=1, description="测试问题")
    model_ids: list[str] = Field(
        ..., min_length=2, max_length=5, description="要对比的模型 ID"
    )


class ModelCompareResult(BaseModel):
    """单个模型对比结果"""

    model_id: str
    model_name: str
    response: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    success: bool
    error: str | None = None


class ModelCompareResponse(BaseModel):
    """模型对比响应"""

    question: str
    results: list[ModelCompareResult]
    started_at: datetime
    completed_at: datetime


# ========== 健康检查相关 ==========


class HealthStatus(str, Enum):
    """健康状态"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheckResponse(BaseModel):
    """健康检查响应"""

    model_id: str
    model_name: str
    status: HealthStatus
    latency_ms: int | None = None
    error_message: str | None = None
    checked_at: datetime


class HealthSummaryResponse(BaseModel):
    """健康摘要响应"""

    total_models: int
    healthy_count: int
    degraded_count: int
    unhealthy_count: int
    unknown_count: int


# ========== 预设模板相关 ==========


class TemplateCategory(str, Enum):
    """模板分类"""

    CHAT = "chat"
    EMBEDDING = "embedding"
    RAG = "rag"
    CUSTOM = "custom"


class TemplateCreate(BaseModel):
    """创建模板请求"""

    name: str = Field(..., min_length=1, max_length=100)
    category: TemplateCategory = Field(...)
    description: str | None = Field(default=None, max_length=500)
    config: dict[str, Any] = Field(..., description="模板配置")
    is_public: bool = Field(default=True)
    tags: list[str] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    """更新模板请求"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    config: dict[str, Any] | None = None
    is_public: bool | None = None
    tags: list[str] | None = None


class TemplateResponse(BaseModel):
    """模板响应"""

    id: str
    name: str
    category: TemplateCategory
    description: str | None
    config: dict[str, Any]
    is_public: bool
    tags: list[str]
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    """模板列表响应"""

    items: list[TemplateResponse]
    total: int
    page: int
    page_size: int


# ========== 审计日志相关 ==========


class AuditAction(str, Enum):
    """审计动作"""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ENABLE = "enable"
    DISABLE = "disable"
    QUERY = "query"


class ResourceType(str, Enum):
    """资源类型"""

    MODEL = "model"
    API_KEY = "api_key"
    TEMPLATE = "template"
    VERSION = "version"


class AuditLogResponse(BaseModel):
    """审计日志响应"""

    id: str
    action: AuditAction
    resource_type: ResourceType
    resource_id: str
    resource_name: str | None = None
    user_id: str
    user_name: str | None = None
    changes: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """审计日志列表响应"""

    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


# ========== 用量统计相关 ==========


class UsageLogResponse(BaseModel):
    """用量日志响应"""

    id: str
    model_id: str
    model_name: str
    model_provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    latency_ms: int
    user_id: str | None = None
    session_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelUsageSummary(BaseModel):
    """模型用量摘要"""

    model_id: str
    model_name: str
    requests: int
    total_tokens: int
    cost: float


class DayUsageSummary(BaseModel):
    """日用量摘要"""

    date: str
    requests: int
    input_tokens: int
    output_tokens: int
    cost: float


class UsageStatsResponse(BaseModel):
    """用量统计响应"""

    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    avg_latency_ms: float
    by_model: list[ModelUsageSummary]
    by_day: list[DayUsageSummary]


class CostSummaryResponse(BaseModel):
    """成本摘要响应"""

    total_cost: float
    daily_cost: float
    monthly_cost: float
    budget_limit: float | None = None
    budget_used_percent: float | None = None
    projected_monthly_cost: float | None = None


# ========== 限流熔断相关 ==========


class CircuitState(str, Enum):
    """熔断状态"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RateLimitStrategy(str, Enum):
    """限流策略"""

    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"  # nosec B105 -- 限流策略枚举值,非密码


class RateLimitResponse(BaseModel):
    """限流响应"""

    allowed: bool
    limit: int
    remaining: int
    reset_at: datetime
    retry_after: int


class CircuitBreakerResponse(BaseModel):
    """熔断器状态响应"""

    model_id: str
    state: CircuitState
    failure_count: int
    last_failure_at: datetime | None = None
    last_success_at: datetime | None = None


class RateLimitConfigResponse(BaseModel):
    """限流配置响应"""

    id: str
    model_id: str
    strategy: RateLimitStrategy
    requests_per_minute: int
    burst_size: int | None = None
    enabled: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


# ========== 版本管理相关 ==========


class VersionStatus(str, Enum):
    """版本状态"""

    DRAFT = "draft"
    RELEASED = "released"
    DEPRECATED = "deprecated"
    ROLLED_BACK = "rolled_back"


class ReleaseType(str, Enum):
    """发布类型"""

    FULL = "full"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    ROLLING = "rolling"


class VersionCreate(BaseModel):
    """创建版本请求"""

    model_id: str = Field(...)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+(-[\w.]+)?$")
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    config: dict[str, Any] = Field(...)


class VersionUpdate(BaseModel):
    """更新版本请求"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    config: dict[str, Any] | None = None


class VersionRollout(BaseModel):
    """版本发布请求"""

    release_type: ReleaseType = Field(default=ReleaseType.FULL)
    rollout_percent: int = Field(default=100, ge=0, le=100)


class VersionResponse(BaseModel):
    """版本响应"""

    id: str
    model_id: str
    version: str
    name: str
    description: str | None
    config: dict[str, Any]
    status: VersionStatus
    release_type: ReleaseType
    rollout_percent: int
    created_by: str | None = None
    released_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VersionListResponse(BaseModel):
    """版本列表响应"""

    items: list[VersionResponse]
    total: int
    page: int
    page_size: int


# ========== A/B 测试相关 ==========


class ExperimentStatus(str, Enum):
    """实验状态"""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class ExperimentCreate(BaseModel):
    """创建实验请求"""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    traffic_percent: int = Field(default=100, ge=1, le=100)
    end_time: datetime | None = None


class ExperimentUpdate(BaseModel):
    """更新实验请求"""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    traffic_percent: int | None = Field(default=None, ge=1, le=100)
    end_time: datetime | None = None


class ExperimentResponse(BaseModel):
    """实验响应"""

    id: str
    name: str
    description: str | None
    status: ExperimentStatus
    traffic_percent: int
    start_time: datetime | None = None
    end_time: datetime | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ABGroupCreate(BaseModel):
    """创建 A/B 分组请求"""

    name: str = Field(..., min_length=1, max_length=100)
    model_id: str = Field(...)
    traffic_percent: int = Field(..., ge=1, le=100)
    description: str | None = None


class ABGroupResponse(BaseModel):
    """A/B 分组响应"""

    id: str
    experiment_id: str
    name: str
    model_id: str
    traffic_percent: int
    description: str | None = None

    model_config = {"from_attributes": True}


class ABAnalysisResponse(BaseModel):
    """A/B 分析报告响应"""

    experiment_id: str
    groups: list[ABGroupResponse]
    metrics: dict[str, Any]  # 每个分组的指标
    winner: str | None = None
    is_significant: bool = False
    confidence_level: float | None = None


# ========== 智能路由相关 ==========


class RoutingStrategy(str, Enum):
    """路由策略"""

    COST_FIRST = "cost_first"
    QUALITY_FIRST = "quality_first"
    LATENCY_FIRST = "latency_first"
    BALANCED = "balanced"


class RouterRuleCreate(BaseModel):
    """创建路由规则请求"""

    name: str = Field(..., min_length=1, max_length=100)
    strategy: RoutingStrategy = Field(...)
    model_ids: list[str] = Field(..., min_length=1)
    conditions: dict[str, Any] | None = Field(default=None, description="路由条件")
    priority: int = Field(default=0)
    is_active: bool = Field(default=True)


class RouterRuleResponse(BaseModel):
    """路由规则响应"""

    id: str
    name: str
    strategy: RoutingStrategy
    model_ids: list[str]
    conditions: dict[str, Any] | None
    priority: int
    is_active: bool

    model_config = {"from_attributes": True}


class RouterStrategyResponse(BaseModel):
    """路由策略响应"""

    id: str
    name: str
    strategy: RoutingStrategy
    description: str | None
    config: dict[str, Any]
    priority: int
    is_active: bool


class RouterPreviewRequest(BaseModel):
    """路由预览请求"""

    question: str = Field(..., min_length=1)


class RouterPreviewResult(BaseModel):
    """路由预览结果"""

    model_id: str
    model_name: str
    estimated_cost: float
    estimated_latency: int
    quality_score: float
    recommended: bool = False


class RouterPreviewResponse(BaseModel):
    """路由预览响应"""

    question: str
    recommended_model_id: str
    all_options: list[RouterPreviewResult]
