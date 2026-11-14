# 文件说明：运维命令行工具：promote_admin。
import argparse
import asyncio

from sqlalchemy import select, update

from app.db.session import async_session_factory, engine
from app.models.user import User


async def promote(email: str) -> bool:
    normalized = email.strip().lower()
    async with async_session_factory() as session:
        exists = await session.scalar(
            select(User.id).where(User.email == normalized)
        )
        if exists is None:
            return False
        await session.execute(
            update(User).where(User.email == normalized).values(role="admin")
        )
        await session.commit()
        return True


async def main_async(email: str) -> int:
    try:
        promoted = await promote(email)
    finally:
        await engine.dispose()
    if not promoted:
        print(f"User not found: {email}")
        return 1
    print(f"Promoted admin: {email.strip().lower()}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote a TripMate user to admin")
    parser.add_argument("email")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args.email)))


if __name__ == "__main__":
    main()
