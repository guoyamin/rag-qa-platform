from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.cost_alert import AlertLevel, AlertStatus, CostAlert
from app.models.usage_log import ModelUsageLog

logger = structlog.get_logger(__name__)


class CostAlertService:
    """成本告警服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_alert(
        self,
        alert_name: str,
        target_type: str,
        threshold_type: str,
        threshold_value: Decimal,
        level: str = AlertLevel.WARNING,
        target_id: str | None = None,
        description: str | None = None,
        auto_resolve: bool = False,
    ) -> CostAlert:
        """创建告警配置"""
        alert = CostAlert(
            alert_name=alert_name,
            target_type=target_type,
            target_id=target_id,
            threshold_type=threshold_type,
            threshold_value=threshold_value,
            level=level,
            status=AlertStatus.PENDING,
            current_value=Decimal("0"),
            message=description,
            auto_resolve=auto_resolve,
        )

        self.db.add(alert)
        await self.db.commit()
        await self.db.refresh(alert)

        logger.info("cost_alert_created", alert_id=alert.id, name=alert_name)
        return alert

    async def get_alert(self, alert_id: str) -> CostAlert:
        """获取告警"""
        result = await self.db.execute(
            select(CostAlert).where(CostAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            raise ValidationError("告警不存在")
        return alert

    async def list_alerts(
        self,
        target_type: str | None = None,
        target_id: str | None = None,
        status: str | None = None,
        is_enabled: bool | None = None,
    ) -> list[CostAlert]:
        """列出告警配置"""
        query = select(CostAlert)

        if target_type:
            query = query.where(CostAlert.target_type == target_type)
        if target_id:
            query = query.where(CostAlert.target_id == target_id)
        if status:
            query = query.where(CostAlert.status == status)
        if is_enabled is not None:
            query = query.where(CostAlert.is_enabled == is_enabled)

        query = query.order_by(CostAlert.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def check_costs(self) -> list[CostAlert]:
        """
        检查成本阈值

        定时任务调用，检查是否触发告警
        """
        # 获取所有启用的告警
        alerts = await self.list_alerts(is_enabled=True)

        triggered_alerts = []
        for alert in alerts:
            current_cost = await self._calculate_current_cost(alert)
            alert.current_value = current_cost

            # 检查是否超过阈值
            if current_cost >= alert.threshold_value:
                if alert.status in (AlertStatus.PENDING, AlertStatus.NOTIFIED):
                    # 告警已触发
                    continue

                # 触发新告警
                alert.status = AlertStatus.PENDING
                alert.triggered_at = datetime.now()
                alert.message = self._generate_alert_message(alert, current_cost)
                triggered_alerts.append(alert)

                logger.warning(
                    "cost_alert_triggered",
                    alert_id=alert.id,
                    name=alert.alert_name,
                    current=current_cost,
                    threshold=alert.threshold_value,
                )

        if triggered_alerts:
            await self.db.commit()

        return triggered_alerts

    async def resolve_alert(
        self,
        alert_id: str,
        resolved_by: str | None = None,
        auto: bool = False,
    ) -> CostAlert:
        """解决告警"""
        alert = await self.get_alert(alert_id)

        alert.status = AlertStatus.AUTO_RESOLVED if auto else AlertStatus.RESOLVED
        alert.resolved_at = datetime.now()
        alert.resolved_by = resolved_by

        await self.db.commit()
        await self.db.refresh(alert)

        logger.info("cost_alert_resolved", alert_id=alert_id, auto=auto)
        return alert

    async def acknowledge_alert(self, alert_id: str) -> CostAlert:
        """确认告警"""
        alert = await self.get_alert(alert_id)
        alert.status = AlertStatus.ACKNOWLEDGED
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def delete_alert(self, alert_id: str) -> None:
        """删除告警配置"""
        alert = await self.get_alert(alert_id)
        await self.db.delete(alert)
        await self.db.commit()

    async def _calculate_current_cost(self, alert: CostAlert) -> Decimal:
        """计算当前成本"""
        # 确定时间范围
        now = datetime.now()
        if alert.threshold_type == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif alert.threshold_type == "monthly":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            # total: 不限制时间
            start = None

        # 查询成本
        query = select(func.sum(ModelUsageLog.cost)).select_from(ModelUsageLog)

        if alert.target_type == "model" and alert.target_id:
            query = query.where(ModelUsageLog.model_id == alert.target_id)
        elif alert.target_type == "user" and alert.target_id:
            query = query.where(ModelUsageLog.user_id == alert.target_id)

        if start:
            query = query.where(ModelUsageLog.created_at >= start)

        result = await self.db.execute(query)
        total_cost = result.scalar() or Decimal("0")
        return Decimal(str(total_cost))

    def _generate_alert_message(self, alert: CostAlert, current_cost: Decimal) -> str:
        """生成告警消息"""
        percentage = (current_cost / alert.threshold_value * 100).quantize(
            Decimal("0.1")
        )
        return (
            f"{alert.alert_name} 已超过阈值："
            f"当前 {current_cost:.4f} 元，"
            f"阈值 {alert.threshold_value:.4f} 元，"
            f"占比 {percentage}%"
        )
