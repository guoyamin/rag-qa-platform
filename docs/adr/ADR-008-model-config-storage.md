# ADR-008: 模型配置存储方案

**状态:** 已接受  
**日期:** 2026-08-01  
**决策主体:** 用户 + AI辅助

---

## 上下文

### 业务背景

模型管理功能需要存储模型的配置信息，包括：
- 模型名称、类型、提供商
- API Endpoint、模型名称
- 调用参数（temperature、top_p、max_tokens 等）
- 启用/禁用状态

### 技术约束

- 配置需要持久化存储
- 支持热更新（修改后立即生效）
- 敏感信息需要加密存储

---

## 决策

> 我们决定使用 **PostgreSQL** 存储模型配置，采用 `model_instances` 表，使用 `model_type` 字段区分 LLM 和 Embedding。

---

## 数据库设计

```sql
CREATE TABLE model_instances (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '模型名称',
    model_type VARCHAR(20) NOT NULL COMMENT '模型类型：llm/embedding',
    provider VARCHAR(50) NOT NULL COMMENT '提供商：openai/anthropic/qwen',
    model_name VARCHAR(100) NOT NULL COMMENT '模型名称',
    api_endpoint VARCHAR(500) COMMENT 'API Endpoint（可选）',
    temperature DECIMAL(3,2) DEFAULT 0.7 COMMENT '温度参数',
    top_p DECIMAL(3,2) COMMENT 'Top P 参数',
    max_tokens INTEGER DEFAULT 2048 COMMENT '最大 Token 数',
    presence_penalty DECIMAL(3,2) DEFAULT 0 COMMENT '存在惩罚',
    frequency_penalty DECIMAL(3,2) DEFAULT 0 COMMENT '频率惩罚',
    system_prompt TEXT COMMENT '系统提示词',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    is_default BOOLEAN DEFAULT FALSE COMMENT '是否为默认模型',
    priority INTEGER DEFAULT 100 COMMENT '优先级（数字越小优先级越高）',
    created_by VARCHAR(36) COMMENT '创建人',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_model_instances_type ON model_instances(model_type);
CREATE INDEX idx_model_instances_active ON model_instances(is_active);
CREATE INDEX idx_model_instances_default ON model_instances(is_default);

COMMENT ON TABLE model_instances IS '模型实例配置表';
```

---

## 影响

### 对开发的影响
- 需要创建 ModelService 处理 CRUD
- 需要实现配置验证逻辑

### 对运维的影响
- 配置变更需要数据库操作
- 建议配合热更新机制使用

---

## 相关决策
- ADR-009: Vault 密钥管理方案
- ADR-010: 多模型管理方案
