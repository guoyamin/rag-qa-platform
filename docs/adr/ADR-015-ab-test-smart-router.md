# ADR-015: A/B 测试与智能路由方案

**状态:** 已接受  
**日期:** 2026-08-01  
**决策主体:** 用户 + AI辅助

---

## 上下文

### 业务背景

模型管理功能需要支持高级能力：
1. **A/B 测试**：对比不同模型效果，选择最优
2. **智能路由**：根据问题复杂度自动选择模型

### 技术约束

- A/B 测试需要分组和结果分析
- 智能路由需要问题复杂度判断
- 需要平衡成本和质量

---

## 决策

> 我们决定实现 **A/B 测试系统** 和 **智能路由系统**，支持模型对比实验和自动选模。

---

## A/B 测试设计

### 实验状态

| 状态 | 说明 |
|------|------|
| draft | 草稿，未启动 |
| running | 运行中 |
| paused | 已暂停 |
| completed | 已完成 |
| archived | 已归档 |

### 实验类型

| 类型 | 说明 |
|------|------|
| model_compare | 对比不同模型 |
| config_compare | 对比不同配置（温度、top_p 等） |
| prompt_compare | 对比不同提示词模板 |

---

## 数据库设计

```sql
-- A/B 实验表
CREATE TABLE ab_experiments (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '实验名称',
    description TEXT COMMENT '实验描述',
    experiment_type VARCHAR(30) NOT NULL COMMENT '实验类型',
    target_model_id VARCHAR(36) COMMENT '目标模型ID',
    status VARCHAR(20) NOT NULL DEFAULT 'draft' COMMENT '状态',
    start_at TIMESTAMPTZ COMMENT '开始时间',
    end_at TIMESTAMPTZ COMMENT '结束时间',
    winner_group_id VARCHAR(36) COMMENT '获胜分组ID',
    conclusion TEXT COMMENT '实验结论',
    created_by VARCHAR(36) COMMENT '创建人',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- A/B 分组配置
CREATE TABLE ab_groups (
    id VARCHAR(36) PRIMARY KEY,
    experiment_id VARCHAR(36) NOT NULL,
    name VARCHAR(100) NOT NULL COMMENT '分组名称',
    model_id VARCHAR(36) COMMENT '使用的模型ID',
    config_snapshot JSONB COMMENT '配置快照',
    traffic_percentage INTEGER NOT NULL DEFAULT 50 COMMENT '流量分配',
    skip_on_circuit_open BOOLEAN DEFAULT TRUE COMMENT '熔断时跳过',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (experiment_id) REFERENCES ab_experiments(id) ON DELETE CASCADE
);

-- A/B 结果表
CREATE TABLE ab_results (
    id VARCHAR(36) PRIMARY KEY,
    experiment_id VARCHAR(36) NOT NULL,
    group_id VARCHAR(36) NOT NULL,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    user_id VARCHAR(36) COMMENT '用户ID',
    question TEXT NOT NULL COMMENT '用户问题',
    answer TEXT COMMENT '模型回答',
    model_id VARCHAR(36) COMMENT '实际调用的模型ID',
    latency_ms INTEGER COMMENT '响应时间',
    input_tokens INTEGER COMMENT '输入Token数',
    output_tokens INTEGER COMMENT '输出Token数',
    is_success BOOLEAN DEFAULT TRUE COMMENT '是否成功',
    feedback_score INTEGER COMMENT '用户反馈：1-5',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (experiment_id) REFERENCES ab_experiments(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES ab_groups(id) ON DELETE CASCADE
);
```

---

## 智能路由设计

### 复杂度判断

| 维度 | 指标 | 说明 |
|------|------|------|
| Token 长度 | 问题字符数/预估 Token | 超过阈值判定为复杂 |
| 关键词检测 | 代码、数学、分析 | 含特定关键词判定为复杂 |
| 历史上下文 | 对话轮数 | 超过 N 轮判定为复杂 |
| 用户等级 | 普通用户/VIP | VIP 用户优先高质量 |

### 路由策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| cost_first | 成本优先 | 预算紧张时 |
| quality_first | 质量优先 | 重要场景 |
| balanced | 平衡模式 | 默认策略 |
| latency_first | 速度优先 | 实时响应要求高 |

### 路由规则表

```sql
-- 路由规则配置
CREATE TABLE router_rules (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '规则名称',
    complexity VARCHAR(20) NOT NULL COMMENT '复杂度：simple/medium/complex',
    priority INTEGER DEFAULT 100 COMMENT '优先级',
    target_model_id VARCHAR(36) NOT NULL COMMENT '目标模型ID',
    version_id VARCHAR(36) COMMENT '指定版本ID（空则使用活跃版本）',
    config_override JSONB COMMENT '配置覆盖',
    conditions JSONB NOT NULL COMMENT '触发条件',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_by VARCHAR(36) COMMENT '创建人',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 路由策略配置
CREATE TABLE router_policies (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '策略名称',
    strategy VARCHAR(30) NOT NULL COMMENT '策略类型',
    fallback_enabled BOOLEAN DEFAULT TRUE COMMENT '启用降级',
    fallback_model_id VARCHAR(36) COMMENT '降级模型ID',
    is_default BOOLEAN DEFAULT FALSE COMMENT '默认策略',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 路由日志
CREATE TABLE router_logs (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL COMMENT '会话ID',
    user_id VARCHAR(36) COMMENT '用户ID',
    question_preview VARCHAR(200) COMMENT '问题预览',
    complexity VARCHAR(20) COMMENT '判定复杂度',
    routed_model_id VARCHAR(36) COMMENT '路由到的模型',
    routing_reason TEXT COMMENT '路由原因',
    latency_ms INTEGER COMMENT '路由决策耗时',
    is_fallback BOOLEAN DEFAULT FALSE COMMENT '是否降级',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 补充设计 S1：A/B 测试缓存刷新

采纳获胜版本后，需要刷新 LLMManager 缓存：

```python
async def adopt_winner(self, experiment_id, winner_group_id, user):
    # ... 验证和更新逻辑 ...
    
    # 刷新缓存
    llm_manager = LLMManager.get_instance()
    llm_manager.reload_llm(experiment.target_model_id)
```

---

## 补充设计 S3：A/B 测试熔断检查

分流前检查熔断状态：

```python
def route_request(self, experiment, session_id):
    available_groups, total = self._filter_available_groups(groups)
    
    if not available_groups:
        raise ServiceUnavailableError("所有模型均不可用")
    
    # 动态调整流量比例
    hash_value = hash(session_id) % 100
    # ...
```

---

## 影响

### 对开发的影响
- 需要实现分组逻辑
- 需要实现复杂度判断
- 需要统计分析模块

### 对运维的影响
- 需要监控实验效果
- 需要定期优化路由规则

---

## 相关决策
- ADR-010: 多模型实例与运行时管理方案
- ADR-011: 模型健康检查方案
- ADR-013: 限流与熔断机制方案
- ADR-014: 模型版本管理方案
