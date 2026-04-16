from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event, User


def slugify_event_title(title: str) -> str:
    raw = title.strip().lower()
    allowed = []

    for ch in raw:
        if ch.isalnum():
            allowed.append(ch)
        elif ch in {" ", "-", "_"}:
            allowed.append("-")

    slug = "".join(allowed)
    while "--" in slug:
        slug = slug.replace("--", "-")

    slug = slug.strip("-")
    return slug or "event"


async def generate_unique_event_slug(session: AsyncSession, title: str) -> str:
    base_slug = slugify_event_title(title)
    slug = base_slug
    counter = 2

    while True:
        stmt = select(Event).where(Event.slug == slug)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            return slug

        slug = f"{base_slug}-{counter}"
        counter += 1


async def list_open_events(session: AsyncSession) -> list[Event]:
    stmt = select(Event).where(Event.status == "open").order_by(Event.id.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_event_by_id(session: AsyncSession, event_id: int) -> Event | None:
    stmt = select(Event).where(Event.id == event_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_event_by_slug(session: AsyncSession, slug: str) -> Event | None:
    stmt = select(Event).where(Event.slug == slug)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_event_by_chat_id(session: AsyncSession, chat_id: int) -> Event | None:
    stmt = select(Event).where(Event.chat_id == chat_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def bind_event_to_chat(
    session: AsyncSession,
    event: Event,
    chat_id: int,
    chat_title: str | None,
) -> Event:
    event.chat_id = chat_id
    event.chat_title = chat_title

    await session.commit()
    await session.refresh(event)
    return event


async def create_event(
    session: AsyncSession,
    creator: User,
    title: str,
    city: str,
    place_name: str,
    start_at: str,
    description: str,
) -> Event:
    slug = await generate_unique_event_slug(session, title)

    event = Event(
        slug=slug,
        title=title.strip(),
        description=description.strip(),
        city=city.strip(),
        place_name=place_name.strip(),
        start_at=start_at.strip(),
        status="open",
        created_by_user_id=creator.id,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def create_demo_event(session: AsyncSession, creator: User) -> Event:
    stmt = select(Event).where(Event.slug == "demo-meetup")
    result = await session.execute(stmt)
    event = result.scalar_one_or_none()

    if event is not None:
        return event

    event = Event(
        slug="demo-meetup",
        title="Тестовая встреча",
        description="Первая тестовая встреча для проверки бота",
        city="Москва",
        place_name="Будет объявлено позже",
        start_at="Скоро",
        status="open",
        created_by_user_id=creator.id,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event