# 项目模块地图（中央路由表）

> 进来先看这张表。一行一模块，决定深入哪个再点链接。
> 模块详解见 [modules/](../modules/) · 架构叙事见 [README](README.md)

## 后端 `backend/app/`

### 核心模块（有详解）
| 模块 | 职责 | 入口 | 详解 |
|---|---|---|---|
| `rag/` | RAG 检索+生成编排 | `RAGPipeline.query()` | [rag.md](../modules/rag.md) |
| `llm/` | LLM 多后端适配 | `LLMFactory.create()` | [llm.md](../modules/llm.md) |
| `services/` | 业务核心（LLM 网关 / 智能路由） | `RouterService.route()` | [services.md](../modules/services.md) |

### API 层 `api/v1/`（前缀 `/api/v1`）
| 路由 | 职责 |
|---|---|
| auth | 认证（登录/JWT） |
| user | 用户管理 |
| chat | 智能问答（调 RAGPipeline） |
| knowledge | 知识库管理 |
| document | 文档上传/管理（ingestion） |
| model | 模型实例管理 |
| template | 预设模板 |
| stats | 用量统计 |
| health | 健康检查 |

> `template` 路由必须先于 `model` 注册：静态路径 `/models/templates` 要避免被 `/models/{model_id}` 参数路径捕获（见 `main.py`）。

### 基础设施
| 目录 | 职责 |
|---|---|
| `core/` | `config`（settings）、`security`（JWT/密码）、`exceptions`（`BaseAppException`→http_status+code） |
| `db/` | `base`（SQLAlchemy Base）、`session`（engine/session）、`migrations/`（alembic） |
| `models/` | 13 个 SQLAlchemy 模型：user / document / model_instance / model_version / ab_test / api_key / audit_log / cost_alert / health_log / rate_limit / router / usage_log / preset_template |
| `schemas/` | Pydantic 校验模型（当前仅 `model.py`，其余 schema 疑内联路由） |
| `scripts/` | `init_admin.py`（初始化管理员） |
| `tasks/` `utils/` | （当前空，预留） |

## 前端 `frontend/src/`

| 目录 | 职责 |
|---|---|
| `views/` | 页面（路由级）：login / chat / knowledge / documents / admin / layout |
| `components/` | 可复用组件（common + business） |
| `composables/` | 组合式函数 |
| `api/` | axios 封装 + 按模块请求函数 |
| `stores/` | Pinia 状态（含持久化） |
| `router/` | Vue Router（懒加载 + 鉴权守卫） |
| `types/` | TypeScript 类型（含 openapi-typescript 生成的 API 类型） |
| `utils/` `styles/` `assets/` | 工具 / 样式 / 静态资源 |

## 顶层目录
| 目录 | 职责 |
|---|---|
| `docs/` | 规范 / 架构 / 知识 / 手册（本文件所在） |
| `tools/` | `export-openapi.py`、`hooks/`、`generate-api-client.sh` |
| `.github/` | CI workflow、CODEOWNERS、dependabot、PR/Issue 模板 |
| `deployment/` | Dockerfile / docker-compose / nginx |

## 改一个东西从哪入手

- **加 API 端点**：`api/v1/<域>.py`（路由）→ `services/`（业务）→ `models/`（持久）→ `schemas/`（校验）→ `make gen-client`
- **加问答能力**：`rag/pipeline.py` + `retriever.py`
- **接新模型**：`llm/` 加适配器 + `services/llm_manager.py` 注册
- **改路由策略**：`services/router_service.py` + 相关 ADR（`docs/adr/`）
