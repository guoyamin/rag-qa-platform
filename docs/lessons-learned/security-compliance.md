# 安全与规范

安全漏洞与编码规范违反，开发中容易疏忽。

## 1. `v-html` + marked 无清洗（XSS）

**问题**：聊天页用 `v-html="renderMarkdown(msg.content)"` 渲染 LLM 回复的 Markdown，`marked` 不清洗 HTML。RAG 上下文来自用户上传的文档，文档内 `<img onerror=...>` 等恶意脚本会被 LLM 原样输出并注入页面执行。

**后果**：XSS 漏洞，可窃取 token、执行任意脚本。

**教训**：任何 `v-html` 渲染不可信内容都必须清洗。

**如何避免**：
- `marked` + `DOMPurify` 清洗
- marked v13 移除了内置 sanitize，必须用 DOMPurify

```vue
<!-- ❌ 危险：无清洗 -->
<div v-html="marked(content)"></div>

<!-- ✅ 安全：DOMPurify 清洗 -->
<script setup>
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const renderMarkdown = (content: string) => {
  return DOMPurify.sanitize(marked.parse(content, { breaks: true }) as string)
}
</script>
<div v-html="renderMarkdown(msg.content)"></div>
```

## 2. `SECRET_KEY` 默认弱值无校验

**问题**：`config.py` 的 `SECRET_KEY` 默认 `"your-super-secret-key-change-in-production"`，`.env.example` 也用同值。生产环境若忘记设置，JWT 签名密钥可预测，可伪造任意 token。

**后果**：生产环境 JWT 可伪造，认证体系失效。

**教训**：敏感配置不能依赖默认值，必须启动校验。

**如何避免**：
- `model_validator` 校验生产环境不能用默认值
- `.env.example` 标注必须修改

```python
from pydantic import model_validator

class Settings(BaseSettings):
    SECRET_KEY: str = Field(default="your-super-secret-key-change-in-production")

    @model_validator(mode="after")
    def _validate_production_security(self):
        """生产环境安全校验：禁止使用默认 SECRET_KEY"""
        default_secret = "your-super-secret-key-change-in-production"
        if self.ENV == "production" and self.SECRET_KEY == default_secret:
            raise ValueError(
                "生产环境(ENV=production)必须设置非默认的 SECRET_KEY"
            )
        return self
```

## 3. Service 层直接抛 `HTTPException`

**问题**：`auth_service.py`（Service 层）大量 `raise HTTPException(status_code=401, detail=...)`。违反编码规范 5.2「Service 层禁止 HTTPException，只抛 BaseAppException 子类」。且 `HTTPException` 返回 `{detail}` 格式，与统一响应格式 `{code, message, data}` 不一致。

**后果**：响应格式不统一（前端 401 拿到 `{detail}`，业务错误拿到 `{code, message}`）；违反分层规范。

**教训**：Service 层只抛业务异常，HTTPException 仅在 API 层转换。

**如何避免**：
- Service 层抛 `BaseAppException` 子类（携带 `http_status` + `code`）
- 异常 handler 按异常类型返回正确状态码 + 统一格式
- `HTTPExceptions`（HTTPException 实例）仅用于 API 依赖层（deps）

```python
# ❌ 错误：Service 层抛 HTTPException
raise HTTPException(status_code=401, detail="用户名或密码错误")

# ✅ 正确：Service 层抛业务异常
from app.core.exceptions import AuthenticationError

raise AuthenticationError("用户名或密码错误")

# 异常类携带 http_status
class AuthenticationError(BaseAppException):
    http_status = 401
    def __init__(self, message="认证失败"):
        super().__init__(message=message, code="AUTHENTICATION_ERROR")

# main.py：handler 按异常类型返回状态码 + 统一格式
@app.exception_handler(BaseAppException)
async def app_exception_handler(request, exc: BaseAppException):
    return ORJSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message},
    )
```
