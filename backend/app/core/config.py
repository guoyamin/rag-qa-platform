"""
智能问答平台 - 核心配置
"""

from functools import lru_cache
from typing import Any, Self, cast

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === 应用基础配置 ===
    APP_NAME: str = Field(default="智能问答平台", description="应用名称")
    APP_VERSION: str = Field(default="1.0.0", description="应用版本")
    DEBUG: bool = Field(default=False, description="调试模式")
    ENV: str = Field(default="development", description="运行环境")

    # === 服务器配置 ===
    HOST: str = Field(
        default="0.0.0.0", description="监听地址"  # nosec B104 -- 容器部署需绑定0.0.0.0
    )
    PORT: int = Field(default=8000, description="监听端口")

    # === 数据库配置 ===
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/rag_qa",
        description="PostgreSQL连接字符串",
    )
    DATABASE_POOL_SIZE: int = Field(default=20, description="连接池大小")
    DATABASE_MAX_OVERFLOW: int = Field(default=10, description="连接池溢出")

    # === Redis配置 ===
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis连接字符串",
    )

    # === 向量数据库配置 (Milvus) ===
    MILVUS_HOST: str = Field(default="localhost", description="Milvus主机")
    MILVUS_PORT: int = Field(default=19530, description="Milvus端口")
    MILVUS_COLLECTION: str = Field(
        default="rag_qa_knowledge", description="Milvus集合名"
    )
    MILVUS_DIM: int = Field(default=1536, description="向量维度")

    # === 安全配置 ===
    SECRET_KEY: str = Field(
        default="your-super-secret-key-change-in-production",
        description="JWT密钥",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=480, description="访问Token过期时间(分钟)"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7, description="刷新Token过期时间(天)"
    )

    # === 密码策略 ===
    PASSWORD_MIN_LENGTH: int = Field(default=8, description="密码最小长度")

    # === 企业认证配置 (SSO/LDAP) ===
    AUTH_MODE: str = Field(default="hybrid", description="认证模式: local/ldap/hybrid")
    LDAP_SERVER: str | None = Field(default=None, description="LDAP服务器地址")
    LDAP_BASE_DN: str | None = Field(default=None, description="LDAP基础DN")
    LDAP_BIND_DN: str | None = Field(default=None, description="LDAP绑定DN")
    LDAP_BIND_PASSWORD: str | None = Field(default=None, description="LDAP绑定密码")
    LDAP_USER_SEARCH_FILTER: str = Field(
        default="(uid={username})", description="LDAP用户搜索过滤器"
    )

    # === LLM配置 ===
    LLM_PROVIDER: str = Field(
        default="openai", description="LLM提供商: openai/qwen/local"
    )
    LLM_API_KEY: str | None = Field(default=None, description="LLM API密钥")
    LLM_API_BASE: str | None = Field(default=None, description="LLM API基础URL")
    LLM_MODEL: str = Field(default="gpt-4o", description="LLM模型名称")
    LLM_TEMPERATURE: float = Field(default=0.7, description="LLM温度参数")
    LLM_MAX_TOKENS: int = Field(default=2048, description="LLM最大Token数")

    # === Embedding配置 ===
    EMBEDDING_PROVIDER: str = Field(
        default="openai", description="Embedding提供商: openai/local"
    )
    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small", description="Embedding模型"
    )
    EMBEDDING_API_KEY: str | None = Field(default=None, description="Embedding API密钥")
    EMBEDDING_API_BASE: str | None = Field(
        default=None, description="Embedding API基础URL"
    )

    # === RAG配置 ===
    RAG_TOP_K: int = Field(default=5, description="检索返回文档数")
    RAG_SIMILARITY_THRESHOLD: float = Field(default=0.7, description="相似度阈值")
    RAG_CHUNK_SIZE: int = Field(default=500, description="文本分块大小")
    RAG_CHUNK_OVERLAP: int = Field(default=50, description="文本分块重叠")

    # === CORS配置 ===
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="允许跨域来源",
    )

    # === 日志配置 ===
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """解析CORS来源字符串为列表"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # 尝试 JSON 数组格式，如 ["http://localhost:5173"]
            if v.startswith("["):
                import json

                try:
                    return cast(list[str], json.loads(v))
                except json.JSONDecodeError:
                    pass
            # 逗号分隔格式
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return []

    @model_validator(mode="after")
    def _validate_production_security(self) -> Self:
        """生产环境安全校验：禁止使用默认 SECRET_KEY"""
        default_secret = "your-super-secret-key-change-in-production"  # nosec B105 -- 开发默认值,生产由环境变量覆盖
        if self.ENV == "production" and default_secret == self.SECRET_KEY:
            raise ValueError(
                "生产环境(ENV=production)必须设置非默认的 SECRET_KEY，"
                "请通过环境变量配置随机密钥"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """获取应用配置（单例模式）"""
    return Settings()


settings = get_settings()
