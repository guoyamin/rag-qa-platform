from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Any, cast

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.api_key import ApiKey, ApiKeyStatus, ApiKeyUsage
from app.schemas.model import ApiKeyCreate, ApiKeyCreateResponse, ApiKeyUpdate
from app.services.vault_client import get_vault_client

logger = structlog.get_logger(__name__)


class ApiKeyService:
    """API Key 管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.vault = get_vault_client()

    @staticmethod
    def _generate_key_preview(api_key: str) -> str:
        """生成 Key 预览"""
        if len(api_key) <= 4:
            return api_key[:2] + "**"
        return f"{api_key[:2]}**{api_key[-2:]}"

    @staticmethod
    def _generate_vault_path(key_id: str) -> str:
        """生成 Vault 路径"""
        return f"api_keys/{key_id}"

    async def create(
        self,
        data: ApiKeyCreate,
        user_id: str | None = None,
    ) -> ApiKeyCreateResponse:
        """
        创建 API Key

        1. 生成唯一 ID
        2. 将 Key 加密存储到 Vault
        3. 在数据库存储元信息（不含明文 Key）
        4. 返回明文 Key（仅此次可见）
        """
        # 1. 生成唯一 ID
        key_id = str(uuid.uuid4())

        # 2. 存储到 Vault
        vault_path = self._generate_vault_path(key_id)
        self.vault.write_secret(
            path=vault_path,
            secret={"api_key": data.api_key},
        )

        # 3. 创建数据库记录
        api_key = ApiKey(
            id=key_id,
            name=data.name,
            provider=data.provider,
            vault_path=vault_path,
            key_preview=self._generate_key_preview(data.api_key),
            usage=ApiKeyUsage(data.usage.value),
            status=ApiKeyStatus.ACTIVE,
            expires_at=data.expires_at,
            description=data.description,
            created_by=user_id,
        )
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)

        logger.info(
            "api_key_created",
            key_id=key_id,
            name=data.name,
            provider=data.provider,
        )

        # 4. 返回明文 Key（仅此次可见）
        return ApiKeyCreateResponse(
            id=api_key.id,
            name=api_key.name,
            provider=api_key.provider,
            api_key=data.api_key,
            key_preview=api_key.key_preview,
            created_at=api_key.created_at,
        )

    async def get(self, key_id: str) -> ApiKey:
        """获取 API Key 元信息"""
        result = await self.db.execute(select(ApiKey).where(ApiKey.id == key_id))
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise NotFoundError("API Key 不存在")
        return api_key

    async def get_decrypted_key(self, key_id: str) -> str:
        """获取解密的 API Key"""
        api_key = await self.get(key_id)

        # 从 Vault 读取
        secret = self.vault.read_secret(api_key.vault_path)
        if not secret:
            raise NotFoundError("API Key 已失效，请重新配置")

        return cast(str, secret.get("api_key", ""))

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        provider: str | None = None,
        usage: str | None = None,
        status: str | None = None,
    ) -> tuple[list[ApiKey], int]:
        """列出 API Keys"""
        query = select(ApiKey)

        if provider:
            query = query.where(ApiKey.provider == provider)
        if usage:
            query = query.where(ApiKey.usage == ApiKeyUsage(usage))
        if status:
            query = query.where(ApiKey.status == ApiKeyStatus(status))

        # 统计总数
        count_result = await self.db.execute(
            select(func.count(ApiKey.id)).select_from(ApiKey)
        )
        total = count_result.scalar() or 0

        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update(
        self,
        key_id: str,
        data: ApiKeyUpdate,
    ) -> ApiKey:
        """更新 API Key"""
        api_key = await self.get(key_id)

        if data.name is not None:
            api_key.name = data.name

        if data.api_key is not None:
            # 重新加密存储
            self.vault.write_secret(
                path=api_key.vault_path,
                secret={"api_key": data.api_key},
            )
            api_key.key_preview = self._generate_key_preview(data.api_key)

        if data.status is not None:
            api_key.status = ApiKeyStatus(data.status.value)

        if data.expires_at is not None:
            api_key.expires_at = data.expires_at

        if data.description is not None:
            api_key.description = data.description

        await self.db.commit()
        await self.db.refresh(api_key)

        logger.info("api_key_updated", key_id=key_id)
        return api_key

    async def delete(self, key_id: str) -> None:
        """删除 API Key"""
        api_key = await self.get(key_id)

        # 从 Vault 删除
        try:
            self.vault.delete_secret(api_key.vault_path)
        except Exception as e:
            logger.warning("vault_delete_failed", path=api_key.vault_path, error=str(e))

        # 从数据库删除
        await self.db.delete(api_key)
        await self.db.commit()

        logger.info("api_key_deleted", key_id=key_id)

    async def rotate_key(self, key_id: str) -> ApiKeyCreateResponse:
        """轮换 API Key（重新生成）"""
        api_key = await self.get(key_id)

        # 生成新 Key
        new_key = f"sk-{secrets.token_urlsafe(32)}"

        # 更新 Vault
        self.vault.write_secret(
            path=api_key.vault_path,
            secret={"api_key": new_key},
        )

        # 更新预览
        api_key.key_preview = self._generate_key_preview(new_key)
        await self.db.commit()
        await self.db.refresh(api_key)

        logger.info("api_key_rotated", key_id=key_id)

        return ApiKeyCreateResponse(
            id=api_key.id,
            name=api_key.name,
            provider=api_key.provider,
            api_key=new_key,
            key_preview=api_key.key_preview,
            created_at=api_key.created_at,
        )

    async def record_usage(self, key_id: str) -> None:
        """记录使用"""
        api_key = await self.get(key_id)
        api_key.use_count += 1
        api_key.last_used_at = datetime.now()
        await self.db.commit()

    async def health_check(self) -> dict[str, Any]:
        """检查 Vault 健康状态"""
        return self.vault.health_check()
