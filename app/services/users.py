from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.types import User as TelegramUser

from app.db.models import User


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    normalized = username.strip().lstrip("@").lower()
    if not normalized:
        return None

    stmt = select(User).where(func.lower(User.username) == normalized)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_telegram_user(session: AsyncSession, tg_user: TelegramUser) -> User:
    user = await get_user_by_telegram_id(session, tg_user.id)

    if user is None:
        user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code,
        )
        session.add(user)
    else:
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name
        user.language_code = tg_user.language_code

    await session.commit()
    await session.refresh(user)
    return user