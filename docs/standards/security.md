# 智能问答平台

# 安全合规基线

**文档编号：** RAG-QA-STD-003  
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

1. [安全基线（不可妥协项）](#1-安全基线不可妥协项)
2. [数据分级](#2-数据分级)
3. [认证与授权规范](#3-认证与授权规范)
4. [输入安全](#4-输入安全)
5. [输出安全](#5-输出安全)
6. [日志与审计](#6-日志与审计)
7. [AI安全特别提醒](#7-ai安全特别提醒)
8. [安全检查清单](#8-安全检查清单)
9. [附录](#9-附录)

---

## 1. 安全基线（不可妥协项）

以下安全要求为强制基线，任何代码不得违反。违反即视为安全漏洞，必须立即修复。

| 编号 | 类别 | 要求 | 检查方式 | 严重级别 |
|------|------|------|----------|----------|
| SEC-001 | 认证 | 所有API（登录、注册、健康检查除外）必须认证 | 自动化扫描 | 阻断 |
| SEC-002 | 授权 | 管理员接口必须校验角色权限 | 代码Review | 阻断 |
| SEC-003 | 输入校验 | 所有用户输入必须校验类型和长度 | Pydantic/表单校验 | 阻断 |
| SEC-004 | SQL安全 | 禁止字符串拼接SQL语句 | ORM + bandit扫描 | 阻断 |
| SEC-005 | XSS防护 | 前端输出必须转义 | Vue默认转义 + 审查 | 高危 |
| SEC-006 | CSRF防护 | 使用Token机制防御 | 框架默认配置 | 高危 |
| SEC-007 | 密码存储 | 使用bcrypt加密，salt自动处理 | 代码审查 | 阻断 |
| SEC-008 | 敏感传输 | 生产环境强制HTTPS | 部署配置 | 阻断 |
| SEC-009 | 日志安全 | 日志中禁止输出Token、密码、身份证号 | 自定义规则扫描 | 高危 |
| SEC-010 | 文件上传 | 限制文件类型和大小，文件名消毒处理 | 代码审查 | 高危 |

### 1.1 基线执行规则

- **阻断级：** CI流水线自动检测，发现问题立即阻断合并
- **高危级：** 代码Review必查项，发现即要求修复
- 所有安全基线项须在代码合并前逐项确认

---

## 2. 数据分级

根据《数据分类分级管理办法》，本平台涉及的数据分级如下：

| 级别 | 标识 | 数据类型 | 处理要求 |
|------|------|----------|----------|
| **绝密** | 🔴 | 个人敏感账户信息、身份证号、银行卡号、手机号 | 数据不出内网；展示时必须脱敏；操作全量审计记录；传输必须加密 |
| **机密** | 🟠 | 内部政策文件（未公开版本）、员工个人信息、登录凭证 | 权限控制；操作留痕；传输加密；存储加密 |
| **内部** | 🟡 | 系统配置、操作日志、统计数据、聊天记录 | 登录后可见；按需授权；定期清理 |
| **公开** | 🟢 | 已公开的企业制度、办事指南、常见问题 | 无需认证；可对外提供；注意版本准确性 |

### 2.1 数据脱敏规则

| 数据类型 | 原始格式 | 脱敏后 | 使用场景 |
|----------|----------|--------|----------|
| 身份证号 | 310101199001011234 | 310101********1234 | 列表展示 |
| 手机号 | 13812345678 | 138****5678 | 列表展示 |
| 银行卡号 | 6222021234567890123 | 6222**********0123 | 列表展示 |
| 姓名 | 张三 | 张* | 列表展示 |
| 邮箱 | zhangsan@example.com | z****@example.com | 列表展示 |

**脱敏原则：** 列表展示必须脱敏，详情页按需授权后可展示完整信息。

### 2.2 数据访问控制矩阵

| 数据级别 | 普通职工 | 业务用户 | 管理员 | 超级管理员 |
|----------|----------|------------|--------|------------|
| 绝密 | ❌ 不可见 | ❌ 不可见 | 🔍 脱敏可见 | ✅ 完整可见 |
| 机密 | 🔍 脱敏可见 | 🔍 脱敏可见 | ✅ 完整可见 | ✅ 完整可见 |
| 内部 | ✅ 可见 | ✅ 可见 | ✅ 可见 | ✅ 完整可见 |
| 公开 | ✅ 可见 | ✅ 可见 | ✅ 可见 | ✅ 可见 |

---

## 3. 认证与授权规范

### 3.1 Token策略

| Token类型 | 有效期 | 用途 | 存储位置 |
|-----------|--------|------|----------|
| Access Token | 8小时 | API请求认证 | 前端内存（Pinia） |
| Refresh Token | 7天 | 刷新Access Token | HttpOnly Cookie |

**Token安全要求：**
- JWT使用HS256算法，密钥长度不少于256位
- Token Payload中不得包含敏感信息（密码、身份证号）
- Token过期后必须重新认证，禁止使用永不过期的Token
- 用户登出后Token加入黑名单（Redis），立即失效

### 3.2 密码策略

| 要求 | 规则 |
|------|------|
| 最小长度 | 8位 |
| 复杂度 | 必须包含字母+数字 |
| 历史密码 | 不得重复使用最近5次密码 |
| 加密算法 | bcrypt，cost factor ≥ 12 |
| 传输 | 必须HTTPS，禁止明文传输 |
| 锁定策略 | 连续5次失败锁定30分钟 |

### 3.3 权限检查规范

**双重校验原则：** 权限检查在API层和Service层各执行一次。

```python
# ✅ 正确：API层校验角色
@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_admin),  # API层校验
    db: AsyncSession = Depends(get_db),
):
    # Service层再次校验
    await user_service.delete_user(user_id, current_user)
    return ResponseBase(message="删除成功")

# ❌ 错误：仅在API层校验
@router.delete("/{user_id}")
async def delete_user(user_id: str):
    # 直接调用，Service层无校验
    await user_service.delete_user(user_id)
```

---

## 4. 输入安全

### 4.1 输入校验层级

| 层级 | 校验内容 | 工具/方式 |
|------|----------|-----------|
| 第一层：协议层 | HTTP方法、Content-Type | FastAPI框架 |
| 第二层：参数层 | 类型、长度、范围、格式 | Pydantic Schema |
| 第三层：业务层 | 业务规则、权限、状态 | Service层校验 |
| 第四层：数据层 | 外键约束、唯一性 | 数据库约束 |

### 4.2 常见注入防护

**SQL注入：**
- 必须使用ORM或参数化查询
- 禁止任何形式的字符串拼接SQL

```python
# ✅ 正确
result = await session.execute(
    select(User).where(User.username == username)
)

# ❌ 错误（绝对禁止）
query = f"SELECT * FROM users WHERE username = '{username}'"
```

**命令注入：**
- 禁止将用户输入传入系统命令
- 如需执行外部命令，使用白名单校验参数

**路径遍历：**
- 文件路径必须使用`os.path.abspath`规范化
- 校验路径是否在允许目录内

```python
# ✅ 正确
base_dir = "/app/uploads"
user_path = os.path.abspath(os.path.join(base_dir, filename))
if not user_path.startswith(base_dir):
    raise ValidationError("非法文件路径")

# ❌ 错误
with open(filename, "r") as f:  # 可能被利用读取/etc/passwd
    ...
```

---

## 5. 输出安全

### 5.1 错误响应规范

生产环境错误响应不得暴露以下信息：
- 堆栈跟踪（Stack Trace）
- 数据库结构信息
- 内部路径和文件名
- 第三方服务内部错误

```python
# ✅ 正确：生产环境统一错误响应
{
    "code": "SYSTEM_ERROR",
    "message": "系统繁忙，请稍后重试"
}

# ❌ 错误：暴露内部信息
{
    "error": "psycopg2.OperationalError: connection refused",
    "traceback": "File '/app/services/auth.py', line 42..."
}
```

### 5.2 响应头安全

```nginx
# Nginx配置示例
add_header X-Content-Type-Options nosniff;
add_header X-Frame-Options DENY;
add_header X-XSS-Protection "1; mode=block";
add_header Content-Security-Policy "default-src 'self'";
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
```

---

## 6. 日志与审计

### 6.1 日志分级

| 级别 | 用途 | 内容限制 |
|------|------|----------|
| DEBUG | 开发调试 | 可包含变量值，生产环境关闭 |
| INFO | 业务事件 | 用户行为、系统状态，不得含敏感信息 |
| WARNING | 异常情况 | 可恢复的错误，需关注 |
| ERROR | 系统错误 | 需人工介入的问题 |
| CRITICAL | 严重故障 | 立即告警 |

### 6.2 禁止记录的信息

日志中绝对禁止输出以下内容：
- 密码（明文或密文）
- JWT Token（完整或部分）
- 身份证号（完整或部分）
- 银行卡号
- 手机号（完整）
- API密钥
- 数据库连接字符串

```python
# ✅ 正确：日志中隐藏敏感信息
logger.info(f"用户登录: user_id={user.id}, ip={client_ip}")

# ❌ 错误：日志泄露敏感信息
logger.info(f"用户登录: username={username}, password={password}")
```

### 6.3 审计日志

以下操作必须记录审计日志：
- 用户登录/登出
- 密码修改
- 权限变更
- 敏感数据访问（绝密/机密级别）
- 数据删除操作
- 管理员操作

审计日志字段：
```json
{
    "timestamp": "2026-07-30T10:30:00+08:00",
    "user_id": "uuid",
    "username": "zhangsan",
    "action": "DELETE",
    "resource": "user:uuid",
    "result": "SUCCESS",
    "client_ip": "192.168.1.100",
    "user_agent": "Mozilla/5.0..."
}
```

---

## 7. AI安全特别提醒

AI生成代码时存在以下固有风险，须特别警惕。

### 7.1 AI常见安全风险

| 风险编号 | 风险 | 描述 | 对策 |
|----------|------|------|------|
| AI-SEC-001 | 不安全随机数 | 使用`random`模块生成安全令牌 | 强制使用`secrets`模块，bandit B311扫描 |
| AI-SEC-002 | 信息泄露 | 在错误响应中暴露堆栈跟踪或系统路径 | 生产环境关闭详细错误信息，统一错误响应格式 |
| AI-SEC-003 | 文件上传漏洞 | 未校验上传文件类型，允许上传可执行文件 | 白名单校验MIME类型，重命名上传文件 |
| AI-SEC-004 | 代码注入 | 使用`eval`、`exec`处理用户输入 | 禁止使用`eval`/`exec`，使用JSON解析替代 |
| AI-SEC-005 | 不安全的反序列化 | 使用pickle处理不可信数据 | 禁止使用pickle，使用JSON序列化 |
| AI-SEC-006 | 依赖漏洞 | 引入存在已知漏洞的第三方库 | CI阶段执行`safety check`和`npm audit` |
| AI-SEC-007 | 硬编码密钥 | 在代码中直接写入API密钥或密码 | detect-secrets扫描，禁止硬编码 |
| AI-SEC-008 | 不安全的CORS | 允许所有来源跨域访问 | 白名单配置CORS，禁止`*` |
| AI-SEC-009 | 敏感信息日志 | 在日志中打印Token、密码等 | 自定义规则扫描，日志审查 |
| AI-SEC-010 | 会话固定 | 登录后未重新生成Session ID | 认证成功后重新生成Token |

### 7.2 AI代码安全审查清单

AI提交代码前，必须逐项确认：

- [ ] 无硬编码密码、密钥、Token
- [ ] 无`eval`/`exec`/`pickle`使用
- [ ] 无字符串拼接SQL
- [ ] 文件上传有类型校验和大小限制
- [ ] 用户输入有长度和格式校验
- [ ] 错误响应不暴露内部信息
- [ ] 日志中无敏感信息
- [ ] 随机数使用`secrets`模块
- [ ] CORS配置为白名单
- [ ] 密码使用bcrypt加密

---

## 8. 安全检查清单

### 8.1 代码合并前安全审查

**审查者（用户）安全关注点：**

- [ ] 新增接口是否有认证要求
- [ ] 管理员接口是否有角色校验
- [ ] 用户输入是否有校验（类型、长度、格式）
- [ ] 数据库操作是否使用ORM/参数化查询
- [ ] 是否有硬编码的密钥、密码
- [ ] 文件上传是否有类型校验
- [ ] 错误处理是否可能泄露敏感信息
- [ ] 日志是否可能记录敏感信息
- [ ] 是否有不安全的随机数使用
- [ ] 第三方依赖是否有已知漏洞

### 8.2 上线前安全审查

- [ ] 生产环境配置已确认（DEBUG=False, SECRET_KEY已更换）
- [ ] HTTPS已配置
- [ ] 安全响应头已配置
- [ ] 数据库访问已限制（仅内网）
- [ ] 日志审计已启用
- [ ] 备份策略已确认
- [ ] 应急响应流程已确认

---

## 9. 附录

### 附录A：安全工具配置

**bandit配置（.bandit）：**

```yaml
skips: []
tests:
  - B105  # 硬编码密码
  - B106  # 硬编码密码函数参数
  - B107  # 硬编码密码默认参数
  - B301  # pickle
  - B307  # eval
  - B311  # random
  - B602  # subprocess_popen_with_shell
  - B605  # start_process_with_a_shell
  - B607  # start_process_with_partial_path
  - B608  # hardcoded_sql_expressions
exclude_dirs:
  - tests
  - migrations
```

**detect-secrets配置（.secrets.baseline）：**

```json
{
  "generated_at": "2026-07-30T00:00:00Z",
  "plugins_used": [
    {"name": "AWSKeyDetector"},
    {"name": "ArtifactoryDetector"},
    {"name": "Base64HighEntropyString", "limit": 4.5},
    {"name": "HexHighEntropyString", "limit": 3.0},
    {"name": "JwtTokenDetector"},
    {"name": "KeywordDetector", "keyword_exclude": ""},
    {"name": "PrivateKeyDetector"}
  ]
}
```

### 附录B：安全事件响应流程

```
发现安全漏洞
  │
  ├─→ 立即评估影响范围（数据泄露？权限绕过？）
  │
  ├─→ 高优先级修复（24小时内）
  │
  ├─→ 编写事后分析文档
  │       ├─→ 漏洞根因
  │       ├─→ 影响范围
  │       ├─→ 修复措施
  │       └─→ 预防措施
  │
  ├─→ 更新安全检查清单
  │
  └─→ 通报相关方
```

---

**文档结束**

---

*本文档为《编码规范》配套专项规范，与之共同构成项目规范体系。*
*安全基线项（SEC-001至SEC-010）为强制要求，任何代码不得违反。*
