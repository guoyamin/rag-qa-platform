from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, cast

import hvac
import structlog

from app.core.exceptions import ValidationError

logger = structlog.get_logger(__name__)


@dataclass
class VaultConfig:
    """Vault 配置"""

    url: str
    role_id: str | None
    secret_id: str | None
    mount_point: str = "secret"
    kv_version: int = 2


class VaultClient:
    """
    HashiCorp Vault 客户端

    支持 AppRole 认证方式，适合服务间认证场景。
    封装了 KV Secret 的读写操作。

    使用方式:
        vault = VaultClient()
        vault.write_secret("api_keys/openai", {"key": "sk-xxx"})
        secret = vault.read_secret("api_keys/openai")
    """

    def __init__(
        self,
        url: str | None = None,
        role_id: str | None = None,
        secret_id: str | None = None,
        mount_point: str = "secret",
        kv_version: int = 2,
    ):
        """
        初始化 Vault 客户端

        Args:
            url: Vault 服务器地址，默认从环境变量 VAULT_ADDR 获取
            role_id: AppRole Role ID，默认从环境变量 VAULT_ROLE_ID 获取
            secret_id: AppRole Secret ID，默认从环境变量 VAULT_SECRET_ID 获取
            mount_point: KV Secret 挂载点，默认 secret
            kv_version: KV 版本，1 或 2
        """
        self.url = url or os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.role_id = role_id or os.getenv("VAULT_ROLE_ID")
        self.secret_id = secret_id or os.getenv("VAULT_SECRET_ID")
        self.mount_point = mount_point
        self.kv_version = kv_version
        self._client: hvac.Client | None = None

    @property
    def client(self) -> hvac.Client:
        """获取或创建 Vault 客户端（延迟初始化）"""
        if self._client is None:
            self._client = hvac.Client(url=self.url)
            self._authenticate()
        return self._client

    def _authenticate(self) -> None:
        """
        根据配置选择认证方式

        优先级:
        1. AppRole 认证（role_id + secret_id）
        2. Token 认证（VAULT_TOKEN 环境变量）
        3. 开发模式（未配置认证时，连接但跳过认证）
        """
        if self.role_id and self.secret_id:
            # AppRole 认证
            self._auth_approle()
        elif os.getenv("VAULT_TOKEN"):
            # Token 认证
            self._client.token = os.getenv("VAULT_TOKEN")  # type: ignore
        else:
            logger.warning(
                "vault_no_auth_configured",
                message="未配置 Vault 认证方式，将尝试无认证连接（仅限开发环境）",
            )

    def _auth_approle(self) -> None:
        """AppRole 认证"""
        if not self.role_id or not self.secret_id:
            raise ValidationError("AppRole 认证需要 role_id 和 secret_id")

        try:
            self._client.approle_login(  # type: ignore
                role_id=self.role_id,
                secret_id=self.secret_id,
            )
            logger.info("vault_approle_auth_success", url=self.url)
        except Exception as e:
            logger.error("vault_approle_auth_failed", error=str(e))
            raise

    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        if self._client is None:
            return False
        try:
            return self._client.is_authenticated()  # type: ignore
        except Exception:
            return False

    def write_secret(
        self,
        path: str,
        secret: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        写入 Secret 到 Vault

        Args:
            path: Secret 路径，如 "api_keys/openai"
            secret: Secret 数据（键值对）
            metadata: KV v2 的 metadata

        Returns:
            写入响应
        """
        try:
            if self.kv_version == 2:
                # KV v2 需要指定版本
                # 检查是否带版本后缀
                path_parts = path.split("/")
                if len(path_parts) >= 2:
                    # path 格式: secret/data/xxx 或 data/xxx
                    if path_parts[0] in ("data", "metadata"):
                        # 已经带了版本前缀，直接使用
                        pass
                    else:
                        # 需要添加 data 前缀
                        path = f"data/{path}"
                else:
                    path = f"data/{path}"

                response = self.client.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret=secret,
                    mount_point=self.mount_point,
                    metadata=metadata,
                )
            else:
                # KV v1
                response = self.client.secrets.kv.v1.create_or_update_secret(
                    path=path,
                    secret=secret,
                    mount_point=self.mount_point,
                )
            logger.info("vault_secret_written", path=path)
            return cast(dict[str, Any], response)
        except Exception as e:
            logger.error("vault_secret_write_failed", path=path, error=str(e))
            raise

    def read_secret(
        self, path: str, version: int | None = None
    ) -> dict[str, Any] | None:
        """
        从 Vault 读取 Secret

        Args:
            path: Secret 路径，如 "api_keys/openai"
            version: 指定版本号（仅 KV v2）

        Returns:
            Secret 数据，读取失败返回 None
        """
        try:
            # KV v2 需要添加 data 前缀
            if self.kv_version == 2:
                if not path.startswith("data/") and not path.startswith("metadata/"):
                    path = f"data/{path}"
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=self.mount_point,
                    version=version,
                )
            else:
                response = self.client.secrets.kv.v1.read_secret(
                    path=path,
                    mount_point=self.mount_point,
                )
            data = response.get("data", {}).get("data") or response.get("data", {})
            return cast(dict[str, Any] | None, data)
        except Exception as e:
            logger.warning("vault_secret_read_failed", path=path, error=str(e))
            return None

    def delete_secret(
        self, path: str, versions: list[int] | None = None
    ) -> dict[str, Any]:
        """
        删除 Secret

        Args:
            path: Secret 路径
            versions: KV v2 要删除的版本列表

        Returns:
            删除响应
        """
        try:
            if self.kv_version == 2:
                if not path.startswith("data/") and not path.startswith("metadata/"):
                    path = f"data/{path}"
                response = self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                    path=path,
                    mount_point=self.mount_point,
                )
            else:
                response = self.client.secrets.kv.v1.delete_secret(
                    path=path,
                    mount_point=self.mount_point,
                )
            logger.info("vault_secret_deleted", path=path)
            return cast(dict[str, Any], response)
        except Exception as e:
            logger.error("vault_secret_delete_failed", path=path, error=str(e))
            raise

    def list_secrets(self, path: str = "") -> list[str]:
        """
        列出路径下的所有 Secret

        Args:
            path: 目录路径

        Returns:
            Secret 路径列表
        """
        try:
            if self.kv_version == 2:
                if not path.startswith("metadata/"):
                    path = f"metadata/{path}" if path else "metadata"
                response = self.client.secrets.kv.v2.list_secrets(
                    path=path,
                    mount_point=self.mount_point,
                )
            else:
                response = self.client.secrets.kv.v1.list_secrets(
                    path=path,
                    mount_point=self.mount_point,
                )
            keys = response.get("data", {}).get("keys", [])
            return [k.rstrip("/") for k in keys]
        except Exception as e:
            logger.warning("vault_list_secrets_failed", path=path, error=str(e))
            return []

    def health_check(self) -> dict[str, Any]:
        """
        检查 Vault 健康状态

        Returns:
            健康状态信息
        """
        try:
            response = self.client.sys.read_health_status()
            return {
                "status": "healthy",
                "version": response.get("version"),
                "leader": response.get("leader"),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# 全局 Vault 客户端实例
_vault_client: VaultClient | None = None


def get_vault_client() -> VaultClient:
    """获取 Vault 客户端单例"""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
    return _vault_client


def init_vault_client(config: VaultConfig) -> VaultClient:
    """初始化 Vault 客户端（用于测试或配置注入）"""
    global _vault_client
    _vault_client = VaultClient(
        url=config.url,
        role_id=config.role_id,
        secret_id=config.secret_id,
        mount_point=config.mount_point,
        kv_version=config.kv_version,
    )
    return _vault_client
