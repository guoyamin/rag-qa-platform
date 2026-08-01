# ADR-012: 模型用量统计与成本分析方案

**状态:** 已接受  
**日期:** 2026-08-01  
**决策主体:** 用户 + AI辅助

---

## 上下文

### 业务背景

模型管理功能需要统计模型使用情况：
- 成本控制：知道钱花在哪了
- 容量规划：预测未来用量
- 用户分析：哪个部门用得多

### 技术约束

- 需要记录每次调用的 Token 消耗
- 需要按模型/时间/用户聚合统计
- 需要支持成本估算

---

## 决策

> 我们决定实现 **模型用量统计系统**，记录每次调用，支持多维度统计和成本分析。

---

## 统计维度

| 维度 | 说明 |
|------|------|
| 按模型 | GPT-4o / Qwen / ChatGLM 分别统计 |
| 按时间 | 今日 / 本周 / 本月 |
| 按用户 | 部门使用排行 |
| 按场景 | 问答 / 知识库 / 文档处理 |

## 统计指标

| 指标 | 说明 |
|------|------|
| Token 消耗量 | input_tokens + output_tokens |
| API 调用次数 | 成功 + 失败 |
| 平均响应时间 | ms |
| 成功率 | 百分比 |
| 预估费用 | 按单价计算 |

---

## 数据库设计

```sql
-- 用量日志（详细记录）
CREATE TABLE model_usage_logs (
    id VARCHAR(36) PRIMARY KEY,
    model_id VARCHAR(36) NOT NULL COMMENT '模型ID',
    user_id VARCHAR(36) COMMENT '用户ID',
    session_id VARCHAR(100) COMMENT '会话ID',
    scene VARCHAR(50) COMMENT '使用场景',
    input_tokens INTEGER DEFAULT 0 COMMENT '输入Token数',
    output_tokens INTEGER DEFAULT 0 COMMENT '输出Token数',
    total_tokens INTEGER DEFAULT 0 COMMENT '总Token数',
    latency_ms INTEGER COMMENT '响应时间',
    success BOOLEAN DEFAULT TRUE COMMENT '是否成功',
    error_message TEXT COMMENT '错误信息',
    cost DECIMAL(10,6) DEFAULT 0 COMMENT '预估费用',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (model_id) REFERENCES model_instances(id) ON DELETE CASCADE
);

CREATE INDEX idx_model_usage_logs_model ON model_usage_logs(model_id);
CREATE INDEX idx_model_usage_logs_user ON model_usage_logs(user_id);
CREATE INDEX idx_model_usage_logs_created ON model_usage_logs(created_at);

COMMENT ON TABLE model_usage_logs IS '模型用量日志';

-- 用量日聚合（报表）
CREATE TABLE model_usage_daily (
    id VARCHAR(36) PRIMARY KEY,
    model_id VARCHAR(36) NOT NULL COMMENT '模型ID',
    date DATE NOT NULL COMMENT '统计日期',
    total_calls INTEGER DEFAULT 0 COMMENT '总调用次数',
    success_calls INTEGER DEFAULT 0 COMMENT '成功次数',
    failed_calls INTEGER DEFAULT 0 COMMENT '失败次数',
    total_input_tokens INTEGER DEFAULT 0 COMMENT '总输入Token',
    total_output_tokens INTEGER DEFAULT 0 COMMENT '总输出Token',
    avg_latency_ms INTEGER DEFAULT 0 COMMENT '平均响应时间',
    success_rate DECIMAL(5,2) DEFAULT 0 COMMENT '成功率',
    estimated_cost DECIMAL(10,4) DEFAULT 0 COMMENT '预估费用',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (model_id) REFERENCES model_instances(id) ON DELETE CASCADE,
    UNIQUE(model_id, date)
);

CREATE INDEX idx_model_usage_daily_date ON model_usage_daily(date);
CREATE INDEX idx_model_usage_daily_model ON model_usage_daily(model_id);

COMMENT ON TABLE model_usage_daily IS '模型用量日聚合报表';
```

---

## 影响

### 对存储的影响
- 用量日志数据量大，需要定期归档
- 建议保留 90 天详细日志

---

## 相关决策
- ADR-008: 模型配置存储方案
