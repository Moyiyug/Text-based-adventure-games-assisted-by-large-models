"""Seed an admin user into the database. Idempotent — skips if admin already exists."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.core.security import hash_password
from app.models import Base  # noqa: F401
from app.models.user import User

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_DISPLAY_NAME = "管理员"


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == ADMIN_USERNAME)
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"[skip] Admin user '{ADMIN_USERNAME}' already exists (id={existing.id}).")
            return

        admin = User(
            username=ADMIN_USERNAME,
            password_hash=hash_password(ADMIN_PASSWORD),
            display_name=ADMIN_DISPLAY_NAME,
            role="admin",
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        print(f"[done] Admin user created: id={admin.id}, username={admin.username}")


if __name__ == "__main__":
    asyncio.run(seed())
