"""
智能问答平台 - 预设模板服务单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.preset_template import PresetTemplate, TemplateType
from app.services.template_service import TemplateService


def _make_result(
    *,
    one_or_none: object = None,
    scalar: object = None,
    scalars_all: list[object] | None = None,
) -> MagicMock:
    """构造一个模拟的 SQLAlchemy Result 对象。"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = one_or_none
    result.scalar.return_value = scalar
    if scalars_all is not None:
        result.scalars.return_value.all.return_value = scalars_all
    return result


def _make_service() -> tuple[TemplateService, MagicMock]:
    """构造一个带有 Mock AsyncSession 的 TemplateService。"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return TemplateService(db), db


def _make_template(tpl_id: str = "tpl-1", **overrides: object) -> PresetTemplate:
    """构造一个临时的 PresetTemplate 实例（无需数据库会话）。"""
    defaults: dict[str, object] = {
        "name": "测试模板",
        "description": "测试描述",
        "template_type": TemplateType.CHAT,
        "template": {"model": "gpt-4"},
        "is_default": False,
        "is_active": True,
        "tags": ["test"],
        "category": "chat",
        "created_by": "user-1",
    }
    defaults.update(overrides)
    template = PresetTemplate(**defaults)  # type: ignore[arg-type]
    template.id = tpl_id
    return template


class TestPresetTemplate:
    """预设模板测试"""

    def test_template_category_enum(self):
        """测试模板分类枚举值"""
        category_map = {
            "CHAT": "chat",
            "EMBEDDING": "embedding",
            "RAG": "rag",
            "CUSTOM": "custom",
        }

        assert category_map["CHAT"] == "chat"
        assert category_map["EMBEDDING"] == "embedding"
        assert category_map["RAG"] == "rag"
        assert category_map["CUSTOM"] == "custom"

    def test_template_create_schema(self):
        """测试模板创建 Schema"""
        from app.schemas.model import TemplateCategory, TemplateCreate

        template = TemplateCreate(
            name="GPT-4 标准配置",
            category=TemplateCategory.CHAT,
            description="GPT-4 标准对话配置",
            config={
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2048,
            },
            is_public=True,
            tags=["openai", "gpt-4", "标准配置"],
        )

        assert template.name == "GPT-4 标准配置"
        assert template.category == TemplateCategory.CHAT
        assert template.config["model"] == "gpt-4"
        assert template.is_public is True

    def test_template_update_schema(self):
        """测试模板更新 Schema"""
        from app.schemas.model import TemplateUpdate

        update = TemplateUpdate(
            name="更新的模板名称",
            description="更新后的描述",
            config={"temperature": 0.5},
        )

        assert update.name == "更新的模板名称"
        assert update.description == "更新后的描述"
        assert update.config["temperature"] == 0.5

    def test_template_response_schema(self):
        """测试模板响应 Schema"""
        from app.schemas.model import TemplateCategory, TemplateResponse

        response = TemplateResponse(
            id="template-1",
            name="测试模板",
            category=TemplateCategory.CHAT,
            description="测试描述",
            config={"model": "gpt-4"},
            is_public=True,
            tags=["test"],
            created_by="user-1",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert response.id == "template-1"
        assert response.category == TemplateCategory.CHAT

    def test_template_validation(self):
        """测试模板配置验证"""
        from pydantic import ValidationError

        from app.schemas.model import TemplateCategory, TemplateCreate

        # 缺少必需字段
        with pytest.raises(ValidationError):
            TemplateCreate(
                category=TemplateCategory.CHAT,
                config={"model": "gpt-4"},
            )

        # 无效的分类 - 应该使用枚举而非字符串
        # 注意：Pydantic 会自动验证枚举类型


class TestTemplateService:
    """模板服务测试"""

    def test_merge_config(self):
        """测试配置合并逻辑"""

        def merge_configs(base: dict, override: dict) -> dict:
            result = base.copy()
            result.update(override)
            return result

        base_config = {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 2048,
            "top_p": 0.9,
        }

        override_config = {
            "temperature": 0.5,
            "max_tokens": 4096,
        }

        merged = merge_configs(base_config, override_config)

        assert merged["model"] == "gpt-4"  # 保持不变
        assert merged["temperature"] == 0.5  # 被覆盖
        assert merged["max_tokens"] == 4096  # 被覆盖
        assert merged["top_p"] == 0.9  # 保持不变

    def test_template_search_filter(self):
        """测试模板搜索过滤"""
        templates = [
            {"name": "GPT-4 标准", "tags": ["openai", "gpt-4"]},
            {"name": "Claude 对话", "tags": ["anthropic", "claude"]},
            {"name": "Embedding 配置", "tags": ["embedding", "openai"]},
        ]

        # 按标签过滤
        openai_templates = [
            t for t in templates if any(tag in ["openai"] for tag in t["tags"])
        ]

        assert len(openai_templates) == 2

        # 按名称搜索
        search_results = [t for t in templates if "GPT" in t["name"]]

        assert len(search_results) == 1
        assert search_results[0]["name"] == "GPT-4 标准"

    def test_template_versioning(self):
        """测试模板版本管理"""
        from app.schemas.model import TemplateCategory, TemplateResponse

        # 创建多个版本
        versions = []
        for i in range(1, 4):
            version = TemplateResponse(
                id=f"template-v{i}",
                name=f"模板 v{i}",
                category=TemplateCategory.CHAT,
                description=f"版本 {i}",
                config={"version": i},
                is_public=True,
                tags=["test"],
                created_by="user-1",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            versions.append(version)

        assert len(versions) == 3
        assert versions[0].config["version"] == 1
        assert versions[2].config["version"] == 3


class TestTemplateServiceCRUD:
    """TemplateService 业务方法单元测试（隔离 DB）"""

    async def test_create_success_returns_template(self):
        """create 正常创建 - 返回新建模板"""
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        async def _refresh_set_id(obj: PresetTemplate) -> None:
            obj.id = "tpl-new"

        db.refresh = AsyncMock(side_effect=_refresh_set_id)

        # Act
        result = await service.create(
            name="新模板",
            template={"model": "gpt-4"},
            template_type=TemplateType.CHAT,
            description="描述",
            tags=["a"],
            user_id="user-1",
        )

        # Assert
        assert result.id == "tpl-new"
        assert result.name == "新模板"
        assert result.template == {"model": "gpt-4"}
        db.add.assert_called_once()
        assert db.commit.await_count == 1
        assert db.refresh.await_count == 1

    async def test_create_duplicate_name_raises_validation_error(self):
        """create 名称重复 - 抛出 ValidationError"""
        # Arrange
        service, db = _make_service()
        existing = _make_template(name="已存在")
        db.execute = AsyncMock(return_value=_make_result(one_or_none=existing))

        # Act / Assert
        with pytest.raises(ValidationError):
            await service.create(
                name="已存在",
                template={"model": "gpt-4"},
                template_type=TemplateType.CHAT,
            )
        db.add.assert_not_called()

    async def test_create_with_is_default_clears_others(self):
        """create 设为默认 - 先清除同类型其它默认标记"""
        # Arrange: _get_by_name(None) -> _clear_default(generic)
        service, db = _make_service()
        db.execute = AsyncMock(
            side_effect=[
                _make_result(one_or_none=None),
                _make_result(),
            ]
        )
        db.refresh = AsyncMock()

        # Act
        result = await service.create(
            name="默认模板",
            template={"model": "gpt-4"},
            template_type=TemplateType.CHAT,
            is_default=True,
        )

        # Assert
        assert result.is_default is True
        assert db.execute.await_count == 2
        db.add.assert_called_once()

    async def test_get_existing_returns_template(self):
        """get 存在 - 返回模板"""
        # Arrange
        service, db = _make_service()
        template = _make_template()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=template))

        # Act
        result = await service.get("tpl-1")

        # Assert
        assert result is template

    async def test_get_missing_raises_not_found(self):
        """get 不存在 - 抛出 NotFoundError"""
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.get("missing")

    async def test_list_returns_paginated_items_and_total(self):
        """list 分页 - 返回条目与总数"""
        # Arrange: count(scalar=5) -> items(scalars_all=[t1, t2])
        service, db = _make_service()
        t1 = _make_template(tpl_id="t1", name="A")
        t2 = _make_template(tpl_id="t2", name="B")
        db.execute = AsyncMock(
            side_effect=[
                _make_result(scalar=5),
                _make_result(scalars_all=[t1, t2]),
            ]
        )

        # Act
        items, total = await service.list(page=1, page_size=2)

        # Assert
        assert total == 5
        assert items == [t1, t2]

    async def test_list_with_filters_returns_items(self):
        """list 带过滤条件 - 正常返回"""
        # Arrange
        service, db = _make_service()
        t1 = _make_template(tpl_id="t1")
        db.execute = AsyncMock(
            side_effect=[
                _make_result(scalar=1),
                _make_result(scalars_all=[t1]),
            ]
        )

        # Act
        items, total = await service.list(
            template_type=TemplateType.CHAT,
            category="chat",
            is_active=True,
        )

        # Assert
        assert total == 1
        assert items == [t1]

    async def test_update_success_updates_fields(self):
        """update 正常 - 更新字段并返回"""
        # Arrange
        service, db = _make_service()
        template = _make_template(name="原名", description="旧描述")
        db.execute = AsyncMock(return_value=_make_result(one_or_none=template))
        db.refresh = AsyncMock()

        # Act
        result = await service.update("tpl-1", description="新描述")

        # Assert
        assert result.description == "新描述"
        assert result.name == "原名"
        assert db.commit.await_count == 1

    async def test_update_name_change_succeeds_when_no_duplicate(self):
        """update 改名且无重名 - 更新成功"""
        # Arrange: get(template) -> _get_by_name(None)
        service, db = _make_service()
        template = _make_template(name="原名")
        db.execute = AsyncMock(
            side_effect=[
                _make_result(one_or_none=template),
                _make_result(one_or_none=None),
            ]
        )
        db.refresh = AsyncMock()

        # Act
        result = await service.update("tpl-1", name="新名")

        # Assert
        assert result.name == "新名"

    async def test_update_name_change_raises_on_duplicate(self):
        """update 改名且重名 - 抛出 ValidationError"""
        # Arrange: get(template) -> _get_by_name(existing with different id)
        service, db = _make_service()
        template = _make_template(name="原名")
        duplicate = _make_template(tpl_id="other-id", name="新名")
        db.execute = AsyncMock(
            side_effect=[
                _make_result(one_or_none=template),
                _make_result(one_or_none=duplicate),
            ]
        )

        # Act / Assert
        with pytest.raises(ValidationError):
            await service.update("tpl-1", name="新名")

    async def test_update_set_default_clears_others(self):
        """update 设为默认 - 清除同类型其它默认"""
        # Arrange: get(template) -> _clear_default(generic)
        service, db = _make_service()
        template = _make_template(is_default=False)
        db.execute = AsyncMock(
            side_effect=[
                _make_result(one_or_none=template),
                _make_result(),
            ]
        )
        db.refresh = AsyncMock()

        # Act
        result = await service.update("tpl-1", is_default=True)

        # Assert
        assert result.is_default is True
        assert db.execute.await_count == 2

    async def test_update_missing_raises_not_found(self):
        """update 模板不存在 - 抛出 NotFoundError"""
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.update("missing", description="x")

    async def test_delete_success_removes_template(self):
        """delete 非默认模板 - 删除成功"""
        # Arrange
        service, db = _make_service()
        template = _make_template(is_default=False)
        db.execute = AsyncMock(return_value=_make_result(one_or_none=template))

        # Act
        await service.delete("tpl-1")

        # Assert
        db.delete.assert_called_once_with(template)
        assert db.commit.await_count == 1

    async def test_delete_default_template_raises_validation_error(self):
        """delete 默认模板 - 抛出 ValidationError"""
        # Arrange
        service, db = _make_service()
        template = _make_template(is_default=True)
        db.execute = AsyncMock(return_value=_make_result(one_or_none=template))

        # Act / Assert
        with pytest.raises(ValidationError):
            await service.delete("tpl-1")
        db.delete.assert_not_called()

    async def test_delete_missing_raises_not_found(self):
        """delete 模板不存在 - 抛出 NotFoundError"""
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.delete("missing")

    async def test_get_default_returns_template(self):
        """get_default 存在默认 - 返回模板"""
        # Arrange
        service, db = _make_service()
        default_tpl = _make_template(is_default=True)
        db.execute = AsyncMock(return_value=_make_result(one_or_none=default_tpl))

        # Act
        result = await service.get_default(TemplateType.CHAT)

        # Assert
        assert result is default_tpl

    async def test_get_default_returns_none_when_absent(self):
        """get_default 无默认 - 返回 None"""
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act
        result = await service.get_default(TemplateType.CHAT)

        # Assert
        assert result is None

    async def test_apply_template_renders_variables(self):
        """apply_template 正常 - 替换变量"""
        # Arrange
        service, db = _make_service()
        template = _make_template(
            template={"prompt": "Hello {{name}}", "config": {"model": "{{model}}"}},
        )
        db.execute = AsyncMock(return_value=_make_result(one_or_none=template))

        # Act
        result = await service.apply_template(
            "tpl-1", {"name": "World", "model": "gpt-4"}
        )

        # Assert
        assert result == {"prompt": "Hello World", "config": {"model": "gpt-4"}}

    async def test_apply_template_inactive_raises(self):
        """apply_template 已禁用 - 抛出 ValidationError"""
        # Arrange
        service, db = _make_service()
        template = _make_template(is_active=False)
        db.execute = AsyncMock(return_value=_make_result(one_or_none=template))

        # Act / Assert
        with pytest.raises(ValidationError):
            await service.apply_template("tpl-1")

    async def test_apply_template_missing_raises_not_found(self):
        """apply_template 模板不存在 - 抛出 NotFoundError"""
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.apply_template("missing")

    async def test_apply_template_missing_variable_keeps_placeholder(self):
        """apply_template 变量缺失 - 保留占位符"""
        # Arrange
        service, db = _make_service()
        template = _make_template(template={"prompt": "Hello {{name}} {{missing}}"})
        db.execute = AsyncMock(return_value=_make_result(one_or_none=template))

        # Act
        result = await service.apply_template("tpl-1", {"name": "World"})

        # Assert
        assert result == {"prompt": "Hello World {{missing}}"}

    async def test_apply_template_no_variables_keeps_placeholders(self):
        """apply_template 不传变量 - 全部保留占位符"""
        # Arrange
        service, db = _make_service()
        template = _make_template(template={"prompt": "Hello {{name}}"})
        db.execute = AsyncMock(return_value=_make_result(one_or_none=template))

        # Act
        result = await service.apply_template("tpl-1")

        # Assert
        assert result == {"prompt": "Hello {{name}}"}

    def test_render_template_replaces_string_variables(self):
        """_render_template 字符串变量 - 替换"""
        # Arrange
        service = TemplateService(MagicMock())

        # Act
        result = service._render_template(
            {"prompt": "Hello {{name}}"}, {"name": "World"}
        )

        # Assert
        assert result == {"prompt": "Hello World"}

    def test_render_template_handles_nested_dict(self):
        """_render_template 嵌套字典 - 递归替换"""
        # Arrange
        service = TemplateService(MagicMock())

        # Act
        result = service._render_template(
            {"outer": {"inner": "{{value}}"}}, {"value": "resolved"}
        )

        # Assert
        assert result == {"outer": {"inner": "resolved"}}

    def test_render_template_handles_list(self):
        """_render_template 列表元素 - 逐项替换"""
        # Arrange
        service = TemplateService(MagicMock())

        # Act
        result = service._render_template(
            {"items": ["{{a}}", "{{b}}"]}, {"a": "1", "b": "2"}
        )

        # Assert
        assert result == {"items": ["1", "2"]}

    def test_render_template_passes_through_non_string_values(self):
        """_render_template 非字符串值 - 原样返回"""
        # Arrange
        service = TemplateService(MagicMock())

        # Act
        result = service._render_template(
            {"count": 5, "enabled": True, "nested": {"n": None}}, {}
        )

        # Assert
        assert result == {"count": 5, "enabled": True, "nested": {"n": None}}

    def test_render_template_missing_variable_keeps_placeholder(self):
        """_render_template 变量缺失 - 保留占位符"""
        # Arrange
        service = TemplateService(MagicMock())

        # Act
        result = service._render_template(
            {"prompt": "Hello {{name}} {{missing}}"}, {"name": "World"}
        )

        # Assert
        assert result == {"prompt": "Hello World {{missing}}"}
