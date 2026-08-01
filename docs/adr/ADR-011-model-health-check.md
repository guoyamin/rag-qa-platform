# ADR-011: 模型健康检查方案

**状态:** 已接受  
**日期:** 2026-08-01  
**决策主体:** 用户 + AI辅助

---

## 上下文

### 业务背景

模型管理功能需要监控模型健康状态：
- 及时发现模型不可用
- 避免将请求发送到故障模型
- 为熔断机制提供数据

### 技术约束

- 健康检查需要低开销
- 需要支持定时检查
- 需要记录历史状态

---

## 决策

> 我们决定使用 **APScheduler 定时任务** 进行健康检查，记录状态到 `model_health_logs` 表。

---

## 健康检查策略

| 检查类型 | 间隔 | 说明 |
|----------|------|------|
| 快速探测 | 30 秒 | 只检查 API 可达性 |
| 完整探测 | 5 分钟 | 发送测试请求验证功能 |
| 综合评估 | 15 分钟 | 综合响应时间、成功率 |

---

## 数据库设计

```sql
CREATE TABLE model_health_logs (
    id VARCHAR(36) PRIMARY KEY,
    model_id VARCHAR(36) NOT NULL COMMENT '模型ID',
    check_type VARCHAR(20) NOT NULL COMMENT '检查类型：quick/full/comprehensive',
    status VARCHAR(20) NOT NULL COMMENT '状态：healthy/degraded/unhealthy/unknown',
    latency_ms INTEGER COMMENT '响应延迟',
    error_message TEXT COMMENT '错误信息',
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (model_id) REFERENCES model_instances(id) ON DELETE CASCADE
);

CREATE INDEX idx_model_health_logs_model ON model_health_logs(model_id);
CREATE INDEX idx_model_health_logs_status ON model_health_logs(status);
CREATE INDEX idx_model_health_logs_time ON model_health_logs(checked_at);

COMMENT ON TABLE model_health_logs IS '模型健康检查日志';
```

---

## 健康检查实现

```python
class HealthCheckService:
    """健康检查服务"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
    
    async def quick_check(self, model_id: str) -> HealthStatus:
        """快速探测：只检查 API 可达性"""
        model = await self._get_model(model_id)
        
        try:
            start = time.time()
            await self._ping(model)
            latency = int((time.time() - start) * 1000)
            
            return HealthStatus(
                status="healthy",
                latency_ms=latency
            )
        except Exception as e:
            return HealthStatus(
                status="unhealthy",
                error_message=str(e)
            )
    
    async def full_check(self, model_id: str) -> HealthStatus:
        """完整探测：发送测试请求"""
        model = await self._get_model(model_id)
        
        try:
            start = time.time()
            response = await self._call_model(model, test_prompt="1+1=?")
            latency = int((time.time() - start) * 1000)
            
            # 验证响应
            if response.is_valid():
                return HealthStatus(
                    status="healthy",
                    latency_ms=latency
                )
            else:
                return HealthStatus(
                    status="degraded",
                    error_message="Invalid response"
                )
        except Exception as e:
            return HealthStatus(
                status="unhealthy",
                error_message=str(e)
            )
```

---

## 影响

### 对开发的影响
- 需要实现健康检查任务调度
- 需要处理网络异常

### 对运维的影响
- 需要监控健康检查任务运行状态
- 需要关注误报情况
