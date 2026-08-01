from __future__ import annotations

import re
from typing import Any, cast

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.preset_template import PresetTemplate, TemplateType

logger = structlog.get_logger(__name__)

# 类型别名：类内 ``list`` 方法会遮蔽内置 ``list``，使用别名保证类型注解解析正确
TagList = list[str]

_PATTERN = re.compile(r"\{\{(\w+)\}\}")


class TemplateService:
    """预设模板服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        name: str,
        template: dict[str, Any],
        template_type: TemplateType,
        description: str | None = None,
        is_default: bool = False,
        tags: TagList | None = None,
        category: str | None = None,
        user_id: str | None = None,
    ) -> PresetTemplate:
        """创建模板"""
        # 检查名称是否重复
        existing = await self._get_by_name(name)
        if existing:
            raise ValidationError(f"模板名称 '{name}' 已存在")

        # 如果设为默认，先取消其他默认
        if is_default:
            await self._clear_default(template_type)

        template_obj = PresetTemplate(
            name=name,
            description=description,
            template_type=template_type,
            template=template,
            is_default=is_default,
            tags=tags or [],
            category=category,
            created_by=user_id,
        )

        self.db.add(template_obj)
        await self.db.commit()
        await self.db.refresh(template_obj)

        logger.info(
            "template_created",
            template_id=template_obj.id,
            name=name,
        )
        return template_obj

    async def get(self, template_id: str) -> PresetTemplate:
        """获取模板"""
        result = await self.db.execute(
            select(PresetTemplate).where(PresetTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()

        if not template:
            raise NotFoundError("模板不存在")

        return template

    async def list(
        self,
        template_type: TemplateType | None = None,
        category: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PresetTemplate], int]:
        """列出模板"""
        query = select(PresetTemplate)

        if template_type:
            query = query.where(PresetTemplate.template_type == template_type)
        if category:
            query = query.where(PresetTemplate.category == category)
        if is_active is not None:
            query = query.where(PresetTemplate.is_active == is_active)

        # 统计总数
        count_result = await self.db.execute(
            select(func.count(PresetTemplate.id)).select_from(PresetTemplate)
        )
        total = count_result.scalar() or 0

        # 分页
        query = query.order_by(PresetTemplate.is_default.desc(), PresetTemplate.name)
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update(
        self,
        template_id: str,
        name: str | None = None,
        template: dict[str, Any] | None = None,
        description: str | None = None,
        is_default: bool | None = None,
        is_active: bool | None = None,
        tags: TagList | None = None,
        category: str | None = None,
    ) -> PresetTemplate:
        """更新模板"""
        template_obj = await self.get(template_id)

        if name is not None and name != template_obj.name:
            # 检查名称是否重复
            existing = await self._get_by_name(name)
            if existing and existing.id != template_id:
                raise ValidationError(f"模板名称 '{name}' 已存在")
            template_obj.name = name

        if template is not None:
            template_obj.template = template

        if description is not None:
            template_obj.description = description

        if is_default is not None and is_default:
            await self._clear_default(template_obj.template_type)
            template_obj.is_default = True

        if is_active is not None:
            template_obj.is_active = is_active

        if tags is not None:
            template_obj.tags = tags

        if category is not None:
            template_obj.category = category

        await self.db.commit()
        await self.db.refresh(template_obj)

        logger.info("template_updated", template_id=template_id)
        return template_obj

    async def delete(self, template_id: str) -> None:
        """删除模板"""
        template_obj = await self.get(template_id)

        if template_obj.is_default:
            raise ValidationError("不能删除默认模板，请先设置其他模板为默认")

        await self.db.delete(template_obj)
        await self.db.commit()

        logger.info("template_deleted", template_id=template_id)

    async def get_default(self, template_type: TemplateType) -> PresetTemplate | None:
        """获取指定类型的默认模板"""
        result = await self.db.execute(
            select(PresetTemplate).where(
                PresetTemplate.template_type == template_type,
                PresetTemplate.is_default.is_(True),
                PresetTemplate.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def apply_template(
        self,
        template_id: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        应用模板，替换变量

        Args:
            template_id: 模板ID
            variables: 变量值

        Returns:
            替换后的模板内容
        """
        template_obj = await self.get(template_id)

        if not template_obj.is_active:
            raise ValidationError("模板已禁用")

        return self._render_template(template_obj.template, variables or {})

    def _render_template(
        self,
        template_content: dict[str, Any],
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """渲染模板，替换 {{variable}} 格式的变量"""

        def replace_variables(value: Any) -> Any:
            if isinstance(value, str):
                # 替换 {{variable}} 格式
                matches = _PATTERN.findall(value)
                for var_name in matches:
                    replacement = variables.get(var_name, f"{{{{{var_name}}}}}")
                    value = value.replace(f"{{{{{var_name}}}}}", str(replacement))
                return value
            elif isinstance(value, dict):
                return {k: replace_variables(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [replace_variables(item) for item in value]
            return value

        return cast(dict[str, Any], replace_variables(template_content))

    async def _get_by_name(self, name: str) -> PresetTemplate | None:
        """根据名称查询模板"""
        result = await self.db.execute(
            select(PresetTemplate).where(PresetTemplate.name == name)
        )
        return result.scalar_one_or_none()

    async def _clear_default(self, template_type: TemplateType) -> None:
        """清除同类型的所有默认标记"""
        await self.db.execute(
            update(PresetTemplate)
            .where(
                PresetTemplate.template_type == template_type,
                PresetTemplate.is_default.is_(True),
            )
            .values(is_default=False)
        )
