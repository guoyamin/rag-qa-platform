# Services 模块 AGENTS

> 模块资产详见 `docs/modules/services.md`（先读，含 15 service 分组与协作链）。

## 加新 service 必须遵守

- 文件命名 `xxx_service.py`，类名 `XxxService`
- 构造函数接 `db: AsyncSession`；服务间依赖在构造时 wire（如 `self.api_key_service = ApiKeyService(db)`）
- 单例类（如 `LLMManager`）用 `get_instance()`
- 按域归位：智能路由 / 模型管理 / 可靠性 / 成本 / 认证鉴权 / 基础设施（见 services.md）

## 硬约束

- **异常**：只抛 `BaseAppException` 子类（见 `backend/AGENTS.md`），不抛 `HTTPException`
- **模型实例改动**：必须经 `ModelService`（它同步 `LLMManager` 缓存：create 预热 / update·toggle reload / delete remove）。**DB 是真相源，LLMManager 是缓存——别绕过 ModelService 直接改 DB**
- **密钥**：必须经 `VaultClient`（被 `ApiKeyService` 封装），别明文存库
- **路由依赖熔断**：`RouterService`/`ABTestService` 调 LLM 前必经 `CircuitBreakerService.check_availability`，扩展别破坏这个契约
- 日志用 `structlog`，事件式命名
