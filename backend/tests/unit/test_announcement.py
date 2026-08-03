"""
智能问答平台 - 公告服务单元测试
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.announcement import Announcement, AnnouncementStatus, AnnouncementType
from app.services.announcement_service import AnnouncementService


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


def _make_service() -> tuple[AnnouncementService, MagicMock]:
    """构造一个带有 Mock AsyncSession 的 AnnouncementService。"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return AnnouncementService(db), db


def _make_announcement(aid: str = "ann-1", **overrides: object) -> Announcement:
    """构造一个临时的 Announcement 实例（无需数据库会话）。"""
    defaults: dict[str, object] = {
        "title": "测试公告",
        "content": "测试内容",
        "type": AnnouncementType.NOTICE,
        "status": AnnouncementStatus.DRAFT,
        "pinned": False,
        "published_at": None,
    }
    defaults.update(overrides)
    announcement = Announcement(**defaults)  # type: ignore[arg-type]
    announcement.id = aid
    announcement.created_at = datetime.now(UTC)
    announcement.updated_at = datetime.now(UTC)
    return announcement


class TestAnnouncementSchema:
    """Schema 验证测试"""

    def test_create_schema_title_required(self):
        """创建时 title 为必填"""
        from pydantic import ValidationError

        from app.schemas.announcement import AnnouncementCreate

        with pytest.raises(ValidationError):
            AnnouncementCreate(content="内容")

    def test_create_schema_content_required(self):
        """创建时 content 为必填"""
        from pydantic import ValidationError

        from app.schemas.announcement import AnnouncementCreate

        with pytest.raises(ValidationError):
            AnnouncementCreate(title="标题")

    def test_create_schema_defaults(self):
        """创建时字段有默认值"""
        from app.schemas.announcement import AnnouncementCreate

        ann = AnnouncementCreate(title="标题", content="内容")
        assert ann.type == "notice"
        assert ann.pinned is False

    def test_update_schema_optional_fields(self):
        """更新时所有字段可选"""
        from app.schemas.announcement import AnnouncementUpdate

        ann = AnnouncementUpdate()
        assert ann.title is None
        assert ann.content is None

    def test_response_schema_from_attributes(self):
        """响应 schema 支持 from_attributes"""
        from app.schemas.announcement import AnnouncementResponse

        now = datetime.now(UTC)
        resp = AnnouncementResponse(
            id="ann-1",
            title="标题",
            content="内容",
            type="notice",
            status="draft",
            pinned=False,
            published_at=None,
            created_at=now,
            updated_at=now,
        )
        assert resp.id == "ann-1"


class TestAnnouncementServiceCRUD:
    """AnnouncementService 业务方法单元测试（隔离 DB）"""

    async def test_create_success_returns_announcement(self):
        """create 正常创建 - 返回新建公告"""
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        async def _refresh_set_id(obj: Announcement) -> None:
            obj.id = "ann-new"

        db.refresh = AsyncMock(side_effect=_refresh_set_id)

        # Act
        result = await service.create(
            title="新公告",
            content="新内容",
            type_=AnnouncementType.NOTICE,
            pinned=False,
        )

        # Assert
        assert result.id == "ann-new"
        assert result.title == "新公告"
        db.add.assert_called_once()
        assert db.commit.await_count == 1

    async def test_create_duplicate_title_raises_validation_error(self):
        """create 标题重复 - 抛出 ValidationError"""
        # Arrange
        service, db = _make_service()
        existing = _make_announcement(title="已存在")
        db.execute = AsyncMock(return_value=_make_result(one_or_none=existing))

        # Act / Assert
        with pytest.raises(ValidationError):
            await service.create(title="已存在", content="内容")
        db.add.assert_not_called()

    async def test_get_existing_returns_announcement(self):
        """get 存在 - 返回公告"""
        # Arrange
        service, db = _make_service()
        ann = _make_announcement()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=ann))

        # Act
        result = await service.get("ann-1")

        # Assert
        assert result is ann

    async def test_get_missing_raises_not_found(self):
        """get 不存在 - 抛出 NotFoundError"""
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.get("missing")

    async def test_get_soft_deleted_returns_not_found(self):
        """get 已软删公告 - 抛出 NotFoundError"""
        # Arrange
        service, db = _make_service()
        # is_deleted=True 的记录不会被查询到，模拟返回 None
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.get("deleted-ann")

    async def test_list_returns_paginated_items_and_total(self):
        """list 分页 - 返回条目与总数"""
        # Arrange
        service, db = _make_service()
        a1 = _make_announcement(aid="a1")
        a2 = _make_announcement(aid="a2")
        db.execute = AsyncMock(
            side_effect=[
                _make_result(scalar=5),
                _make_result(scalars_all=[a1, a2]),
            ]
        )

        # Act
        items, total = await service.list_items(page=1, page_size=2)

        # Assert
        assert total == 5
        assert len(items) == 2

    async def test_list_with_status_filter(self):
        """list 带 status 过滤 - 正常返回"""
        # Arrange
        service, db = _make_service()
        ann = _make_announcement(status=AnnouncementStatus.PUBLISHED)
        db.execute = AsyncMock(
            side_effect=[
                _make_result(scalar=1),
                _make_result(scalars_all=[ann]),
            ]
        )

        # Act
        items, total = await service.list_items(
            status=AnnouncementStatus.PUBLISHED,
        )

        # Assert
        assert total == 1
        assert items[0].status == AnnouncementStatus.PUBLISHED

    async def test_list_with_type_filter(self):
        """list 带 type 过滤 - 正常返回"""
        # Arrange
        service, db = _make_service()
        ann = _make_announcement(type=AnnouncementType.MAINTENANCE)
        db.execute = AsyncMock(
            side_effect=[
                _make_result(scalar=1),
                _make_result(scalars_all=[ann]),
            ]
        )

        # Act
        items, total = await service.list_items(
            type_=AnnouncementType.MAINTENANCE,
        )

        # Assert
        assert total == 1
        assert items[0].type == AnnouncementType.MAINTENANCE

    async def test_update_success_updates_fields(self):
        """update 正常 - 更新字段并返回"""
        # Arrange
        service, db = _make_service()
        ann = _make_announcement(title="原标题")
        db.execute = AsyncMock(return_value=_make_result(one_or_none=ann))
        db.refresh = AsyncMock()

        # Act
        result = await service.update("ann-1", title="新标题")

        # Assert
        assert result.title == "新标题"
        assert db.commit.await_count == 1

    async def test_update_title_change_raises_on_duplicate(self):
        """update 改标题且重名 - 抛出 ValidationError"""
        # Arrange
        service, db = _make_service()
        ann = _make_announcement(title="原标题")
        duplicate = _make_announcement(aid="other", title="新标题")
        db.execute = AsyncMock(
            side_effect=[
                _make_result(one_or_none=ann),
                _make_result(one_or_none=duplicate),
            ]
        )

        # Act / Assert
        with pytest.raises(ValidationError):
            await service.update("ann-1", title="新标题")

    async def test_update_missing_raises_not_found(self):
        """update 公告不存在 - 抛出 NotFoundError"""
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.update("missing", title="x")

    async def test_update_to_published_sets_published_at(self):
        """update 转 published 状态 - 自动写入 published_at"""
        # Arrange
        service, db = _make_service()
        ann = _make_announcement(status=AnnouncementStatus.DRAFT, published_at=None)
        db.execute = AsyncMock(return_value=_make_result(one_or_none=ann))
        db.refresh = AsyncMock()

        # Act
        result = await service.update("ann-1", status=AnnouncementStatus.PUBLISHED)

        # Assert
        assert result.status == AnnouncementStatus.PUBLISHED
        assert result.published_at is not None

    async def test_delete_success_soft_deletes(self):
        """delete 正常 - 设置 is_deleted=True"""
        # Arrange
        service, db = _make_service()
        ann = _make_announcement()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=ann))

        # Act
        await service.delete("ann-1")

        # Assert
        assert ann.is_deleted is True
        assert db.commit.await_count == 1
        db.delete.assert_not_called()  # 软删，不调用 db.delete

    async def test_delete_missing_raises_not_found(self):
        """delete 公告不存在 - 抛出 NotFoundError"""
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.delete("missing")

    async def test_publish_success_updates_status_and_time(self):
        """publish 正常 - 设置 status=PUBLISHED + published_at"""
        # Arrange
        service, db = _make_service()
        ann = _make_announcement(status=AnnouncementStatus.DRAFT, published_at=None)
        db.execute = AsyncMock(return_value=_make_result(one_or_none=ann))
        db.refresh = AsyncMock()

        # Act
        result = await service.publish("ann-1")

        # Assert
        assert result.status == AnnouncementStatus.PUBLISHED
        assert result.published_at is not None
        assert db.commit.await_count == 1

    async def test_publish_missing_raises_not_found(self):
        """publish 公告不存在 - 抛出 NotFoundError"""
        # Arrange
        service, db = _make_service()
        db.execute = AsyncMock(return_value=_make_result(one_or_none=None))

        # Act / Assert
        with pytest.raises(NotFoundError):
            await service.publish("missing")
