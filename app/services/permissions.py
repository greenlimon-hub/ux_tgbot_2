from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Organizer
from app.services.users import get_user_by_telegram_id


async def is_admin_or_organizer(
    session: AsyncSession,
    telegram_id: int,
    event_id: int | None = None,
) -> bool:
    settings = get_settings()

    if telegram_id in settings.admin_ids:
        return True

    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        return False

    stmt = select(Organizer).where(Organizer.user_id == user.id)

    if event_id is None:
        stmt = stmt.where(Organizer.event_id.is_(None))
    else:
        stmt = stmt.where(
            or_(
                Organizer.event_id == event_id,
                Organizer.event_id.is_(None),
            )
        )

    result = await session.execute(stmt)
    organizer = result.scalar_one_or_none()
    return organizer is not None