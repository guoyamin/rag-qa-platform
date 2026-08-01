from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditAction, AuditLevel, AuditLog

logger = structlog.get_logger(__name__)


class AuditService:
    """审计日志服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: AuditAction,
        user_id: str | None = None,
        username: str | None = None,
        user_role: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        target_name: str | None = None,
        method: str | None = None,
        path: str | None = None,
        request_data: dict[str, Any] | None = None,
        response_status: int | None = None,
        success: bool = True,
        error_message: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        level: AuditLevel = AuditLevel.INFO,
    ) -> AuditLog:
        """
        记录审计日志

        Args:
            action: 操作类型
            user_id: 操作用户ID
            username: 操作用户名
            user_role: 操作用户角色
            target_type: 目标类型
            target_id: 目标ID
            target_name: 目标名称
            method: HTTP方法
            path: 请求路径
            request_data: 请求数据（会自动脱敏）
            response_status: 响应状态码
            success: 是否成功
            error_message: 错误信息
            ip_address: 客户端IP
            user_agent: User-Agent
            level: 日志级别
        """
        # 脱敏处理
        sanitized_data = self._sanitize_request_data(request_data)

        audit_log = AuditLog(
            action=action,
            level=level,
            user_id=user_id,
            username=username,
            user_role=user_role,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            method=method,
            path=path,
            request_data=json.dumps(sanitized_data) if sanitized_data else None,
            response_status=response_status,
            success=success,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)

        logger.info(
            "audit_logged",
            action=action.value,
            user=username,
            target=target_type,
            success=success,
        )

        return audit_log

    def _sanitize_request_data(
        self, data: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """
        脱敏处理

        移除敏感字段
        """
        if not data:
            return None

        sensitive_fields = {
            "password",
            "old_password",
            "new_password",
            "api_key",
            "secret",
            "token",
            "access_token",
            "refresh_token",
            "secret_key",
            "private_key",
        }

        sanitized: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in sensitive_fields:
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_request_data(value)
            else:
                sanitized[key] = value

        return sanitized

    async def get_logs(
        self,
        user_id: str | None = None,
        action: AuditAction | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AuditLog], int]:
        """查询审计日志"""
        query = select(AuditLog)

        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
        if target_type:
            query = query.where(AuditLog.target_type == target_type)
        if target_id:
            query = query.where(AuditLog.target_id == target_id)
        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)

        # 统计总数
        count_result = await self.db.execute(
            select(func.count(AuditLog.id)).select_from(AuditLog)
        )
        total = count_result.scalar() or 0

        # 分页
        query = query.order_by(AuditLog.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_user_activity(
        self,
        user_id: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """获取用户活动统计"""
        from datetime import timedelta

        start_date = datetime.now() - timedelta(days=days)

        query = (
            select(
                AuditLog.action,
                func.count(AuditLog.id).label("count"),
            )
            .where(AuditLog.user_id == user_id)
            .where(AuditLog.created_at >= start_date)
            .group_by(AuditLog.action)
            .order_by(func.count(AuditLog.id).desc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [{"action": row.action.value, "count": row.count} for row in rows]
