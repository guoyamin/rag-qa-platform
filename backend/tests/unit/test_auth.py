"""
认证服务单元测试
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User, UserAuthType, UserRole, UserStatus
from app.schemas import LoginRequest, UserCreate
from app.services.auth_service import AuthService


def _make_scalar_result(return_value):
    """创建模拟数据库标量查询结果"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = return_value
    return result


def _make_ldap_entry(
    cn="测试用户", mail="test@example.com", dn="cn=test,dc=example,dc=com"
):
    """创建模拟LDAP条目"""
    entry = MagicMock()
    entry.entry_dn = dn
    entry.cn = cn
    entry.mail = mail
    return entry


def _make_mock_ldap3(entries, bound=True):
    """创建模拟ldap3模块及其连接"""
    mock_mod = MagicMock()
    mock_mod.SUBTREE = "subtree"
    search_conn = MagicMock()
    search_conn.entries = entries
    auth_conn = MagicMock()
    auth_conn.bound = bound
    mock_mod.Connection.side_effect = [search_conn, auth_conn]
    return mock_mod


class TestAuthService:
    """认证服务测试"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def test_user(self):
        """测试用户"""
        user = User(
            id="test-uuid",
            username="testuser",
            email="test@example.com",
            display_name="测试用户",
            hashed_password=get_password_hash("password123"),
            auth_type=UserAuthType.LOCAL,
            role=UserRole.STAFF,
            status=UserStatus.ACTIVE,
            login_count=0,
            failed_login_count=0,
        )
        return user

    # ========== 既有测试 ==========

    @pytest.mark.asyncio
    async def test_local_auth_success(self, mock_db, test_user):
        """测试本地认证成功"""
        # 模拟查询结果
        result = MagicMock()
        result.scalar_one_or_none.return_value = test_user
        mock_db.execute.return_value = result

        auth_service = AuthService(mock_db)
        login_data = LoginRequest(username="testuser", password="password123")

        token_response = await auth_service.authenticate(login_data)

        assert token_response.access_token is not None
        assert token_response.refresh_token is not None
        assert token_response.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_local_auth_wrong_password(self, mock_db, test_user):
        """测试本地认证密码错误"""
        result = MagicMock()
        result.scalar_one_or_none.return_value = test_user
        mock_db.execute.return_value = result

        auth_service = AuthService(mock_db)
        login_data = LoginRequest(username="testuser", password="wrongpassword")

        with pytest.raises(Exception) as exc_info:
            await auth_service.authenticate(login_data)

        assert "401" in str(exc_info.value) or "用户名或密码错误" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_local_auth_user_not_found(self, mock_db):
        """测试本地认证用户不存在"""
        mock_db.execute.return_value = _make_scalar_result(None)

        auth_service = AuthService(mock_db)
        login_data = LoginRequest(username="nonexistent", password="password123")

        with pytest.raises(AuthenticationError):
            await auth_service.authenticate(login_data)

    def test_password_hash(self):
        """测试密码哈希"""
        password = "testpassword"
        hashed = get_password_hash(password)

        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrongpassword", hashed) is False

    def test_create_access_token(self):
        """测试创建访问Token"""
        user_id = "test-user-id"
        token = create_access_token(subject=user_id)

        assert token is not None
        assert isinstance(token, str)

    # ========== _local_auth 测试 ==========

    @pytest.mark.asyncio
    async def test_local_auth_wrong_auth_type_returns_none(self, mock_db, test_user):
        """非本地认证类型用户本地登录返回None"""
        # Arrange
        test_user.auth_type = UserAuthType.LDAP
        mock_db.execute.return_value = _make_scalar_result(test_user)
        service = AuthService(mock_db)

        # Act
        user = await service._local_auth("testuser", "password123")

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_local_auth_no_hashed_password_returns_none(self, mock_db, test_user):
        """无密码哈希用户本地登录返回None"""
        # Arrange
        test_user.hashed_password = None
        mock_db.execute.return_value = _make_scalar_result(test_user)
        service = AuthService(mock_db)

        # Act
        user = await service._local_auth("testuser", "password123")

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_local_auth_locked_user_raises_authorization(
        self, mock_db, test_user
    ):
        """锁定用户本地登录抛出AuthorizationError"""
        # Arrange
        test_user.status = UserStatus.LOCKED
        mock_db.execute.return_value = _make_scalar_result(test_user)
        service = AuthService(mock_db)

        # Act & Assert
        with pytest.raises(AuthorizationError, match="账号已锁定"):
            await service._local_auth("testuser", "password123")

    @pytest.mark.asyncio
    async def test_local_auth_wrong_password_increments_fail_count(
        self, mock_db, test_user
    ):
        """密码错误时失败登录次数递增"""
        # Arrange
        mock_db.execute.return_value = _make_scalar_result(test_user)
        service = AuthService(mock_db)

        # Act
        user = await service._local_auth("testuser", "wrongpassword")

        # Assert
        assert user is None
        assert test_user.failed_login_count == 1
        assert test_user.status == UserStatus.ACTIVE
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_local_auth_fail_count_reaches_five_locks_account(
        self, mock_db, test_user
    ):
        """失败次数达到五次锁定账号"""
        # Arrange
        test_user.failed_login_count = 4
        mock_db.execute.return_value = _make_scalar_result(test_user)
        service = AuthService(mock_db)

        # Act
        user = await service._local_auth("testuser", "wrongpassword")

        # Assert
        assert user is None
        assert test_user.failed_login_count == 5
        assert test_user.status == UserStatus.LOCKED

    # ========== authenticate 路由测试 ==========

    @pytest.mark.asyncio
    async def test_authenticate_local_mode_explicit_success(self, mock_db, test_user):
        """显式local模式认证成功"""
        # Arrange
        mock_db.execute.return_value = _make_scalar_result(test_user)
        service = AuthService(mock_db)
        login_data = LoginRequest(
            username="testuser", password="password123", auth_type="local"
        )

        # Act
        response = await service.authenticate(login_data)

        # Assert
        assert response.access_token is not None

    @pytest.mark.asyncio
    async def test_authenticate_ldap_mode_success(self, mock_db, test_user):
        """ldap模式认证成功"""
        # Arrange
        service = AuthService(mock_db)
        login_data = LoginRequest(
            username="testuser", password="password123", auth_type="ldap"
        )

        # Act
        with patch.object(service, "_ldap_auth", AsyncMock(return_value=test_user)):
            response = await service.authenticate(login_data)

        # Assert
        assert response.access_token is not None

    @pytest.mark.asyncio
    async def test_authenticate_hybrid_local_fail_ldap_success(
        self, mock_db, test_user
    ):
        """hybrid模式本地失败后LDAP认证成功"""
        # Arrange
        mock_db.execute.return_value = _make_scalar_result(None)
        service = AuthService(mock_db)
        login_data = LoginRequest(username="testuser", password="password123")

        # Act
        with (
            patch.object(service, "_ldap_auth", AsyncMock(return_value=test_user)),
            patch.object(settings, "LDAP_SERVER", "ldap://example.com"),
        ):
            response = await service.authenticate(login_data)

        # Assert
        assert response.access_token is not None

    @pytest.mark.asyncio
    async def test_authenticate_all_methods_fail_raises_authentication(self, mock_db):
        """所有认证方式均失败抛出AuthenticationError"""
        # Arrange
        mock_db.execute.return_value = _make_scalar_result(None)
        service = AuthService(mock_db)
        login_data = LoginRequest(username="testuser", password="password123")

        # Act & Assert
        with (
            patch.object(service, "_ldap_auth", AsyncMock(return_value=None)),
            patch.object(settings, "LDAP_SERVER", "ldap://example.com"),
            pytest.raises(AuthenticationError, match="用户名或密码错误"),
        ):
            await service.authenticate(login_data)

    @pytest.mark.asyncio
    async def test_authenticate_locked_user_raises_authorization(
        self, mock_db, test_user
    ):
        """锁定用户认证抛出AuthorizationError"""
        # Arrange
        test_user.status = UserStatus.LOCKED
        mock_db.execute.return_value = _make_scalar_result(test_user)
        service = AuthService(mock_db)
        login_data = LoginRequest(username="testuser", password="password123")

        # Act & Assert
        with pytest.raises(AuthorizationError, match="账号已锁定"):
            await service.authenticate(login_data)

    # ========== _ldap_auth 测试 ==========

    @pytest.mark.asyncio
    async def test_ldap_auth_import_error_returns_none(self, mock_db):
        """ldap3未安装时返回None"""
        # Arrange
        service = AuthService(mock_db)

        # Act
        with patch.dict("sys.modules", {"ldap3": None}):
            user = await service._ldap_auth("testuser", "password")

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_ldap_auth_connection_exception_returns_none(self, mock_db):
        """LDAP连接异常时返回None"""
        # Arrange
        mock_mod = MagicMock()
        mock_mod.SUBTREE = "subtree"
        mock_mod.Server = MagicMock()
        mock_mod.Connection.side_effect = Exception("connection failed")
        service = AuthService(mock_db)

        # Act
        with patch.dict("sys.modules", {"ldap3": mock_mod}):
            user = await service._ldap_auth("testuser", "password")

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_ldap_auth_no_entries_returns_none(self, mock_db):
        """LDAP搜索无结果返回None"""
        # Arrange
        mock_mod = _make_mock_ldap3(entries=[])
        service = AuthService(mock_db)

        # Act
        with patch.dict("sys.modules", {"ldap3": mock_mod}):
            user = await service._ldap_auth("testuser", "password")

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_ldap_auth_bind_fails_returns_none(self, mock_db):
        """LDAP用户绑定失败返回None"""
        # Arrange
        entry = _make_ldap_entry()
        mock_mod = _make_mock_ldap3(entries=[entry], bound=False)
        service = AuthService(mock_db)

        # Act
        with patch.dict("sys.modules", {"ldap3": mock_mod}):
            user = await service._ldap_auth("testuser", "password")

        # Assert
        assert user is None

    @pytest.mark.asyncio
    async def test_ldap_auth_success_creates_new_user(self, mock_db):
        """LDAP认证成功且创建新本地用户"""
        # Arrange
        entry = _make_ldap_entry()
        mock_mod = _make_mock_ldap3(entries=[entry], bound=True)
        mock_db.execute.return_value = _make_scalar_result(None)
        service = AuthService(mock_db)

        # Act
        with (
            patch.dict("sys.modules", {"ldap3": mock_mod}),
            patch.object(settings, "LDAP_SERVER", "ldap://example.com"),
            patch.object(settings, "LDAP_BASE_DN", "dc=example,dc=com"),
        ):
            user = await service._ldap_auth("testuser", "password")

        # Assert
        assert user is not None
        assert user.username == "testuser"
        assert user.auth_type == UserAuthType.LDAP
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_ldap_auth_success_updates_existing_user(self, mock_db, test_user):
        """LDAP认证成功且更新已有本地用户"""
        # Arrange
        entry = _make_ldap_entry()
        mock_mod = _make_mock_ldap3(entries=[entry], bound=True)
        test_user.auth_type = UserAuthType.LOCAL
        mock_db.execute.return_value = _make_scalar_result(test_user)
        service = AuthService(mock_db)

        # Act
        with (
            patch.dict("sys.modules", {"ldap3": mock_mod}),
            patch.object(settings, "LDAP_SERVER", "ldap://example.com"),
            patch.object(settings, "LDAP_BASE_DN", "dc=example,dc=com"),
        ):
            user = await service._ldap_auth("testuser", "password")

        # Assert
        assert user is not None
        assert user.auth_type == UserAuthType.LDAP
        assert user.status == UserStatus.ACTIVE
        mock_db.add.assert_not_called()
        mock_db.commit.assert_called_once()

    # ========== refresh_token 测试 ==========

    @pytest.mark.asyncio
    async def test_refresh_token_valid_returns_new_token(self, mock_db, test_user):
        """有效刷新Token返回新Token"""
        # Arrange
        token = create_refresh_token(subject="test-uuid")
        mock_db.execute.return_value = _make_scalar_result(test_user)
        service = AuthService(mock_db)

        # Act
        response = await service.refresh_token(token)

        # Assert
        assert response.access_token is not None
        assert response.refresh_token is not None
        assert response.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_raises_authentication(self, mock_db):
        """无效刷新Token抛出AuthenticationError"""
        # Arrange
        service = AuthService(mock_db)

        # Act & Assert
        with pytest.raises(AuthenticationError, match="无效的刷新Token"):
            await service.refresh_token("invalid-token-string")

    @pytest.mark.asyncio
    async def test_refresh_token_wrong_type_raises_authentication(self, mock_db):
        """非refresh类型Token抛出AuthenticationError"""
        # Arrange
        token = create_access_token(subject="test-uuid")
        service = AuthService(mock_db)

        # Act & Assert
        with pytest.raises(AuthenticationError, match="无效的刷新Token"):
            await service.refresh_token(token)

    @pytest.mark.asyncio
    async def test_refresh_token_user_not_found_raises_authentication(self, mock_db):
        """刷新Token对应用户不存在抛出AuthenticationError"""
        # Arrange
        token = create_refresh_token(subject="test-uuid")
        mock_db.execute.return_value = _make_scalar_result(None)
        service = AuthService(mock_db)

        # Act & Assert
        with pytest.raises(AuthenticationError, match="用户不存在或已被禁用"):
            await service.refresh_token(token)

    @pytest.mark.asyncio
    async def test_refresh_token_user_inactive_raises_authentication(
        self, mock_db, test_user
    ):
        """刷新Token对应用户非活跃状态抛出AuthenticationError"""
        # Arrange
        token = create_refresh_token(subject="test-uuid")
        test_user.status = UserStatus.INACTIVE
        mock_db.execute.return_value = _make_scalar_result(test_user)
        service = AuthService(mock_db)

        # Act & Assert
        with pytest.raises(AuthenticationError, match="用户不存在或已被禁用"):
            await service.refresh_token(token)

    # ========== create_local_user 测试 ==========

    @pytest.mark.asyncio
    async def test_create_local_user_success_returns_user(self, mock_db):
        """创建本地用户成功"""
        # Arrange
        mock_db.execute.return_value = _make_scalar_result(None)
        service = AuthService(mock_db)
        user_data = UserCreate(
            username="newuser",
            email="new@example.com",
            password="password123",
            display_name="新用户",
            role="staff",
        )

        # Act
        user = await service.create_local_user(user_data)

        # Assert
        assert user.username == "newuser"
        assert user.auth_type == UserAuthType.LOCAL
        assert user.hashed_password is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_local_user_duplicate_raises_validation(
        self, mock_db, test_user
    ):
        """用户名已存在抛出ValidationError"""
        # Arrange
        mock_db.execute.return_value = _make_scalar_result(test_user)
        service = AuthService(mock_db)
        user_data = UserCreate(username="testuser", password="password123")

        # Act & Assert
        with pytest.raises(ValidationError, match="用户名已存在"):
            await service.create_local_user(user_data)

    # ========== change_password 测试 ==========

    @pytest.mark.asyncio
    async def test_change_password_success_returns_true(self, mock_db, test_user):
        """修改密码成功返回True"""
        # Arrange
        service = AuthService(mock_db)

        # Act
        result = await service.change_password(
            test_user, "password123", "newpassword123"
        )

        # Assert
        assert result is True
        assert verify_password("newpassword123", test_user.hashed_password or "")
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_change_password_ldap_user_raises_validation(
        self, mock_db, test_user
    ):
        """LDAP用户修改密码抛出ValidationError"""
        # Arrange
        test_user.auth_type = UserAuthType.LDAP
        service = AuthService(mock_db)

        # Act & Assert
        with pytest.raises(ValidationError, match="LDAP/SSO用户不能修改密码"):
            await service.change_password(test_user, "password123", "newpassword123")

    @pytest.mark.asyncio
    async def test_change_password_wrong_old_raises_validation(
        self, mock_db, test_user
    ):
        """原密码错误抛出ValidationError"""
        # Arrange
        service = AuthService(mock_db)

        # Act & Assert
        with pytest.raises(ValidationError, match="原密码错误"):
            await service.change_password(test_user, "wrongold", "newpassword123")
