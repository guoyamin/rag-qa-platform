# 智能问答平台 - 部署文档

## 目录

- [环境准备](#环境准备)
- [Docker部署](#docker部署)
- [Kubernetes部署](#kubernetes部署)
- [配置说明](#配置说明)
- [监控与日志](#监控与日志)

## 环境准备

### 服务器要求

| 服务 | 最低配置 | 推荐配置 |
|------|---------|---------|
| 后端 | 2核4G | 4核8G |
| 前端 | 1核2G | 2核4G |
| PostgreSQL | 2核4G | 4核8G |
| Milvus | 4核8G | 8核16G |
| Redis | 1核2G | 2核4G |

### 依赖软件

- Docker 24.0+
- Docker Compose 2.20+
- (可选) Kubernetes 1.28+

## Docker部署

### 1. 准备配置文件

```bash
cp backend/.env.example backend/.env
# 编辑 .env 配置API密钥和数据库连接
```

### 2. 启动服务

```bash
docker-compose up -d

# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 3. 初始化数据

```bash
# 创建管理员用户
docker-compose exec backend python -c "
from app.db.session import AsyncSessionLocal
from app.services.auth_service import AuthService
from app.schemas import UserCreate
import asyncio

async def init():
    async with AsyncSessionLocal() as db:
        auth = AuthService(db)
        await auth.create_local_user(UserCreate(
            username='admin',
            password='Admin@123',
            display_name='系统管理员',
            role='super_admin'
        ))

asyncio.run(init())
"
```

## 配置说明

### 关键环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL连接 | `postgresql+asyncpg://user:pass@host/db` |
| `REDIS_URL` | Redis连接 | `redis://host:6379/0` |
| `MILVUS_HOST` | Milvus主机 | `milvus` |
| `SECRET_KEY` | JWT密钥 | 随机字符串 |
| `LLM_PROVIDER` | LLM提供商 | `openai` / `local` |
| `LLM_API_KEY` | LLM API密钥 | `sk-...` |
| `LLM_MODEL` | LLM模型 | `gpt-4o` |
| `AUTH_MODE` | 认证模式 | `local` / `ldap` / `hybrid` |

### LDAP配置

```bash
AUTH_MODE=hybrid
LDAP_SERVER=ldap.company.com
LDAP_BASE_DN=dc=company,dc=com
LDAP_BIND_DN=cn=admin,dc=company,dc=com
LDAP_BIND_PASSWORD=secret
```

## 监控与日志

### 健康检查

```bash
curl http://localhost:8000/health
```

### 日志收集

推荐使用 ELK Stack 或 Loki + Grafana：

```yaml
# docker-compose.logging.yml
services:
  loki:
    image: grafana/loki:2.9.0
    ports:
      - "3100:3100"
  
  promtail:
    image: grafana/promtail:2.9.0
    volumes:
      - /var/log:/var/log
      - ./promtail-config.yml:/etc/promtail/config.yml
```

### 性能监控

推荐使用 Prometheus + Grafana：

```python
# 后端集成 prometheus-client
from prometheus_client import Counter, Histogram

request_count = Counter('http_requests_total', 'Total requests')
request_latency = Histogram('http_request_duration_seconds', 'Request latency')
```
