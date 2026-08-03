# 智能问答平台

基于 RAG（检索增强生成）技术的智能问答系统，为企业职工提供企业制度、业务流程、产品文档等方面的智能问答服务。

## 技术架构

### 后端 (backend/)
| 技术 | 用途 |
|------|------|
| **FastAPI** | Web框架，高性能异步API |
| **SQLAlchemy 2.0** | ORM + 异步数据库操作 |
| **PostgreSQL** | 业务数据存储 |
| **Milvus** | 向量数据库，存储文档Embedding |
| **Redis** | 缓存、会话管理 |
| **LangChain** | RAG流程编排 |
| **Pytest** | 单元测试和集成测试 |

### 前端 (frontend/)
| 技术 | 用途 |
|------|------|
| **Vue 3** | 前端框架，Composition API |
| **Element Plus** | UI组件库 |
| **Pinia** | 状态管理 |
| **TypeScript** | 类型安全 |
| **Vite** | 构建工具 |
| **Vitest** | 单元测试 |
| **Playwright** | 端到端测试 |

### 基础设施
| 技术 | 用途 |
|------|------|
| **Docker** | 容器化部署 |
| **Docker Compose** | 本地开发环境编排 |

## 项目结构

```
rag-qa-platform/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/v1/            # API路由 (RESTful)
│   │   ├── core/              # 核心配置、安全、异常
│   │   ├── db/                # 数据库模型和会话
│   │   ├── models/            # SQLAlchemy数据模型
│   │   ├── schemas/           # Pydantic验证模型
│   │   ├── services/          # 业务逻辑层
│   │   ├── rag/               # RAG核心模块
│   │   ├── llm/               # LLM适配层
│   │   └── main.py            # FastAPI入口
│   ├── tests/                 # 测试代码
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   # 前端服务
│   ├── src/
│   │   ├── api/               # API封装
│   │   ├── components/        # 组件
│   │   ├── views/             # 页面
│   │   ├── router/            # 路由
│   │   ├── stores/            # Pinia状态管理
│   │   └── types/             # TypeScript类型
│   ├── tests/                 # 测试代码
│   └── Dockerfile
└── README.md
```

## 快速开始

### 环境要求
- Docker & Docker Compose
- Node.js 20+ (前端开发)
- Python 3.11+ (后端开发)

### 1. 使用 Docker Compose 启动（推荐）

```bash
# 克隆项目
git clone <项目地址>
cd rag-qa-platform

# 复制环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，配置LLM API密钥

# 启动开发栈（make dev → deployment/docker-compose.dev.yml：后端+前端+PG+Redis+Milvus）
make dev

# 访问
# 前端: http://localhost:5173
# 后端API文档: http://localhost:8000/api/docs
```

### 2. 本地开发

#### 后端开发

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 启动服务
uvicorn app.main:app --reload --port 8000
```

#### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 访问 http://localhost:5173
```

## 核心功能

### 智能问答
- 基于RAG技术，结合向量检索和大语言模型
- 支持流式输出，实时显示回答
- 引用来源展示，回答有据可查
- 支持指定知识库范围检索

### 知识库管理
- 多知识库管理
- 支持PDF、Word、Excel、Markdown等文档上传
- 自动文档解析和向量化
- 文档分块和索引管理

### 用户认证
- 支持本地账号认证
- 支持LDAP/企业SSO对接
- 混合认证模式（本地+LDAP）
- JWT Token机制，支持Token刷新

### 权限管理
- 角色分级：超级管理员、管理员、业务用户、内部职工
- 菜单级权限控制
- API接口权限控制

## LLM适配层设计

系统设计了统一的LLM抽象层，支持多种模型接入：

| 模式 | 提供商 | 模型 |
|------|--------|------|
| 开发阶段 | OpenAI兼容API | GPT-4o / 通义千问 / 文心一言 |
| 部署阶段 | 私有化部署 | ChatGLM / Qwen / Baichuan |

通过修改环境变量即可切换，无需改动业务代码：
```bash
# 开发阶段（公有云API）
LLM_PROVIDER=openai
LLM_API_KEY=your-key
LLM_MODEL=gpt-4o

# 部署阶段（私有化）
LLM_PROVIDER=local
LLM_API_BASE=http://localhost:8000/v1
LLM_MODEL=chatglm3-6b
```

## 测试

### 后端测试
```bash
cd backend

# 运行所有测试
pytest

# 运行单元测试
pytest -m unit

# 运行集成测试
pytest -m integration

# 覆盖率报告
pytest --cov=app --cov-report=html
```

### 前端测试
```bash
cd frontend

# 单元测试
npm run test:unit

# 端到端测试
npm run test:e2e
```

## 部署建议

### 开发环境
用 `make dev` 一键启动开发栈（`deployment/docker-compose.dev.yml`），适合快速验证功能。

### 测试环境
- Kubernetes 部署
- 独立的数据库和向量数据库集群
- 配置监控和日志收集

### 生产环境
- 多实例部署保证高可用
- Milvus 集群模式
- PostgreSQL 主从复制
- Redis 哨兵/集群模式
- 私有化LLM部署（vLLM/Ollama）

## 安全考虑

1. **数据安全**：知识库数据敏感，生产环境必须私有化部署LLM
2. **访问控制**：JWT认证 + 角色权限控制
3. **审计日志**：所有操作记录可追溯
4. **HTTPS**：生产环境强制HTTPS
5. **密码策略**：最小长度8位， bcrypt加密存储

## 路线图

- [x] 项目架构搭建
- [x] 用户认证模块
- [x] RAG核心流程
- [x] 基础前端页面
- [ ] 文档解析与向量化
- [ ] 知识库管理完整功能
- [ ] 聊天历史管理
- [ ] 管理后台
- [ ] 性能监控
- [ ] 多轮对话优化

## 许可证

MIT License
