# ADR-009: Vault 密钥管理方案

**状态:** 已接受  
**日期:** 2026-08-01  
**决策主体:** 用户 + AI辅助

---

## 上下文

### 业务背景

模型管理功能需要存储 API Key 等敏感信息：
- OpenAI API Key
- Anthropic API Key
- 其他第三方 API Key

### 技术约束

- 敏感信息不能明文存储
- 需要支持密钥轮换
- 需要审计密钥访问

---

## 决策

> 我们决定使用 **HashiCorp Vault** 进行密钥管理，采用 AppRole 认证方式。

---

## Vault 配置

### 1. 启用 AppRole 认证
```bash
vault auth enable approle
```

### 2. 创建角色
```bash
vault write auth/approle/role/model-service \
    token_ttl=24h \
    token_max_ttl=48h \
    policies="model-api-key-policy"
```

### 3. 创建策略
```hcl
# model-api-key-policy.hcl
path "secret/data/models/*" {
  capabilities = ["read"]
}

path "secret/metadata/models/*" {
  capabilities = ["list"]
}
```

### 4. 获取 Role ID 和 Secret ID
```bash
vault read auth/approle/role/model-service/role-id
vault read -f auth/approle/role/model-service/secret-id
```

---

## 客户端实现

```python
class VaultClient:
    """HashiCorp Vault 客户端"""
    
    def __init__(self, role_id: str, secret_id: str):
        self.vault_url = settings.VAULT_URL
        self.role_id = role_id
        self.secret_id = secret_id
        self._token = None
    
    async def get_token(self) -> str:
        """获取 Vault Token"""
        if self._token:
            return self._token
        
        response = requests.post(
            f"{self.vault_url}/v1/auth/approle/login",
            json={"role_id": self.role_id, "secret_id": self.secret_id}
        )
        response.raise_for_status()
        self._token = response.json()["auth"]["client_token"]
        return self._token
    
    async def get_secret(self, path: str) -> dict:
        """获取密钥"""
        token = await self.get_token()
        response = requests.get(
            f"{self.vault_url}/v1/secret/data/{path}",
            headers={"X-Vault-Token": token}
        )
        response.raise_for_status()
        return response.json()["data"]["data"]
    
    async def set_secret(self, path: str, data: dict):
        """设置密钥"""
        token = await self.get_token()
        response = requests.post(
            f"{self.vault_url}/v1/secret/data/{path}",
            headers={"X-Vault-Token": token},
            json={"data": data}
        )
        response.raise_for_status()
```

---

## 数据库设计

```sql
CREATE TABLE api_keys (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT 'Key 名称',
    provider VARCHAR(50) NOT NULL COMMENT '提供商',
    vault_path VARCHAR(200) NOT NULL COMMENT 'Vault 存储路径',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    expires_at TIMESTAMPTZ COMMENT '过期时间',
    last_used_at TIMESTAMPTZ COMMENT '最后使用时间',
    created_by VARCHAR(36) COMMENT '创建人',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_api_keys_provider ON api_keys(provider);
CREATE INDEX idx_api_keys_active ON api_keys(is_active);

COMMENT ON TABLE api_keys IS 'API Key 配置表（Vault 路径）';
```

---

## 影响

### 对开发的影响
- 需要部署 Vault 服务
- 需要配置 AppRole 凭证
- 需要实现 VaultClient

### 对运维的影响
- Vault 服务需要高可用部署
- 需要定期轮换 Secret ID
- 需要备份 Vault 数据
