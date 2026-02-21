"""Seed admin user on first run."""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import AdminUser
from app.auth import hash_password
from app.config import settings


async def seed_admin():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AdminUser).limit(1))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"Admin user already exists: {existing.username}")
            return
        admin = AdminUser(
            username=settings.ADMIN_USERNAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
        )
        db.add(admin)
        await db.commit()
        print(f"Created admin user: {settings.ADMIN_USERNAME}")


if __name__ == "__main__":
    asyncio.run(seed_admin())
