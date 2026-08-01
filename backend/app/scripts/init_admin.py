"""
创建初始管理员账号
"""

import asyncio

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.user import User, UserAuthType, UserRole, UserStatus


async def create_admin() -> None:
    # 先确保所有表已创建
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("数据库表已就绪")

    async with AsyncSessionLocal() as session:
        # 检查是否已存在
        result = await session.execute(select(User).where(User.username == "admin"))
        existing = result.scalar_one_or_none()

        if existing:
            print("管理员账号已存在，跳过创建")
            return

        admin = User(
            username="admin",
            hashed_password=get_password_hash("admin123"),
            display_name="系统管理员",
            email="admin@example.com",
            auth_type=UserAuthType.LOCAL,
            role=UserRole.SUPER_ADMIN,
            status=UserStatus.ACTIVE,
            department="信息中心",
            position="系统管理员",
        )
        session.add(admin)
        await session.commit()
        print("管理员账号创建成功！")
        print("  用户名: admin")
        print("  密码: admin123")
        print("  角色: super_admin")


if __name__ == "__main__":
    asyncio.run(create_admin())
