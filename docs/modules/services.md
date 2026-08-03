# 业务服务层（Services）

> 路径：`backend/app/services/` · 15 个 service · 路由定位见 [module-map](../architecture/module-map.md) · AI 工作指令见 `backend/app/services/AGENTS.md`
>
> 本平台不只是 RAG 问答——`services/` 实现了完整的 **LLM 网关 / 智能路由**：多模型管理、复杂度路由、AB 测试、限流熔断、成本管控、健康监控。

## 按域分组（15 个 service）

### 🧭 智能路由域（流量入口）
| service | 职责 |
|---|---|
| `router_service.RouterService` | **智能路由入口** `route()`：按问题复杂度（关键词+长度→SIMPLE/MEDIUM/COMPLEX）匹配规则 → 每条规则查熔断器可用性 → 选第一个可用模型；全挂走降级（`policy.fallback_model_id`）。策略 BALANCED/QUALITY_FIRST/COST_FIRST。记 RouterLog |
| `ab_test_service.ABTestService` | A/B 测试：实验分组（ABExperiment/ABGroup/ABResult），流量分配；依赖 LLMManager + 熔断 |

### 🤖 模型管理域
| service | 职责 |
|---|---|
| `model_service.ModelService` | 模型实例 CRUD（ModelInstance）；**与 LLMManager 缓存联动**（create 预热 / update·toggle reload / delete remove）；依赖 ApiKeyService 取密钥；含 `compare_models` 多模型对比、`get_active_models` |
| `llm_manager.LLMManager` | **运行时管理器（单例 `get_instance()`）**：缓存所有 LLM 实例、热更新（reload）、线程安全。**DB 是真相源，它是缓存层** |
| `version_service.VersionService` | 模型版本管理 + 灰度发布（`ROLLOUT_STAGES=[10,30,50,100]`） |
| `template_service.TemplateService` | 预设提示词模板（PresetTemplate） |

### 🛡️ 可靠性域
| service | 职责 |
|---|---|
| `circuit_breaker_service.CircuitBreakerService` | 熔断器：CLOSED→OPEN→HALF_OPEN 状态机；`check_availability()` 被 RouterService/ABTestService 调用摘除故障模型 |
| `rate_limit_service.RateLimitService` | 限流：GLOBAL/USER/MODEL 三级（RateLimitConfig/Record）；`check_limit()` |
| `health_check_service.HealthCheckService` | 健康检查：QUICK(30s)/FULL(5min)/COMPREHENSIVE(15min) 三档，AsyncIOScheduler 定时探活 |

### 💰 成本域
| service | 职责 |
|---|---|
| `usage_stats_service.UsageStatsService` | 用量统计：`calculate_cost(model, in/out tokens)→Decimal`；ModelUsageLog/Daily |
| `cost_alert_service.CostAlertService` | 成本告警阈值（CostAlert） |

### 🔐 认证鉴权域
| service | 职责 |
|---|---|
| `auth_service.AuthService` | 用户认证（JWT/密码，配合 core/security） |
| `api_key_service.ApiKeyService` | API Key 管理：密钥经 VaultClient 加密存储（ApiKey），数据库只存 preview |
| `audit_service.AuditService` | 审计日志（AuditLog，AuditAction） |

### 🔧 基础设施域
| service | 职责 |
|---|---|
| `vault_client.VaultClient` | HashiCorp Vault 客户端：AppRole 认证 + KV Secret 读写（被 ApiKeyService 等使用） |

## 核心协作链

### 智能路由（选模型）
```
chat 请求 → RouterService.route(question)
  ① _classify_complexity()   关键词 + token 长度 → SIMPLE/MEDIUM/COMPLEX
  ② _get_policy(strategy)    取路由策略（默认 BALANCED）
  ③ _get_matching_rules()    匹配规则（complexity + active），按 priority 排序
  ④ 遍历规则 → CircuitBreakerService.check_availability(model_id)  跳过熔断模型
  ⑤ 选第一个可用模型；全挂 → _get_fallback_rule() 降级
  ⑥ 记 RouterLog（session/user/complexity/model/reason/latency/is_fallback）
  → 返回 {model_id, version_id, config_override, complexity, is_fallback}
```
> `route()` 只**选模型**，不实际调 LLM。实际调用由 chat 流程拿返回的 model_id 经 LLMManager 取实例。

### 模型实例 ↔ 缓存联动
```
ModelService.create()  → LLMManager.get_llm()      预热（失败不阻塞创建）
ModelService.update()  → LLMManager.reload_llm()   刷新缓存
ModelService.toggle()  → LLMManager.reload_llm()
ModelService.delete()  → LLMManager.remove_llm()   摘除缓存
```
> **DB 是真相源，LLMManager 是缓存**。改模型配置必须经 ModelService（它负责同步缓存），别绕过。

## 关键设计

- **单例 LLMManager**：所有模型实例集中管理（`get_instance()`），避免重复创建、支持运行时热更新
- **熔断贯穿路由**：RouterService 和 ABTestService 都依赖 CircuitBreakerService——故障模型自动摘除，全挂走降级
- **复杂度路由**：RouterService 用关键词 + token 长度启发式分类，**规则驱动**（RouterRule），非 ML 路由
- **密钥不落库明文**：ApiKeyService 经 VaultClient 存取，数据库只存 preview
- **structlog 结构化日志**：所有 service 用 `structlog.get_logger()`，事件式命名（`router_rule_created`、`model_status_toggled`）
- **依赖注入**：service 构造函数接 `db: AsyncSession`，服务间依赖构造时 wire（如 ModelService 内部 `ApiKeyService(db)` + `LLMManager.get_instance()`）

## 改这个模块时

- **加新业务能力** → 新建 `xxx_service.py`，构造函数接 `db: AsyncSession`，按域归位（上方分组）
- **动模型实例** → 必须经 ModelService（同步 LLMManager 缓存），别直接改 DB
- **动路由逻辑** → RouterService 是协作链核心，改 `_classify_complexity` / 规则匹配 / 降级 要考虑对熔断/限流的影响
- **加熔断/限流维度** → CircuitBreakerService / RateLimitService 已被路由依赖，扩展别破坏 `check_availability` / `check_limit` 契约
- **涉及密钥** → 必须经 VaultClient，别明文存库

## 范围说明

本文档是**总览**（每个 service 一句话 + 协作链 + 关键设计）。单个 service 的方法级深挖后续按需补 `services/<域>.md`。
