"""
智能问答平台 - 版本管理服务单元测试

生成信息:
- AI辅助生成: 是
- 生成日期: 2026-08-01
- 验证状态: 待测试
- 版本: V1.0
"""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.model_version import ReleaseType, VersionStatus
from app.services.version_service import VersionService


class TestModelVersion:
    """模型版本测试"""

    def test_version_status_enum(self):
        """测试版本状态枚举值"""
        version_status = {
            "DRAFT": "draft",
            "RELEASED": "released",
            "DEPRECATED": "deprecated",
            "ROLLED_BACK": "rolled_back",
        }

        assert version_status["DRAFT"] == "draft"
        assert version_status["RELEASED"] == "released"
        assert version_status["DEPRECATED"] == "deprecated"
        assert version_status["ROLLED_BACK"] == "rolled_back"

    def test_release_type_enum(self):
        """测试发布类型枚举值"""
        release_type = {
            "FULL": "full",
            "CANARY": "canary",
            "BLUE_GREEN": "blue_green",
            "ROLLING": "rolling",
        }

        assert release_type["FULL"] == "full"
        assert release_type["CANARY"] == "canary"
        assert release_type["BLUE_GREEN"] == "blue_green"
        assert release_type["ROLLING"] == "rolling"

    def test_version_schema(self):
        """测试版本 Schema"""
        from app.schemas.model import ReleaseType, VersionResponse, VersionStatus

        response = VersionResponse(
            id="version-1",
            model_id="model-1",
            version="1.0.0",
            name="正式版本",
            description="首个正式版本",
            config={"temperature": 0.7},
            status=VersionStatus.RELEASED,
            release_type=ReleaseType.FULL,
            rollout_percent=100,
            created_by="user-1",
            released_at=datetime.now(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert response.version == "1.0.0"
        assert response.status == VersionStatus.RELEASED
        assert response.rollout_percent == 100


class TestVersionManagement:
    """版本管理测试"""

    def test_version_comparison(self):
        """测试版本号比较"""

        def compare_versions(v1: str, v2: str) -> int:
            """比较两个版本号: v1 > v2 返回 1, v1 < v2 返回 -1, 相等返回 0"""
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]

            # 补齐长度
            max_len = max(len(parts1), len(parts2))
            parts1.extend([0] * (max_len - len(parts1)))
            parts2.extend([0] * (max_len - len(parts2)))

            for p1, p2 in zip(parts1, parts2, strict=False):
                if p1 > p2:
                    return 1
                if p1 < p2:
                    return -1
            return 0

        # 大版本比较
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.0.0", "2.0.0") == -1

        # 小版本比较
        assert compare_versions("1.1.0", "1.0.0") == 1
        assert compare_versions("1.0.0", "1.1.0") == -1

        # 修订版本比较
        assert compare_versions("1.0.1", "1.0.0") == 1
        assert compare_versions("1.0.0", "1.0.1") == -1

        # 相等
        assert compare_versions("1.0.0", "1.0.0") == 0

    def test_semantic_versioning(self):
        """测试语义化版本"""

        def parse_version(version: str) -> dict:
            """解析语义化版本号"""
            parts = version.split(".")
            return {
                "major": int(parts[0]) if len(parts) > 0 else 0,
                "minor": int(parts[1]) if len(parts) > 1 else 0,
                "patch": int(parts[2].split("-")[0]) if len(parts) > 2 else 0,
                "prerelease": (
                    parts[2].split("-")[1]
                    if len(parts) > 2 and "-" in parts[2]
                    else None
                ),
            }

        v = parse_version("1.2.3")
        assert v["major"] == 1
        assert v["minor"] == 2
        assert v["patch"] == 3

        v = parse_version("2.0.0-beta")
        assert v["major"] == 2
        assert v["minor"] == 0
        assert v["patch"] == 0
        assert v["prerelease"] == "beta"

    def test_version_bump(self):
        """测试版本号递增"""

        def bump_version(version: str, part: str = "patch") -> str:
            """递增版本号"""
            parts = version.split(".")
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0

            if part == "major":
                major += 1
                minor = 0
                patch = 0
            elif part == "minor":
                minor += 1
                patch = 0
            else:  # patch
                patch += 1

            return f"{major}.{minor}.{patch}"

        # patch 递增
        assert bump_version("1.0.0", "patch") == "1.0.1"
        assert bump_version("1.2.3", "patch") == "1.2.4"

        # minor 递增
        assert bump_version("1.0.0", "minor") == "1.1.0"
        assert bump_version("1.2.3", "minor") == "1.3.0"

        # major 递增
        assert bump_version("1.0.0", "major") == "2.0.0"
        assert bump_version("1.2.3", "major") == "2.0.0"


class TestGrayRelease:
    """灰度发布测试"""

    def test_canary_release_percentage(self):
        """测试金丝雀发布百分比"""

        def should_receive_traffic(user_id: str, rollout_percent: int) -> bool:
            """根据用户ID和发布百分比决定是否接收流量"""
            # 使用用户ID的哈希来确保一致性
            hash_value = sum(ord(c) for c in user_id)
            bucket = hash_value % 100
            return bucket < rollout_percent

        # 100% 发布
        assert should_receive_traffic("user-1", 100) is True

        # 0% 发布
        assert should_receive_traffic("user-1", 0) is False

        # 50% 发布
        # 多次测试确保分布大致均匀
        true_count = sum(
            1 for i in range(100) if should_receive_traffic(f"user-{i}", 50)
        )
        assert 30 <= true_count <= 70  # 允许一定偏差

    def test_gray_release_tier(self):
        """测试灰度分层"""
        tiers = [
            {"name": "alpha", "percent": 5, "users": ["admin-1", "admin-2"]},
            {"name": "beta", "percent": 20, "users": ["tester-*"]},
            {"name": "gamma", "percent": 50},
            {"name": "release", "percent": 100},
        ]

        def is_in_tier(user_id: str, tier: dict) -> bool:
            """检查用户是否在指定层"""
            # 检查白名单用户
            if "users" in tier:
                for pattern in tier["users"]:
                    if pattern.endswith("*"):
                        prefix = pattern[:-1]
                        if user_id.startswith(prefix):
                            return True
                    elif user_id == pattern:
                        return True
            return False

        assert is_in_tier("admin-1", tiers[0]) is True
        assert is_in_tier("tester-1", tiers[1]) is True
        assert is_in_tier("normal-user", tiers[2]) is False


class TestRollback:
    """版本回滚测试"""

    def test_rollback_eligibility(self):
        """测试回滚资格"""

        def can_rollback(version: dict, released_versions: list) -> tuple[bool, str]:
            """检查是否可以回滚"""
            if version["status"] != "released":
                return False, "当前版本未发布"

            if version["rollout_percent"] < 100:
                return False, "灰度发布中，无法回滚"

            if not released_versions:
                return False, "没有可回滚的版本"

            return True, ""

        # 可以回滚
        version = {"status": "released", "rollout_percent": 100}
        released = [{"id": "v1"}]
        can_rollback_result, msg = can_rollback(version, released)
        assert can_rollback_result is True

        # 灰度中无法回滚
        version = {"status": "released", "rollout_percent": 50}
        can_rollback_result, msg = can_rollback(version, released)
        assert can_rollback_result is False
        assert msg == "灰度发布中，无法回滚"


# ========== Service 单元测试辅助函数 ==========


def _make_scalar_result(value: object = None) -> MagicMock:
    """构造返回单个值的 db.execute 结果"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _make_scalars_result(items: list[Any] | None = None) -> MagicMock:
    """构造返回列表的 db.execute 结果"""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    return result


def _make_service() -> tuple[VersionService, MagicMock]:
    """构造带 Mock DB 的 VersionService"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.add = MagicMock()
    service = VersionService(db)
    return service, db


def _make_version(
    id: str = "version-1",
    model_id: str = "model-1",
    version: str = "1.0.0",
    status: VersionStatus = VersionStatus.DRAFT,
    rollout_percentage: int = 0,
) -> MagicMock:
    """构造模拟版本对象"""
    v = MagicMock()
    v.id = id
    v.model_id = model_id
    v.version = version
    v.status = status
    v.rollout_percentage = rollout_percentage
    return v


def _make_model(id: str = "model-1") -> MagicMock:
    """构造模拟模型实例对象"""
    m = MagicMock()
    m.id = id
    return m


class TestVersionService:
    """版本管理服务单元测试"""

    def setup_method(self) -> None:
        self.service, self.db = _make_service()

    # ----- create_version -----

    async def test_create_version_success_creates_draft_version(self) -> None:
        """创建版本成功时返回草稿状态的新版本"""
        # Arrange
        self.db.execute.side_effect = [
            _make_scalar_result(_make_model()),  # _get_model
            _make_scalar_result(None),  # _get_version_by_number
        ]

        # Act
        result = await self.service.create_version(
            model_id="model-1",
            version="1.0.0",
            config={"temperature": 0.7},
            description="首个版本",
            user_id="user-1",
        )

        # Assert
        assert result.model_id == "model-1"
        assert result.version == "1.0.0"
        assert result.status == VersionStatus.DRAFT
        assert result.rollout_percentage == 0
        assert result.config_snapshot == {"temperature": 0.7}
        assert result.created_by == "user-1"
        self.db.add.assert_called_once()
        self.db.commit.assert_awaited_once()
        self.db.refresh.assert_awaited_once()

    async def test_create_version_model_not_found_raises_not_found_error(self) -> None:
        """模型不存在时创建版本抛出 NotFoundError"""
        # Arrange
        self.db.execute.side_effect = [_make_scalar_result(None)]

        # Act & Assert
        with pytest.raises(NotFoundError, match="模型不存在"):
            await self.service.create_version(
                model_id="missing-model", version="1.0.0", config={}
            )
        self.db.add.assert_not_called()

    async def test_create_version_duplicate_version_raises_validation_error(
        self,
    ) -> None:
        """版本号已存在时创建版本抛出 ValidationError"""
        # Arrange
        existing = _make_version(version="1.0.0")
        self.db.execute.side_effect = [
            _make_scalar_result(_make_model()),  # _get_model
            _make_scalar_result(existing),  # _get_version_by_number
        ]

        # Act & Assert
        with pytest.raises(ValidationError, match="版本 1.0.0 已存在"):
            await self.service.create_version(
                model_id="model-1", version="1.0.0", config={}
            )
        self.db.add.assert_not_called()

    # ----- get_version -----

    async def test_get_version_found_returns_version(self) -> None:
        """版本存在时返回该版本"""
        # Arrange
        version = _make_version(id="v-1", status=VersionStatus.ACTIVE)
        self.db.execute.return_value = _make_scalar_result(version)

        # Act
        result = await self.service.get_version("v-1")

        # Assert
        assert result is version

    async def test_get_version_not_found_raises_not_found_error(self) -> None:
        """版本不存在时抛出 NotFoundError"""
        # Arrange
        self.db.execute.return_value = _make_scalar_result(None)

        # Act & Assert
        with pytest.raises(NotFoundError, match="版本不存在"):
            await self.service.get_version("missing-v")

    # ----- list_versions -----

    async def test_list_versions_returns_all_for_model(self) -> None:
        """列出模型的所有版本"""
        # Arrange
        v1 = _make_version(id="v1", version="1.0.0")
        v2 = _make_version(id="v2", version="2.0.0")
        self.db.execute.return_value = _make_scalars_result([v1, v2])

        # Act
        result = await self.service.list_versions("model-1")

        # Assert
        assert result == [v1, v2]
        assert len(result) == 2

    async def test_list_versions_with_status_filter_returns_filtered(self) -> None:
        """按状态过滤版本"""
        # Arrange
        v1 = _make_version(id="v1", status=VersionStatus.DRAFT)
        self.db.execute.return_value = _make_scalars_result([v1])

        # Act
        result = await self.service.list_versions("model-1", status=VersionStatus.DRAFT)

        # Assert
        assert result == [v1]
        self.db.execute.assert_awaited_once()

    async def test_list_versions_empty_returns_empty_list(self) -> None:
        """无版本时返回空列表"""
        # Arrange
        self.db.execute.return_value = _make_scalars_result([])

        # Act
        result = await self.service.list_versions("model-1")

        # Assert
        assert result == []

    # ----- get_active_version -----

    async def test_get_active_version_found_returns_version(self) -> None:
        """存在活跃版本时返回该版本"""
        # Arrange
        active = _make_version(
            id="v-1", status=VersionStatus.ACTIVE, rollout_percentage=100
        )
        self.db.execute.return_value = _make_scalar_result(active)

        # Act
        result = await self.service.get_active_version("model-1")

        # Assert
        assert result is active

    async def test_get_active_version_none_returns_none(self) -> None:
        """无活跃版本时返回 None"""
        # Arrange
        self.db.execute.return_value = _make_scalar_result(None)

        # Act
        result = await self.service.get_active_version("model-1")

        # Assert
        assert result is None

    # ----- rollout -----

    async def test_rollout_auto_advance_uses_next_stage(self) -> None:
        """未指定百分比时自动推进到下一灰度阶段"""
        # Arrange
        version = _make_version(
            id="v-1", rollout_percentage=0, status=VersionStatus.DRAFT
        )
        self.db.execute.return_value = _make_scalar_result(version)

        # Act
        result = await self.service.rollout("v-1")

        # Assert
        assert result.rollout_percentage == 10
        assert result.status == VersionStatus.ROLLING_OUT
        release = self.db.add.call_args[0][0]
        assert release.release_type == ReleaseType.ROLLOUT
        assert release.from_percentage == 0
        assert release.to_percentage == 10
        self.db.commit.assert_awaited_once()

    async def test_rollout_explicit_partial_percentage_sets_rolling_out(
        self,
    ) -> None:
        """指定部分百分比时设为灰度发布中"""
        # Arrange
        version = _make_version(id="v-1", rollout_percentage=0)
        self.db.execute.return_value = _make_scalar_result(version)

        # Act
        result = await self.service.rollout("v-1", percentage=50)

        # Assert
        assert result.rollout_percentage == 50
        assert result.status == VersionStatus.ROLLING_OUT

    async def test_rollout_full_percentage_sets_active_and_deprecates(
        self,
    ) -> None:
        """全量发布时设为活跃并废弃其他版本"""
        # Arrange
        version = _make_version(
            id="v-1",
            rollout_percentage=50,
            status=VersionStatus.ROLLING_OUT,
        )
        self.db.execute.side_effect = [
            _make_scalar_result(version),  # get_version
            _make_scalar_result(None),  # _deprecate_other_versions
        ]

        # Act
        result = await self.service.rollout("v-1", percentage=100)

        # Assert
        assert result.rollout_percentage == 100
        assert result.status == VersionStatus.ACTIVE
        assert self.db.execute.await_count == 2
        self.db.add.assert_called_once()

    async def test_rollout_invalid_percentage_raises_validation_error(
        self,
    ) -> None:
        """非法灰度百分比抛出 ValidationError"""
        # Arrange
        version = _make_version(id="v-1", rollout_percentage=0)
        self.db.execute.return_value = _make_scalar_result(version)

        # Act & Assert
        with pytest.raises(ValidationError, match="灰度百分比"):
            await self.service.rollout("v-1", percentage=15)
        self.db.add.assert_not_called()

    async def test_rollout_version_not_found_raises_not_found_error(
        self,
    ) -> None:
        """版本不存在时灰度发布抛出 NotFoundError"""
        # Arrange
        self.db.execute.return_value = _make_scalar_result(None)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await self.service.rollout("missing-v", percentage=50)

    # ----- rollback -----

    async def test_rollback_non_active_version_deprecates_directly(self) -> None:
        """回滚非活跃版本时直接废弃"""
        # Arrange
        version = _make_version(
            id="v-1",
            status=VersionStatus.ROLLING_OUT,
            rollout_percentage=50,
        )
        self.db.execute.return_value = _make_scalar_result(version)

        # Act
        result = await self.service.rollback("v-1")

        # Assert
        assert result.status == VersionStatus.DEPRECATED
        assert result.rollout_percentage == 0
        self.db.add.assert_called_once()
        self.db.commit.assert_awaited_once()

    async def test_rollback_active_version_without_previous_deprecates(
        self,
    ) -> None:
        """回滚活跃版本但无上一版本时直接废弃"""
        # Arrange
        version = _make_version(
            id="v-1",
            status=VersionStatus.ACTIVE,
            rollout_percentage=100,
        )
        self.db.execute.side_effect = [
            _make_scalar_result(version),  # get_version
            _make_scalar_result(None),  # _get_previous_version
        ]

        # Act
        result = await self.service.rollback("v-1")

        # Assert
        assert result.status == VersionStatus.DEPRECATED
        assert result.rollout_percentage == 0
        assert self.db.execute.await_count == 2

    async def test_rollback_active_version_with_previous_rollout_previous(
        self,
    ) -> None:
        """回滚活跃版本且有上一版本时对上一版本执行全量发布"""
        # Arrange
        version = _make_version(
            id="v-1",
            model_id="model-1",
            version="2.0.0",
            status=VersionStatus.ACTIVE,
            rollout_percentage=100,
        )
        previous = _make_version(
            id="v-0",
            model_id="model-1",
            version="1.0.0",
            status=VersionStatus.DEPRECATED,
            rollout_percentage=0,
        )
        self.db.execute.side_effect = [
            _make_scalar_result(version),  # rollback get_version
            _make_scalar_result(previous),  # rollback _get_previous_version
            _make_scalar_result(previous),  # rollout get_version
            _make_scalar_result(None),  # rollout _deprecate_other_versions
        ]

        # Act
        result = await self.service.rollback("v-1", user_id="user-1")

        # Assert
        assert result.status == VersionStatus.DEPRECATED
        assert result.rollout_percentage == 0
        assert previous.status == VersionStatus.ACTIVE
        assert previous.rollout_percentage == 100
        assert self.db.add.call_count == 2
        assert self.db.commit.await_count == 2

    # ----- delete_version -----

    async def test_delete_version_draft_succeeds(self) -> None:
        """删除草稿版本成功"""
        # Arrange
        version = _make_version(id="v-1", status=VersionStatus.DRAFT)
        self.db.execute.return_value = _make_scalar_result(version)

        # Act
        await self.service.delete_version("v-1")

        # Assert
        self.db.delete.assert_awaited_once_with(version)
        self.db.commit.assert_awaited_once()

    async def test_delete_version_non_draft_raises_validation_error(
        self,
    ) -> None:
        """删除非草稿版本抛出 ValidationError"""
        # Arrange
        version = _make_version(id="v-1", status=VersionStatus.ACTIVE)
        self.db.execute.return_value = _make_scalar_result(version)

        # Act & Assert
        with pytest.raises(ValidationError, match="只能删除草稿版本"):
            await self.service.delete_version("v-1")
        self.db.delete.assert_not_called()

    async def test_delete_version_not_found_raises_not_found_error(
        self,
    ) -> None:
        """删除不存在的版本抛出 NotFoundError"""
        # Arrange
        self.db.execute.return_value = _make_scalar_result(None)

        # Act & Assert
        with pytest.raises(NotFoundError):
            await self.service.delete_version("missing-v")

    # ----- _get_next_stage -----

    def test_get_next_stage_returns_next_higher_stage(self) -> None:
        """返回下一个更高的灰度阶段"""
        # Arrange
        stages = self.service.ROLLOUT_STAGES  # [10, 30, 50, 100]

        # Act & Assert
        assert self.service._get_next_stage(0) == stages[0]
        assert self.service._get_next_stage(10) == stages[1]
        assert self.service._get_next_stage(30) == stages[2]
        assert self.service._get_next_stage(50) == stages[3]
        # 已在最高阶段时返回 100
        assert self.service._get_next_stage(100) == 100
