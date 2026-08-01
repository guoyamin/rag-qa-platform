## 变更摘要

**需求/任务:** worktree 代码自检与修复 + 集成测试 + E2E，达规范全部门禁（阶段1/2/3）
**模块:** 后端 services/models/schemas/core/api + 前端 views/api
**影响范围:** 后端约 50 文件，前端约 15 文件
**AI生成:** 是
**生成日期:** 2026-08-01
**预计Review时间:** 40 分钟

### 阶段1：单元测试 + 类型 + 安全门禁
- 后端单元测试：116 -> 539 passed（补 ~423 个 service 层测试）
- 前端单元测试：23 -> 107 passed（补 84 个 view 测试）
- mypy --strict 0 / ruff 0 / bandit 0
- 后端 coverage 92%（omit api/main，api 由集成测试覆盖）
- 前端 coverage 79.69%

### 阶段2：集成测试
- 新建 tests/integration/（conftest + 9 个 api 集成测试）
- 190 passed（auth/model/chat/health/stats/template/user/knowledge/document）
- TestClient + SQLite 内存库 + mock 外部依赖

### 阶段3：E2E
- 7 passed（login 2 + chat 2 + models 3）
- playwright chromium
- 范围：已实现功能（登录、纯聊天、模型管理）

### 代码 bug 修复（重点 Review）
- auth_service.py：漏 datetime 导入（登录 500 根因）
- llm_manager.py：漏 asyncio + 4 方法锁异步化（asyncio.Lock 用在同步方法）
- db/base.py：删除重复的空 Base 定义（25 个 mypy attr-defined 根因）
- circuit_breaker_service.py：漏 datetime + CircuitBreakerState 导入路径错（运行时 ImportError，熔断不可用）
- model_service.py：create 默认 ACTIVE + 预热容错（503 根因）
- ab_test_service.py：MD5 流量分流哈希加 usedforsecurity=False
- 前端 request.ts：响应拦截器已解包但类型未改，补 UnwrappedAxios 类型声明
- 前端 models/index.vue：API 返回类型 + formData.id + 表格行类型

### 配置变更
- requirements.txt：补 apscheduler/hvac/aiosqlite/freezegun
- Dockerfile：pip install 换阿里云镜像（解决 pypi.org SSL 不稳）
- pyproject.toml：coverage omit api/main；ruff 配置迁移 [tool.ruff.lint]；删 mypy 无用 overrides
- .env：LLM 配 DeepSeek chat + 千问 embedding（1024维）；MILVUS_DIM=1536->1024
- milvus collection：新建 rag_qa_knowledge（1024维，COSINE 索引）
- 前端 .eslintrc.cjs（项目原本无配置）；vitest.config.ts 补 coverage thresholds
- 后端镜像重建（4 依赖烘焙进镜像，requirements 持久化）

### 自检结果
- [x] mypy --strict 0 错误
- [x] pytest 729 passed（539 单元 + 190 集成）
- [x] ruff 0 错误
- [x] bandit 0（High/Medium/Low 全清）
- [x] 后端 coverage 92%（≥80%）
- [x] vue-tsc --noEmit 0 错误
- [x] eslint 0 error
- [x] vitest 107 passed / coverage 79.69%（≥70%）
- [x] E2E 7 passed
- [x] 后端镜像重建（4 依赖烘焙）

### 已确认事项
1. coverage omit api/main -- 认可（api 由集成测试覆盖，测试金字塔）
2. 前端 functions threshold 不强制 -- 认可（v8 对 Vue SFC 编译产物统计偏差）
3. requirements 重建镜像 -- 已完成
4. milvus 容器 -- 已在跑
5. LLM key -- DeepSeek chat + 千问 embedding 已配

### 已知功能缺口（不在本次范围）
- chat 前端 sendMessage 是 mock（setTimeout，未接后端 chat API/DeepSeek）
- documents/knowledge/users 前端是占位页（功能未实现）
- 上述功能的 E2E 暂缺，待功能实现后补

### Review 建议
- 重点关注：db/base.py 重复定义修复、llm_manager 锁异步化、circuit_breaker 导入路径 bug、model_service create 默认 ACTIVE+预热容错
- 可快速浏览：测试文件、类型注解、Dockerfile 阿里云镜像
