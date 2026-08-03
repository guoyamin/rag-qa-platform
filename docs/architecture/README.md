# 架构设计文档

**文档编号：** RAG-QA-ARCH-001  
**版本号：** V1.0  
**编制部门：** 信息技术部  
**最后更新：** 2026年07月30日  

---

## 目录

1. [系统架构概览](#1-系统架构概览)
2. [技术栈总览](#2-技术栈总览)
3. [数据流图](#3-数据流图)
4. [模块划分](#4-模块划分)
5. [部署架构](#5-部署架构)
6. [相关文档](#6-相关文档)

---

## 1. 系统架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        客户端层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   内部职工   │  │  业务用户  │  │   管理员    │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
└─────────┼────────────────┼────────────────┼────────────────┘
          │                │                │
          └────────────────┴────────────────┘
                           │
                    ┌──────┴──────┐
                    │   Nginx     │  ← 前端静态资源 + 反向代理
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────┴──────┐  ┌──────┴──────┐  ┌─────┴──────┐
   │  Vue 3 SPA  │  │  FastAPI    │  │  API Docs  │
   │  (前端)      │  │  (后端API)  │  │  (Swagger) │
   └─────────────┘  └──────┬──────┘  └────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
   ┌──────┴──────┐  ┌──────┴──────┐  ┌─────┴──────┐
   │  PostgreSQL │  │   Milvus    │  │   Redis    │
   │  (业务数据)  │  │ (向量检索)  │  │ (缓存/会话) │
   └─────────────┘  └─────────────┘  └────────────┘
                           │
                    ┌──────┴──────┐
                    │   LLM服务   │
                    │ (API/私有化) │
                    └─────────────┘
```

---

## 2. 技术栈总览

### 2.1 后端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 运行环境 |
| FastAPI | 0.111 | Web框架 |
| SQLAlchemy | 2.0 | ORM |
| PostgreSQL | 16 | 业务数据存储 |
| Milvus | 2.4 | 向量数据库 |
| Redis | 7 | 缓存、会话管理 |
| LangChain | 0.2 | RAG流程编排 |
| Pytest | 8.x | 单元测试和集成测试 |

### 2.2 前端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4 | 前端框架 |
| Element Plus | 2.7 | UI组件库 |
| Pinia | 2.1 | 状态管理 |
| TypeScript | 5.5 | 类型安全 |
| Vite | 5.3 | 构建工具 |
| Vitest | 2.x | 单元测试 |
| Playwright | 1.45 | 端到端测试 |

### 2.3 基础设施

| 技术 | 用途 |
|------|------|
| Docker | 容器化部署 |
| Docker Compose | 本地开发环境编排 |
| Nginx | 反向代理、静态资源服务 |

---

## 3. 数据流图

### 3.1 智能问答流程

```
用户提问
  │
  ▼
┌─────────────┐
│  前端ChatUI  │
└──────┬──────┘
       │ POST /api/v1/chat/completions
       ▼
┌─────────────┐
│  RAGPipeline │
│  ├─ 1. 检索  │ → Milvus (向量搜索)
│  ├─ 2. 构建  │ → 组装上下文
│  ├─ 3. 生成  │ → LLM服务
│  └─ 4. 返回  │ → 回答 + 来源
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  前端展示    │
│  ├─ 流式输出 │
│  ├─ 引用来源 │
│  └─ 历史记录 │
└─────────────┘
```

### 3.2 文档处理流程

```
上传文档
  │
  ▼
┌─────────────┐
│  文档解析    │ → 提取文本 (PDF/Word/Excel/Markdown)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  文本分块    │ → 按策略切分 (大小/重叠)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Embedding  │ → 生成向量 (OpenAI / 本地模型)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  向量入库    │ → Milvus (存储 + 索引)
└─────────────┘
```

---

## 4. 模块划分

### 4.1 后端模块

> 模块资产详见 [modules/](../modules/)（rag / llm / services 详解），快速定位见 [module-map.md](module-map.md)。

```
backend/app/
├── api/v1/          ← API 路由层（HTTP 协议处理，前缀 /api/v1）
│   ├── auth.py        ← 认证（登录/JWT）
│   ├── user.py        ← 用户管理
│   ├── chat.py        ← 智能问答（调 RAGPipeline）
│   ├── knowledge.py   ← 知识库管理
│   ├── document.py    ← 文档上传/管理（ingestion）
│   ├── model.py       ← 模型实例管理
│   ├── template.py    ← 预设模板
│   ├── stats.py       ← 用量统计
│   └── health.py      ← 健康检查
├── core/            ← 核心基础设施
│   ├── config.py      ← 应用配置（settings）
│   ├── security.py    ← JWT / 密码加密
│   └── exceptions.py  ← 自定义异常（BaseAppException → http_status + code）
├── db/              ← 数据库
│   ├── base.py        ← SQLAlchemy 模型基类
│   ├── session.py     ← engine / session
│   └── migrations/    ← alembic 迁移
├── models/          ← SQLAlchemy 数据模型（13 个：user / document / model_instance /
│                    ←   model_version / ab_test / api_key / audit_log / cost_alert /
│                    ←   health_log / rate_limit / router / usage_log / preset_template）
├── schemas/         ← Pydantic 校验模型（当前仅 model.py，其余内联路由）
├── services/        ← 业务服务层（LLM 网关 / 智能路由核心，15 个 service）
│   ├── 智能路由域     ← router_service / ab_test_service
│   ├── 模型管理域     ← model_service / llm_manager / version_service / template_service
│   ├── 可靠性域       ← circuit_breaker / rate_limit / health_check
│   ├── 成本域         ← usage_stats / cost_alert
│   ├── 认证鉴权域     ← auth / api_key / audit
│   └── 基础设施域     ← vault_client
├── rag/             ← RAG 核心模块（详见 ../modules/rag.md）
│   ├── pipeline.py    ← RAG 流程编排（检索→构建→生成）
│   └── retriever.py   ← Milvus 向量检索
├── llm/             ← LLM 适配层（详见 ../modules/llm.md）
│   ├── base.py        ← 抽象接口 + LLMFactory
│   ├── openai_compatible.py ← OpenAI / 通义千问
│   └── local_model.py ← vLLM / TGI / Ollama
├── scripts/         ← 运维脚本（init_admin.py）
├── tasks/           ← （预留，当前空）
└── utils/           ← （预留，当前空）
```

> **注**：本平台不只是 RAG 问答，`services/` 层实现了完整的 **LLM 网关 / 智能路由**（多模型管理、复杂度路由、AB 测试、限流熔断、成本管控、健康监控）。详见 [modules/services.md](../modules/services.md)。

### 4.2 前端模块

```
frontend/src/
├── api/             ← API请求封装
│   ├── auth.ts      ← 认证API
│   ├── chat.ts      ← 问答API
│   └── request.ts   ← Axios封装
├── components/      ← 组件
│   ├── common/      ← 通用组件
│   └── business/    ← 业务组件
├── views/           ← 页面视图
│   ├── login/       ← 登录页
│   ├── chat/        ← 问答页
│   ├── knowledge/   ← 知识库页
│   ├── documents/   ← 文档管理页
│   ├── admin/       ← 管理后台
│   └── layout/      ← 布局页
├── router/          ← 路由配置
├── stores/          ← Pinia状态管理
│   └── auth.ts      ← 认证状态
├── types/           ← TypeScript类型
└── utils/           ← 工具函数
```

---

## 5. 部署架构

### 5.1 开发环境

```
Docker Compose
├── postgres    ← PostgreSQL 16
├── redis       ← Redis 7
├── milvus      ← Milvus 2.4 (含etcd + minio)
├── backend     ← FastAPI (热重载)
└── frontend    ← Nginx (Vue SPA)
```

### 5.2 生产环境（规划）

```
Kubernetes / Docker Swarm
├── Ingress Controller (Nginx)
├── Frontend Pods (Vue SPA)
├── Backend Pods (FastAPI, 多实例)
├── PostgreSQL (主从复制)
├── Redis Cluster
├── Milvus Cluster
└── LLM Service (私有化部署)
```

---

## 6. 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 模块地图 | `module-map.md` | 模块快速定位 |
| 模块资产 | `../modules/` | rag/llm/services 详解 |
| 编码规范 | `../standards/coding-standard.md` | 项目规范总纲 |
| API 契约 | `../standards/api-contract.md` | 接口设计规范 |
| 测试策略 | `../standards/testing.md` | 测试规范 |
| 安全基线 | `../standards/security.md` | 安全规范 |
| 知识库 | `../knowledge/` | 术语/ADR/复盘/AI协作 |
| 架构决策记录 | `../adr/` | ADR 索引及详情 |
| 部署文档 | `../runbooks/deployment.md` | 部署指南 |

---

**文档结束**

---

*本文档由AI辅助编制，须经项目负责人审核确认。*
