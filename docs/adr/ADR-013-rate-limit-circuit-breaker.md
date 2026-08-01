# ADR-013: 限流与熔断机制方案

**状态:** 已接受  
**日期:** 2026-08-01  
**决策主体:** 用户 + AI辅助

---

## 上下文

### 业务背景

模型管理功能需要保护 LLM 服务，防止：
- API 被刷（恶意请求）
- 单模型故障影响全局
- 超出预算的调用

### 技术约束

- 限流需要基于请求频率
- 熔断需要基于错误率
- 需要支持自动恢复

---

## 决策

> 我们决定实现 **限流与熔断机制**，支持请求限流和故障熔断。

---

## 限流策略

| 策略 | 说明 | 默认值 |
|------|------|--------|
| 全局限流 | 每分钟总调用次数 | 100 次 |
| 单用户限流 | 每分钟单用户调用 | 10 次 |
| 单模型限流 | 每分钟单模型调用 | 50 次 |

## 熔断策略

| 策略 | 说明 | 默认值 |
|------|------|--------|
| 错误阈值 | 连续失败 N 次触发熔断 | 5 次 |
| 熔断时长 | 熔断持续时间 | 30 秒 |
| 半开尝试 | 熔断后尝试恢复 | 每 30 秒 |
| 恢复阈值 | 连续成功 N 次恢复 | 3 次 |

---

## 数据库设计

```sql
-- 限流配置
CREATE TABLE rate_limit_configs (
    id VARCHAR(36) PRIMARY KEY,
    limit_type VARCHAR(30) NOT NULL COMMENT '限流类型：global/user/model',
    target_id VARCHAR(36) COMMENT '目标ID（模型ID/用户ID等）',
    max_requests INTEGER NOT NULL COMMENT '最大请求数',
    window_seconds INTEGER NOT NULL COMMENT '时间窗口（秒）',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_rate_limit_configs_type ON rate_limit_configs(limit_type);

COMMENT ON TABLE rate_limit_configs IS '限流配置';

-- 熔断状态
CREATE TABLE circuit_breaker_states (
    id VARCHAR(36) PRIMARY KEY,
    model_id VARCHAR(36) NOT NULL UNIQUE COMMENT '模型ID',
    state VARCHAR(20) NOT NULL DEFAULT 'closed' COMMENT '状态：closed/open/half_open',
    failure_count INTEGER DEFAULT 0 COMMENT '连续失败次数',
    success_count INTEGER DEFAULT 0 COMMENT '连续成功次数',
    last_failure_at TIMESTAMPTZ COMMENT '最后失败时间',
    opened_at TIMESTAMPTZ COMMENT '熔断开始时间',
    closed_at TIMESTAMPTZ COMMENT '熔断结束时间',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (model_id) REFERENCES model_instances(id) ON DELETE CASCADE
);

COMMENT ON TABLE circuit_breaker_states IS '熔断状态';

-- 限流记录
CREATE TABLE rate_limit_records (
    id VARCHAR(36) PRIMARY KEY,
    limit_type VARCHAR(30) NOT NULL COMMENT '限流类型',
    target_id VARCHAR(36) COMMENT '目标ID',
    request_count INTEGER DEFAULT 1 COMMENT '本次请求数',
    limited BOOLEAN DEFAULT FALSE COMMENT '是否被限流',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_rate_limit_records_created ON rate_limit_records(created_at);

COMMENT ON TABLE rate_limit_records IS '限流记录';
```

---

## 影响

### 对开发的影响
- 需要在 RAG Pipeline 中集成限流和熔断逻辑

### 对运维的影响
- 需要监控熔断状态
- 需要调整限流阈值

---

## 相关决策
- ADR-010: 多模型实例与运行时管理方案
