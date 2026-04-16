from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.announcements import (
    parse_meeting_args,
    parse_poll_args,
    parse_when_args,
    parse_where_args,
    render_announce_message,
    render_important_message,
    render_meeting_message,
    render_when_message,
    render_where_message,
)
from app.services.audit import log_action
from app.services.events import (
    bind_event_to_chat,
    create_demo_event,
    create_event,
    get_event_by_chat_id,
    get_event_by_id,
    get_event_by_slug,
    list_open_events,
)
from app.services.permissions import is_admin_or_organizer
from app.services.users import get_user_by_telegram_id, upsert_telegram_user

router = Router(name="admin")


def parse_create_event_args(raw: str) -> tuple[str, str, str, str, str]:
    parts = [part.strip() for part in raw.split("|") if part.strip()]

    if len(parts) != 5:
        raise ValueError(
            "Неверный формат.\n\n"
            "Используй:\n"
            "<code>/create_event Название | Город | Место | Время | Описание</code>\n\n"
            "Пример:\n"
            "<code>/create_event Встреча студентов МИЭМ | Москва | Антикафе «Точка» | 25 апреля, 18:30 | знакомство, разговоры и мини-игры</code>"
        )

    title, city, place_name, start_at, description = parts

    if len(title) > 255:
        raise ValueError("Название слишком длинное. Максимум: 255 символов.")
    if len(city) > 128:
        raise ValueError("Город слишком длинный. Максимум: 128 символов.")
    if len(place_name) > 255:
        raise ValueError("Место слишком длинное. Максимум: 255 символов.")
    if len(start_at) > 64:
        raise ValueError("Поле времени слишком длинное. Максимум: 64 символа.")

    return title, city, place_name, start_at, description


async def get_local_user_id(session: AsyncSession, message: Message) -> int | None:
    if message.from_user is None:
        return None

    await upsert_telegram_user(session, message.from_user)
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if user is None:
        return None

    return user.id


async def get_bound_event_id(session: AsyncSession, chat_id: int) -> int | None:
    event = await get_event_by_chat_id(session, chat_id)
    if event is None:
        return None
    return event.id


async def ensure_group_organizer(session: AsyncSession, message: Message) -> tuple[bool, int | None, int | None]:
    if message.from_user is None:
        return False, None, None

    event_id = await get_bound_event_id(session, message.chat.id)
    allowed = await is_admin_or_organizer(
        session=session,
        telegram_id=message.from_user.id,
        event_id=event_id,
    )

    user_id = await get_local_user_id(session, message)
    return allowed, event_id, user_id


async def try_delete_command_message(message: Message) -> None:
    try:
        await message.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


@router.message(Command("whoami"))
async def cmd_whoami(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return

    await upsert_telegram_user(session, message.from_user)

    admin_status = await is_admin_or_organizer(
        session=session,
        telegram_id=message.from_user.id,
    )

    username = f"@{message.from_user.username}" if message.from_user.username else "нет username"

    await message.answer(
        f"<b>Твои данные:</b>\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Username: {username}\n"
        f"Admin: {'да' if admin_status else 'нет'}"
    )


@router.message(Command("create_demo_event"), F.chat.type == "private")
async def cmd_create_demo_event(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return

    allowed = await is_admin_or_organizer(session, message.from_user.id)
    if not allowed:
        await message.answer(
            "Эта команда доступна только администратору.\n"
            "Добавь свой Telegram ID в ADMINS в файле .env"
        )
        return

    user = await upsert_telegram_user(session, message.from_user)
    event = await create_demo_event(session, user)

    await message.answer(
        "Демо-встреча готова.\n\n"
        f"ID: <code>{event.id}</code>\n"
        f"Slug: <code>{event.slug}</code>\n"
        f"Название: <b>{event.title}</b>\n\n"
        "Теперь команда /events будет показывать эту встречу."
    )


@router.message(Command("create_event"), F.chat.type == "private")
async def cmd_create_event(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    if message.from_user is None:
        return

    allowed = await is_admin_or_organizer(session, message.from_user.id)
    if not allowed:
        await message.answer(
            "Эта команда доступна только организатору или администратору."
        )
        return

    raw = (command.args or "").strip()
    if not raw:
        await message.answer(
            "Используй:\n"
            "<code>/create_event Название | Город | Место | Время | Описание</code>\n\n"
            "Пример:\n"
            "<code>/create_event Встреча студентов МИЭМ | Москва | Антикафе «Точка» | 25 апреля, 18:30 | знакомство, разговоры и мини-игры</code>"
        )
        return

    try:
        title, city, place_name, start_at, description = parse_create_event_args(raw)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    user = await upsert_telegram_user(session, message.from_user)
    event = await create_event(
        session=session,
        creator=user,
        title=title,
        city=city,
        place_name=place_name,
        start_at=start_at,
        description=description,
    )

    await message.answer(
        "Встреча создана ✅\n\n"
        f"<b>Название:</b> {event.title}\n"
        f"<b>Город:</b> {event.city or '—'}\n"
        f"<b>Место:</b> {event.place_name or '—'}\n"
        f"<b>Время:</b> {event.start_at or '—'}\n"
        f"<b>Описание:</b> {event.description or '—'}\n"
        f"<b>ID:</b> <code>{event.id}</code>\n"
        f"<b>Slug:</b> <code>{event.slug}</code>\n\n"
        "Теперь можно:\n"
        "1. добавить бота в групповой чат встречи\n"
        f"2. привязать чат командой <code>/bind_event {event.slug}</code>"
    )


@router.message(Command("bind_event"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_bind_event(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    if message.from_user is None:
        return

    allowed = await is_admin_or_organizer(session, message.from_user.id)
    if not allowed:
        await message.answer("Эта команда доступна только организатору или администратору.")
        return

    arg = (command.args or "").strip()

    event = None
    if arg:
        if arg.isdigit():
            event = await get_event_by_id(session, int(arg))
        else:
            event = await get_event_by_slug(session, arg)
    else:
        open_events = await list_open_events(session)
        if len(open_events) == 1:
            event = open_events[0]

    if event is None:
        await message.answer(
            "Не удалось определить встречу.\n\n"
            "Используй команду так:\n"
            "<code>/bind_event demo-meetup</code>\n"
            "или\n"
            "<code>/bind_event 1</code>"
        )
        return

    await bind_event_to_chat(
        session=session,
        event=event,
        chat_id=message.chat.id,
        chat_title=message.chat.title,
    )

    await message.answer(
        f"Чат привязан к встрече <b>{event.title}</b>.\n\n"
        f"chat_id: <code>{message.chat.id}</code>\n"
        f"slug: <code>{event.slug}</code>\n\n"
        "Теперь при вступлении участника с подтвержденной анкетой бот будет публиковать его карточку."
    )


@router.message(Command("announce"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_announce(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    allowed, event_id, actor_user_id = await ensure_group_organizer(session, message)
    if not allowed or actor_user_id is None:
        await message.answer("Эта команда доступна только организатору.")
        return

    text = (command.args or "").strip()
    if not text:
        await message.answer("Используй:\n<code>/announce Текст сообщения</code>")
        return

    await try_delete_command_message(message)
    await message.answer(render_announce_message(text))

    await log_action(
        session=session,
        actor_user_id=actor_user_id,
        event_id=event_id,
        action="announce_sent",
        payload_json={"text": text},
    )


@router.message(Command("meeting"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_meeting(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    allowed, event_id, actor_user_id = await ensure_group_organizer(session, message)
    if not allowed or actor_user_id is None:
        await message.answer("Эта команда доступна только организатору.")
        return

    raw = (command.args or "").strip()
    try:
        date_time, place, description = parse_meeting_args(raw)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await try_delete_command_message(message)
    await message.answer(render_meeting_message(date_time, place, description))

    await log_action(
        session=session,
        actor_user_id=actor_user_id,
        event_id=event_id,
        action="meeting_announcement_sent",
        payload_json={
            "date_time": date_time,
            "place": place,
            "description": description,
        },
    )


@router.message(Command("where"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_where(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    allowed, event_id, actor_user_id = await ensure_group_organizer(session, message)
    if not allowed or actor_user_id is None:
        await message.answer("Эта команда доступна только организатору.")
        return

    raw = (command.args or "").strip()
    try:
        place, comment = parse_where_args(raw)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await try_delete_command_message(message)
    await message.answer(render_where_message(place, comment))

    await log_action(
        session=session,
        actor_user_id=actor_user_id,
        event_id=event_id,
        action="where_update_sent",
        payload_json={
            "place": place,
            "comment": comment,
        },
    )


@router.message(Command("when"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_when(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    allowed, event_id, actor_user_id = await ensure_group_organizer(session, message)
    if not allowed or actor_user_id is None:
        await message.answer("Эта команда доступна только организатору.")
        return

    raw = (command.args or "").strip()
    try:
        date_time, comment = parse_when_args(raw)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await try_delete_command_message(message)
    await message.answer(render_when_message(date_time, comment))

    await log_action(
        session=session,
        actor_user_id=actor_user_id,
        event_id=event_id,
        action="when_update_sent",
        payload_json={
            "date_time": date_time,
            "comment": comment,
        },
    )


@router.message(Command("important"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_important(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    allowed, event_id, actor_user_id = await ensure_group_organizer(session, message)
    if not allowed or actor_user_id is None:
        await message.answer("Эта команда доступна только организатору.")
        return

    text = (command.args or "").strip()
    if not text:
        await message.answer("Используй:\n<code>/important Важный текст</code>")
        return

    await try_delete_command_message(message)
    await message.answer(render_important_message(text))

    await log_action(
        session=session,
        actor_user_id=actor_user_id,
        event_id=event_id,
        action="important_message_sent",
        payload_json={"text": text},
    )


@router.message(Command("poll_custom"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_poll_custom(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    bot: Bot,
) -> None:
    allowed, event_id, actor_user_id = await ensure_group_organizer(session, message)
    if not allowed or actor_user_id is None:
        await message.answer("Эта команда доступна только организатору.")
        return

    raw = (command.args or "").strip()
    try:
        question, options = parse_poll_args(raw)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await try_delete_command_message(message)

    await bot.send_poll(
        chat_id=message.chat.id,
        question=question,
        options=options,
        is_anonymous=False,
        allows_multiple_answers=False,
    )

    await log_action(
        session=session,
        actor_user_id=actor_user_id,
        event_id=event_id,
        action="custom_poll_sent",
        payload_json={
            "question": question,
            "options": options,
        },
    )


@router.message(Command("get_db"))
async def cmd_get_db(message: Message, session: AsyncSession):
    """Отправить файл базы данных администратору"""
    from aiogram.types import FSInputFile
    import os
    
    if message.from_user is None:
        return
    
    allowed = await is_admin_or_organizer(session, message.from_user.id)
    if not allowed:
        await message.answer("Эта команда доступна только администратору.")
        return
    
    db_path = "app.db"
    
    if os.path.exists(db_path):
        await message.answer_document(
            document=FSInputFile(db_path),
            caption=f"База данных бота\nРазмер: {os.path.getsize(db_path)} байт"
        )
    else:
        await message.answer("Файл базы данных не найден.")
