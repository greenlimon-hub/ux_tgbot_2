from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


async def log_action(
    session: AsyncSession,
    actor_user_id: int,
    action: str,
    event_id: int | None = None,
    payload_json: dict | None = None,
) -> None:
    log = AuditLog(
        actor_user_id=actor_user_id,
        event_id=event_id,
        action=action,
        payload_json=payload_json,
    )
    session.add(log)
    await session.commit()