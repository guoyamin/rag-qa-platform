# ADR-014: 模型版本管理方案

**状态:** 已接受  
**日期:** 2026-08-01  
**决策主体:** 用户 + AI辅助

---

## 上下文

### 业务背景

模型管理功能需要支持模型版本控制：
- 记录模型版本变更历史
- 支持灰度发布（小范围试用新版本）
- 支持一键回滚

### 技术约束

- 版本变更需要平滑过渡
- 回滚需要快速可用
- 需要记录版本性能数据

---

## 决策

> 我们决定实现 **模型版本管理系统**，支持版本记录、灰度发布和回滚。

---

## 版本状态

| 状态 | 说明 |
|------|------|
| draft | 草稿，未发布 |
| rolling_out | 灰度发布中 |
| active | 正式启用 |
| deprecated | 已废弃 |

## 灰度发布

| 阶段 | 百分比 | 说明 |
|------|--------|------|
| 1 | 10% | 小范围试用 |
| 2 | 30% | 中等范围 |
| 3 | 50% | 扩大范围 |
| 4 | 100% | 全量发布 |

---

## 数据库设计

```sql
-- 模型版本表
CREATE TABLE model_versions (
    id VARCHAR(36) PRIMARY KEY,
    model_id VARCHAR(36) NOT NULL COMMENT '模型实例ID',
    version VARCHAR(50) NOT NULL COMMENT '版本号：v1.0',
    description TEXT COMMENT '版本说明',
    config_snapshot JSONB NOT NULL COMMENT '完整配置快照',
    status VARCHAR(20) NOT NULL DEFAULT 'draft' COMMENT '状态：draft/rolling_out/active/deprecated',
    rollout_percentage INTEGER DEFAULT 0 COMMENT '灰度发布百分比',
    created_by VARCHAR(36) COMMENT '创建人',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (model_id) REFERENCES model_instances(id) ON DELETE CASCADE
);

CREATE INDEX idx_model_versions_model ON model_versions(model_id);
CREATE INDEX idx_model_versions_status ON model_versions(status);

COMMENT ON TABLE model_versions IS '模型版本记录';

-- 版本发布记录
CREATE TABLE version_releases (
    id VARCHAR(36) PRIMARY KEY,
    version_id VARCHAR(36) NOT NULL COMMENT '版本ID',
    release_type VARCHAR(20) NOT NULL COMMENT '发布类型：rollout/rollback/full',
    from_percentage INTEGER COMMENT '发布前百分比',
    to_percentage INTEGER COMMENT '发布后百分比',
    released_by VARCHAR(36) COMMENT '发布人',
    released_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT COMMENT '发布备注',
    
    FOREIGN KEY (version_id) REFERENCES model_versions(id) ON DELETE CASCADE
);

CREATE INDEX idx_version_releases ON version_releases(version_id);

COMMENT ON TABLE version_releases IS '版本发布记录';
```

---

## 补充设计 S2：与智能路由集成

路由规则可指定版本号，未指定时使用当前活跃版本：

```sql
-- router_rules 表增加 version_id 字段
ALTER TABLE router_rules ADD COLUMN version_id VARCHAR(36);
```

---

## 补充设计 S5：与预设模板关联

支持从模板创建版本，或将版本保存为模板：

```python
# 从模板创建版本
async def create_version_from_template(self, model_id, version, template_id, ...):
    template = await self.template_service.get(template_id)
    config = self._build_config_from_template(template)
    return await self.create_version(model_id, version, config, ...)

# 将版本保存为模板
async def save_version_as_template(self, version_id, template_name, ...):
    version = await self.get_version(version_id)
    return await self.template_service.create_from_config(template_name, version.config)
```

---

## 影响

### 对开发的影响
- 需要实现版本切换逻辑
- 需要支持配置快照

### 对运维的影响
- 需要监控各版本使用情况
- 需要支持快速回滚

---

## 相关决策
- ADR-010: 多模型实例与运行时管理方案
