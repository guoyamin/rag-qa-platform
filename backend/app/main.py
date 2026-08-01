"""
智能问答平台 - FastAPI主入口
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.v1 import (
    auth,
    chat,
    document,
    health,
    knowledge,
    model,
    stats,
    template,
    user,
)
from app.core.config import settings
from app.core.exceptions import BaseAppException
from app.db.base import Base
from app.db.session import engine

# 导入所有模型以确保 SQLAlchemy 能创建所有表
from app.models import (  # noqa: F401
    ABExperiment,
    ABGroup,
    ABResult,
    ApiKey,
    AuditLog,
    CircuitBreakerState,
    CostAlert,
    ModelHealthLog,
    ModelInstance,
    ModelUsageDaily,
    ModelUsageLog,
    ModelVersion,
    PresetTemplate,
    RateLimitConfig,
    RateLimitRecord,
    RouterLog,
    RouterPolicy,
    RouterRule,
    User,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理"""
    # 启动时执行
    # 开发环境自动建表便于调试；生产环境应通过 Alembic 迁移管理 schema
    if settings.DEBUG:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    yield

    # 关闭时执行
    await engine.dispose()


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="基于RAG的智能问答平台后端API",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        openapi_url="/api/openapi.json" if settings.DEBUG else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 异常处理：按异常类型返回对应 HTTP 状态码（协议层）+ 业务错误码
    @app.exception_handler(BaseAppException)
    async def app_exception_handler(
        request: Request, exc: BaseAppException
    ) -> ORJSONResponse:
        return ORJSONResponse(
            status_code=exc.http_status,
            content={"code": exc.code, "message": exc.message},
        )

    # 注册路由
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(user.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(knowledge.router, prefix="/api/v1")
    app.include_router(document.router, prefix="/api/v1")
    # template 路由前缀 /models/templates 为静态路径，必须先于 model 路由的
    # /models/{model_id} 参数路径注册，否则 GET /models/templates 会被后者捕获返回 404
    app.include_router(template.router, prefix="/api/v1")
    app.include_router(model.router, prefix="/api/v1")
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(stats.router, prefix="/api/v1")

    @app.get("/health", tags=["健康检查"])
    async def health_check() -> dict[str, str]:
        """健康检查接口"""
        return {"status": "healthy", "version": settings.APP_VERSION}

    @app.get("/", tags=["根路径"])
    async def root() -> dict[str, str]:
        """根路径"""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/api/docs",
        }

    return app


app = create_app()
