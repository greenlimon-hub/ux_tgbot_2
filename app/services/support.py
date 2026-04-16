from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SupportAdminNotification, SupportRequest


async def create_support_request(
    session: AsyncSession,
    user_id: int,
    issue_text: str,
) -> SupportRequest:
    request = SupportRequest(
        user_id=user_id,
        issue_text=issue_text.strip(),
        status="open",
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def add_support_notification(
    session: AsyncSession,
    request_id: int,
    admin_telegram_id: int,
    chat_id: int,
    message_id: int,
) -> SupportAdminNotification:
    notification = SupportAdminNotification(
        request_id=request_id,
        admin_telegram_id=admin_telegram_id,
        chat_id=chat_id,
        message_id=message_id,
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification


async def get_support_request(
    session: AsyncSession,
    request_id: int,
) -> SupportRequest | None:
    stmt = select(SupportRequest).where(SupportRequest.id == request_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_support_notifications(
    session: AsyncSession,
    request_id: int,
) -> list[SupportAdminNotification]:
    stmt = select(SupportAdminNotification).where(
        SupportAdminNotification.request_id == request_id
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def claim_support_request(
    session: AsyncSession,
    request_id: int,
    admin_telegram_id: int,
) -> tuple[SupportRequest | None, str]:
    request = await get_support_request(session, request_id)
    if request is None:
        return None, "not_found"

    if request.status == "closed":
        return request, "closed"

    if request.status == "claimed":
        if request.claimed_by_admin_telegram_id == admin_telegram_id:
            return request, "already_claimed_by_you"
        return request, "claimed_by_other"

    request.status = "claimed"
    request.claimed_by_admin_telegram_id = admin_telegram_id
    await session.commit()
    await session.refresh(request)
    return request, "claimed"


async def reopen_support_request(
    session: AsyncSession,
    request_id: int,
    admin_telegram_id: int,
) -> SupportRequest | None:
    request = await get_support_request(session, request_id)
    if request is None:
        return None

    if request.status == "claimed" and request.claimed_by_admin_telegram_id == admin_telegram_id:
        request.status = "open"
        request.claimed_by_admin_telegram_id = None
        await session.commit()
        await session.refresh(request)

    return request


async def close_support_request(
    session: AsyncSession,
    request_id: int,
    admin_telegram_id: int,
    response_text: str,
) -> SupportRequest | None:
    request = await get_support_request(session, request_id)
    if request is None:
        return None

    request.status = "closed"
    request.closed_by_admin_telegram_id = admin_telegram_id
    request.response_text = response_text
    await session.commit()
    await session.refresh(request)
    return request