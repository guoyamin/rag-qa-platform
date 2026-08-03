# 智能问答平台

# 编码规范

**文档编号：** RAG-QA-STD-001  
**版本号：** V1.0  
**编制部门：** 信息技术部  
**发布日期：** 2026年07月30日  
**密级：** 内部公开  

---

**修订记录**

| 版本号 | 修订日期 | 修订内容 | 作者 | 审核人 |
|--------|----------|----------|------|--------|
| V1.0 | 2026-07-30 | 初始版本 | AI辅助 | 待确认 |

---

**分发范围：** 项目开发团队  
**保管部门：** 信息技术部  

---

## 目录

1. [目的与适用范围](#1-目的与适用范围)
2. [术语与定义](#2-术语与定义)
3. [规范体系架构](#3-规范体系架构)
4. [开发工作流规范](#4-开发工作流规范)
5. [编码风格规范](#5-编码风格规范)
   - 5.1 [外部规范引用](#51-外部规范引用)
   - 5.2 [项目特有补充规则](#52-项目特有补充规则)
   - 5.3 [工具链绑定](#53-工具链绑定)
   - 5.4 [AI生成代码的特殊检查](#54-ai生成代码的特殊检查)
6. [文档与知识管理](#6-文档与知识管理)
7. [规范维护机制](#7-规范维护机制)

---

## 1. 目的与适用范围

### 1.1 目的

本规范旨在建立智能问答平台（以下简称"本平台"）的统一技术标准与开发纪律，确保AI辅助生成代码的质量、安全性与可维护性，降低技术债务累积速度，保障项目可持续演进。

### 1.2 适用范围

本规范适用于以下范围的全部代码资产：

- 后端服务代码（Python / FastAPI）
- 前端应用代码（Vue 3 / TypeScript）
- 自动化测试代码（单元测试、集成测试、端到端测试）
- 基础设施配置（Docker、Docker Compose、Nginx）
- 数据库迁移脚本

### 1.3 约束条件

本规范与以下组织级规范存在层级关系：

| 规范层级 | 文件 | 关系 |
|----------|------|------|
| 组织级 | 《信息技术部代码安全基线》 | 本规范不得低于其要求 |
| 组织级 | 《数据分类分级管理办法》 | 数据处理须符合其分级要求 |
| 项目级 | 本文档 | 本项目的具体实施标准 |

当本规范与组织级规范存在冲突时，以组织级规范为准，并须在三个工作日内提交规范修订申请。

### 1.4 配套文档

本文档为项目规范体系的总纲，以下专项规范与之配套使用：

| 文档 | 文件路径 | 内容 |
|------|----------|------|
| 测试策略规范 | `docs/standards/testing.md` | 测试金字塔、用例规范、数据管理 |
| 安全合规基线 | `docs/standards/security.md` | 安全基线、数据分级、AI安全提醒 |
| AI协作规则 | `docs/knowledge/ai-collaboration.md` | 决策边界、变更清单、自检清单、协作节奏 |
| API 契约 | `docs/standards/api-contract.md` | 接口设计、错误码、分页、流式 |
| 架构决策记录 | `docs/adr/` | ADR索引及模板 |

---

## 2. 术语与定义

| 术语 | 英文 | 定义 |
|------|------|------|
| AI生成代码 | AI-Generated Code | 由大语言模型辅助编写或自动生成的源代码，包含代码注释中标注为AI生成的部分 |
| 架构决策记录 | ADR | Architecture Decision Record，用于记录项目关键架构决策的背景、方案与影响 |
| 质量门禁 | Quality Gate | 代码合并前必须通过的一系列自动化与人工检查 |
| RAG | Retrieval-Augmented Generation | 检索增强生成，本平台核心技术的简称 |
| 软删除 | Soft Delete | 数据记录保留但标记为已删除，不进行物理删除 |
| 流式输出 | Streaming | LLM响应以数据流形式逐字返回，而非等待完整响应 |

---

## 3. 规范体系架构

### 3.1 三层规范模型

本平台采用三层规范体系，各层职责分明：

**第一层：组织级规范**
- 制定主体：信息技术部技术委员会
- 更新周期：半年至一年
- 内容范围：跨项目的通用约定（代码风格、安全基线、Git提交格式）

**第二层：项目级规范**
- 制定主体：本项目负责人
- 更新周期：随项目演进动态调整
- 内容范围：本项目的特殊约定（技术选型理由、模块边界、接口契约）
- 承载文档：本文档及其配套专项规范、ADR

**第三层：临时约定**
- 制定主体：当前迭代开发者
- 更新周期：一个迭代周期
- 内容范围：针对当前迭代的特殊处理（技术债、临时方案、过渡期规则）
- 承载位置：迭代计划文档或任务卡片注释

### 3.2 规范冲突解决原则

当不同层级规范出现冲突时，按以下优先级执行：

组织级规范 > 项目级规范 > 临时约定

### 3.3 规范文档清单

```
docs/
├── standards/                  ← 规范层
│   ├── coding-standard.md      ← 本文档（总纲）
│   ├── api-contract.md         ← API 契约
│   ├── security.md             ← 安全合规
│   └── testing.md              ← 测试策略
├── knowledge/                  ← 知识层
│   ├── ai-collaboration.md     ← AI协作规则
│   ├── glossary.md             ← 业务术语
│   └── lessons-learned/        ← 经验复盘
├── runbooks/                   ← 操作手册
│   ├── deployment.md           ← 部署文档
│   └── harness-setup.md        ← Harness 平台设置
├── architecture/               ← 架构设计 + 模块地图(module-map.md)
├── modules/                    ← 模块资产（rag/llm/services 详解）
├── adr/                        ← 架构决策记录
│   ├── README.md
│   └── template.md
└── templates/                  ← 模板文件
    └── change-list.md
```

---

## 4. 开发工作流规范

### 4.1 分支模型

采用GitHub Flow简化版，适用于AI快速迭代场景：

```
main (保护分支，仅允许通过Pull Request合并)
  │
  ├── feature/login-page
  ├── feature/rag-retriever
  ├── fix/auth-token-refresh
  └── refactor/user-service
```

**分支命名规则：**

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feature/` | 新功能开发 | `feature/ldap-auth` |
| `fix/` | 缺陷修复 | `fix/login-redirect-loop` |
| `refactor/` | 代码重构 | `refactor/user-service` |
| `docs/` | 文档更新 | `docs/api-examples` |
| `chore/` | 构建/工具变更 | `chore/ci-pipeline` |

命名格式：`前缀/简短描述`，全部小写，单词间用连字符分隔，不得超过50个字符。

### 4.2 迭代节奏

| 活动 | 触发条件 | 参与方 | 产出物 |
|------|----------|--------|--------|
| 需求对齐 | 迭代开始时 | 用户 + AI | 验收标准确认 |
| 技术方案设计 | 需求对齐后 | AI | ADR草案 / 技术方案文档 |
| 方案确认 | 技术方案产出后 | 用户 | 确认意见或修改要求 |
| 代码实现 | 方案确认后 | AI | 源代码 + 测试代码 |
| AI自检 | 代码完成后 | AI | 自检报告 |
| 用户Review | AI自检通过后 | 用户 | Review意见 |
| AI修复 | Review意见明确后 | AI | 修复后的代码 |
| 合并验收 | 修复完成后 | 用户 | 合并到main分支 |

### 4.3 提交信息规范

提交信息采用结构化格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type取值：**

| 类型 | 用途 | 示例 |
|------|------|------|
| feat | 新功能 | `feat(auth): 实现LDAP统一认证` |
| fix | 缺陷修复 | `fix(api): 修复Token刷新失效问题` |
| refactor | 代码重构 | `refactor(rag): 提取检索逻辑到独立模块` |
| test | 测试相关 | `test(auth): 补充LDAP认证单元测试` |
| docs | 文档更新 | `docs(api): 更新登录接口说明` |
| chore | 构建/工具 | `chore(ci): 添加mypy类型检查` |
| perf | 性能优化 | `perf(db): 优化用户查询索引` |
| security | 安全修复 | `security(auth): 修复JWT密钥泄露风险` |

**Scope取值：** 对应模块名称（auth、rag、chat、kb、doc、user、ci等）。

**Subject规则：**
- 不超过50个字符
- 使用祈使句现在时（"添加"而非"添加了"）
- 首字母小写，末尾不加句号

**Body规则：**
- 每行不超过72个字符
- 说明"为什么做"而非"做了什么"
- 可以包含变更的动机、与之前行为的对比

**Footer规则：**
- 引用关联的Issue或任务编号：`Closes #123`
- 标记破坏性变更：`BREAKING CHANGE: 接口响应字段调整`

**AI生成代码的提交补充：**

AI生成的代码提交须在Footer中标注：

```
Co-authored-by: Claude <ai-assistant>
AI-Generated: true
```

### 4.4 代码合并门禁

一个Pull Request必须满足以下条件方可合并：

**自动化门禁（CI流水线）：**

| 检查项 | 后端工具 | 前端工具 | 失败处理 |
|--------|----------|----------|----------|
| 类型检查 | mypy --strict | vue-tsc --noEmit | 阻塞合并 |
| 代码格式 | black / isort | prettier | 自动修复后重试 |
| 代码风格 | ruff | eslint | 阻塞合并 |
| 单元测试 | pytest | vitest | 阻塞合并 |
| 测试覆盖率 | pytest-cov | vitest | 不得低于基线 |
| 安全扫描 | bandit | npm audit | 阻塞合并 |
| 密钥泄露检测 | detect-secrets | detect-secrets | 阻塞合并 |

**人工门禁：**

- [ ] 业务逻辑符合需求及验收标准
- [ ] 关键路径有测试覆盖
- [ ] 涉及数据库变更时有迁移脚本（Alembic）
- [ ] API接口变更有文档更新
- [ ] 无硬编码敏感信息（密码、密钥、Token）
- [ ] 错误处理覆盖边界情况

---

## 5. 编码风格规范

### 5.1 外部规范引用

本项目编码风格以以下权威规范为基准，各规范优先级及冲突解决方式如下：

| 技术领域 | 引用规范 | 来源 | 优先级 |
|----------|----------|------|--------|
| Python 基础风格 | PEP 8 | Python官方 | 基准 |
| Python 工程实践 | Google Python Style Guide | Google | 补充 |
| Vue 组件 | Vue Style Guide | Vue官方 | 基准 |
| TypeScript 类型 | Google TypeScript Style Guide | Google | 补充 |
| JavaScript 语法 | Airbnb JavaScript Style Guide | Airbnb | 补充 |
| REST API 设计 | Microsoft REST API Guidelines | Microsoft | 基准 |
| 云原生架构 | 12-Factor App | Heroku | 架构指导 |

**冲突解决原则：**
- 外部规范之间冲突时，以"本项目补充规则"为准
- 补充规则未覆盖时，以上表"优先级"为准（基准 > 补充）
- 所有外部规范未覆盖或与本项目冲突的领域，以本文档"项目特有补充规则"为准

### 5.2 项目特有补充规则

外部规范未覆盖或与本项目冲突的规则，必须在项目规范中明确写出。以下为本项目补充规则：

#### Python / FastAPI 补充规则

| 规则 | 说明 | 来源冲突 |
|------|------|----------|
| 强制类型注解 | 所有函数参数和返回值必须有类型注解 | PEP 8 不强制 |
| 行长度 88 | 代码行长度上限 88 字符 | PEP 8 推荐 79，Google 推荐 80 |
| Service层禁止HTTPException | Service 层只允许抛 BaseAppException 子类，HTTPException 仅在 API 层转换 | 外部规范未覆盖 |
| 导入顺序 | 标准库 → 第三方 → 本项目（绝对导入） | isort profile=black 自动处理 |
| 函数长度 ≤50 行 | 超过 50 行必须拆分 | ruff 不检查，人工审查 |
| 嵌套层级 ≤4 层 | 过深则提取函数 | 外部规范未量化 |
| 禁止 print | 统一使用 structlog 结构化日志 | 外部规范未禁止 |
| Pydantic Schema 必用 | API 入参出参必须用 Pydantic 模型，禁止裸 dict | FastAPI 推荐，本项目强制 |
| f-string 统一 | 字符串格式化统一使用 f-string，禁止 % 格式化和 .format() | Python 3.11+ |

#### Vue / TypeScript 补充规则

| 规则 | 说明 | 来源冲突 |
|------|------|----------|
| Composition API 强制 | 所有组件必须使用 Composition API，禁止 Options API | Vue Style Guide 允许两者 |
| 组件 PascalCase | 组件文件名与组件名一致，使用 PascalCase | Vue Style Guide 推荐 |
| Props 接口定义 | 必须有 TypeScript 接口 + 默认值 | 外部规范未强制 |
| API 封装隔离 | 禁止组件中直接写 axios，必须通过 api/ 目录封装 | 外部规范未覆盖 |
| 样式 scoped 强制 | 组件样式必须 scoped，全局样式只在 styles/ 目录 | 外部规范未强制 |
| Store 按领域拆分 | 禁止大全局 Store，按业务领域拆分 Pinia Store | Pinia 推荐 |

#### REST API 补充规则

| 规则 | 说明 |
|------|------|
| 统一响应格式 | `{"code": "SUCCESS", "message": "...", "data": {}}` |
| 错误码分离 | 业务错误用 code 字段，HTTP 状态码只表协议层 |
| URL 规范 | 全小写、名词复数、连字符：`/api/v1/chat-sessions` |
| 分页参数 | `page` / `page_size`，默认 20，最大 100 |

#### 数据库设计补充规则

| 规则 | 说明 |
|------|------|
| 表名 | 小写下划线复数：`users`、`chat_messages` |
| 时间字段 | `created_at`、`updated_at` 必须存在 |
| 软删除 | `is_deleted` 字段，禁止物理删除 |
| 迁移 | 必须通过 Alembic 生成，禁止手写 DDL |

### 5.3 工具链绑定

外部规范中已由工具自动覆盖的规则，不在项目规范中重复描述。开发者只需运行工具即可，无需记忆。

#### 后端工具链

| 工具 | 覆盖的外部规范 | 配置 |
|------|---------------|------|
| black | PEP 8 代码格式（空格、换行、引号） | `line-length = 88` |
| isort | PEP 8 / Google 导入排序 | `profile = black` |
| ruff | PEP 8 风格、未使用变量、未定义名称 | `select = ["E", "W", "F", "I"]` |
| mypy | 类型注解检查 | `--strict` |

**pyproject.toml 配置：**

```toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.ruff]
line-length = 88
select = ["E", "W", "F", "I"]
```

**快捷命令：**

```bash
make lint      # black + isort + ruff + mypy
make test      # pytest --cov
make security  # bandit + detect-secrets
```

#### 前端工具链

| 工具 | 覆盖的外部规范 | 配置 |
|------|---------------|------|
| prettier | 代码格式 | `.prettierrc` |
| eslint | Vue Style Guide + Airbnb JS | `@vue/eslint-config` |
| vue-tsc | TypeScript 类型检查 | `--noEmit` |

**.prettierrc 配置：**

```json
{
  "semi": false,
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100
}
```

**快捷命令：**

```json
"lint": "eslint . --fix && prettier --write \"src/**/*\"",
"type-check": "vue-tsc --noEmit",
"test:unit": "vitest"
```

#### CI 流水线

```
Push/PR
  │
  ├─→ black check
  ├─→ isort check
  ├─→ ruff check
  ├─→ mypy --strict
  ├─→ pytest --cov (≥80%)
  ├─→ bandit
  ├─→ detect-secrets
  ├─→ 前端: eslint
  ├─→ 前端: vue-tsc --noEmit
  ├─→ 前端: vitest
  │
  └─→ 全部通过 → 允许合并
```

#### IDE 绑定

**VS Code 推荐配置：**

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "ms-python.black-formatter",
  "python.analysis.typeCheckingMode": "strict",
  "eslint.format.enable": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  }
}
```

### 5.4 核心原则总结

| 外部规范已覆盖 | 项目规范只写"引用声明"，工具自动执行 |
|---------------|-----------------------------------|
| 外部规范未覆盖 | 项目规范必须明确写出具体规则 |
| 外部规范冲突 | 项目规范必须明确优先级和取舍 |

**团队成员只需记住：**
1. 运行 `make lint` 自动格式化并检查
2. 超出工具覆盖范围的规则，以本文档 5.2 节为准
3. 所有规则冲突时，以"项目特有补充规则"为最终依据

### 5.4 AI生成代码的特殊检查

AI生成代码存在特定风险，增加以下专项检查，作为工具链覆盖的补充：

| 检查项 | 风险描述 | 检查方式 |
|--------|----------|----------|
| 硬编码密钥 | AI可能在示例代码中生成临时密钥并遗留 | detect-secrets扫描 |
| 调试代码残留 | AI可能在代码中遗留`print`、`debugger` | 自定义脚本扫描 |
| SQL注入 | AI可能写出字符串拼接SQL | bandit B608 |
| 不安全随机数 | AI可能使用`random`而非`secrets` | bandit B311 |
| 敏感信息日志 | AI可能在日志中打印Token、密码 | 自定义规则扫描 |
| 依赖安全 | AI引入的依赖是否有已知漏洞 | safety check / npm audit |
| 路径遍历 | AI可能未校验文件路径 | bandit B607 |
| 命令注入 | AI可能拼接用户输入到系统命令 | bandit B605 |

---

## 5.5 前端设计规范（Art Design Pro 风格）

前端页面参照 [Art Design Pro](https://github.com/Daymychen/art-design-pro) 设计语言，采用现代简约 + 玻璃拟态 + 渐变风格。保留 Element Plus，通过 CSS 主题定制实现。

### 5.5.1 配色规范

主色采用蓝紫渐变（品牌蓝基底 + Art Design Pro 蓝紫）：

| 用途 | 颜色值 |
|------|--------|
| 主色渐变 | `linear-gradient(135deg, #1a5f9e 0%, #2d6cdf 50%, #5b6ef5 100%)` |
| 品牌深色（侧边栏） | `linear-gradient(180deg, #1a2342 0%, #1f2a52 100%)` |

全局 CSS 变量（亮/暗双主题，定义在 `App.vue`）：

| 变量 | 亮色 | 暗色 | 用途 |
|------|------|------|------|
| `--bg-page` | `#f0f2f5` | `#141414` | 页面背景 |
| `--bg-card` | `#fff` | `#1d1f27` | 卡片/容器背景 |
| `--bg-subtle` | `#f7f8fa` | `#25262e` | 次级背景（代码块、来源卡片） |
| `--text-primary` | `#1d2129` | `#e5e6eb` | 主文字 |
| `--text-secondary` | `#4e5969` | `#a8a8b3` | 次级文字 |
| `--text-tertiary` | `#86909c` | `#6b6e76` | 辅助文字 |
| `--border-color` | `#f0f2f5` | `#2a2d35` | 边框 |

**规则**：自定义样式必须使用上述 CSS 变量，禁止硬编码颜色值（`#fff` 等），确保暗色模式适配。

### 5.5.2 组件风格

| 元素 | 规范 |
|------|------|
| 圆角 | 卡片 `16px`，输入框/按钮 `10px`，菜单项 `10px`，小元素 `8px` |
| 阴影 | 卡片 `0 4px 20px rgba(0,0,0,0.06)`，按钮 `0 4px 12px rgba(45,108,223,0.3)` |
| 玻璃拟态 | `backdrop-filter: blur(20px)` + `rgba(255,255,255,0.1)` 背景（品牌区装饰、特性卡） |
| 渐变按钮 | 主按钮用 `linear-gradient(135deg, #2d6cdf, #5b6ef5)`，hover 上浮 `translateY(-2px)` + 阴影加深 |
| 输入框 | 圆角 10px，聚焦 `box-shadow: 0 0 0 2px rgba(45,108,223,0.3) inset` |

### 5.5.3 暗色模式

- **双主题切换**：使用 `@vueuse/core` 的 `useDark` + `useToggle`，顶栏放切换按钮（Sunny/Moon 图标）
- **持久化**：`useDark` 自动持久化到 localStorage
- **Element Plus**：`main.ts` 已 import `element-plus/theme-chalk/dark/css-vars.css`，组件自动适配
- **自定义样式**：通过 CSS 变量（5.5.1）适配，`html.dark` 切换变量值

### 5.5.4 布局规范

- **登录页**：左右分栏（左品牌区渐变 + 玻璃装饰圆 + 网格纹理，右表单卡片）
- **主布局**：深色侧边栏（渐变菜单高亮）+ 顶栏（面包屑 + 主题切换）+ 内容区
- **聊天页**：渐变用户气泡 + 白卡片助手气泡 + 卡片化输入区
- **字体**：`-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif`

### 5.5.5 动效

- 入场动画：`fadeInUp`（opacity 0->1, translateY 20px->0），时长 0.8s
- hover 微动效：`translateY(-2px)` + 阴影加深，过渡 0.2-0.3s
- 主题切换：背景/文字 `transition: 0.3s ease`

---

## 6. 文档与知识管理

### 6.1 文档分级体系

| 文档类型 | 存放路径 | 维护主体 | 更新时机 |
|----------|----------|----------|----------|
| 编码规范 | `docs/standards/coding-standard.md` | 用户 | 规范变更时 |
| 测试策略 | `docs/standards/testing.md` | 用户/AI | 测试策略变更时 |
| 安全基线 | `docs/standards/security.md` | 用户 | 安全策略变更时 |
| AI协作规则 | `docs/knowledge/ai-collaboration.md` | 用户 | 协作方式变更时 |
| 架构决策记录 | `docs/adr/` | AI | 做决策时 |
| 架构设计文档 | `docs/architecture/` | AI编写，用户确认 | 架构变更时 |
| API接口文档 | 自动生成 + `docs/standards/api-contract.md` | AI | 接口变更时 |
| 部署文档 | `docs/runbooks/deployment.md` | AI | 部署变更时 |
| 操作手册 | `docs/operation/` | 用户 | 功能上线时 |
| README | `README.md` | AI | 项目结构变更时 |
| 变更清单模板 | `docs/templates/change-list.md` | AI | 模板更新时 |

### 6.2 代码即文档原则

- 复杂业务逻辑必须有注释说明"为什么"，而非"做了什么"
- 公共API必须有完整的docstring/JSDoc，包含参数、返回值、异常说明
- 配置文件必须有注释说明每个配置项的用途和默认值
- 不写会过时的文档（如版本号、日期），此类信息通过代码或CI生成

### 6.3 API文档规范

- 基础文档：FastAPI自动生成的OpenAPI文档（Swagger UI / ReDoc）
- 补充文档：复杂业务接口在`docs/standards/api-contract.md`中补充说明
- 变更同步：接口变更（URL、请求/响应字段）必须同步更新文档
- 文档与代码一致性：以代码中的Pydantic Schema为唯一真相源

---

## 7. 规范维护机制

### 7.1 规范的动态性

规范不是一成不变的文件，须遵循以下原则：

- **可证伪性：** 每条规范必须能回答"如果不遵守，会有什么后果"
- **可调整性：** 如果一条规范经常被违反，说明规范本身有问题，须修订
- **可验证性：** 如果一条规范从未被违反，可能是无人遵守或检查不足，须评估

### 7.2 规范修订流程

```
发现问题（开发中遇到规范阻碍）
  │
  ├─→ 提出修改建议
  │       ├─→ 在PR中讨论
  │       └─→ 或单独开Issue
  │
  ├─→ 评估影响范围
  │       ├─→ 影响已有代码？需要重构吗？
  │       └─→ 影响开发效率？是提升还是降低？
  │
  ├─→ 决策
  │       ├─→ 简单修改：直接更新规范
  │       └─→ 重大修改：须经用户确认
  │
  ├─→ 更新规范文档
  │
  └─→ 必要时重构已有代码
```

### 7.3 规范修订记录

每次修订须在文档头部的"修订记录"表中登记，包含版本号、日期、修订内容、作者、审核人。

### 7.4 规范的初始化路线图

| 阶段 | 时间 | 内容 | 优先级 |
|------|------|------|--------|
| Week 1 | 项目启动 | 架构决策（ADR 001-005） | P0 |
| Week 1 | 项目启动 | Git工作流 + 分支策略 | P0 |
| Week 1 | 项目启动 | CI/CD流水线搭建 | P0 |
| Week 2 | 需求分析 | 接口设计规范 | P1 |
| Week 2 | 需求分析 | 编码规范微调 | P1 |
| Week 3 | 开发阶段 | 测试策略细化 | P1 |
| Week 3 | 开发阶段 | 安全基线检查清单 | P1 |
| 持续 | 全周期 | 文档同步更新 | P2 |

---

**文档结束**

---

*本文档由AI辅助编制，须经项目负责人审核确认后生效。*
*版本控制：本文档的修改须通过Pull Request进行，禁止直接修改。*
