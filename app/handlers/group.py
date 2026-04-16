import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.events import get_event_by_chat_id
from app.services.questionnaire import get_confirmed_profile, mark_participant_joined
from app.services.users import (
    get_user_by_telegram_id,
    get_user_by_username,
    upsert_telegram_user,
)

logger = logging.getLogger(__name__)
router = Router(name="group")


async def notify_organizers(
    bot: Bot,
    event_title: str,
    organizer_profile_text: str,
) -> None:
    settings = get_settings()

    text = (
        f"Новый участник вошел в чат встречи <b>{escape(event_title)}</b>\n\n"
        f"{organizer_profile_text}"
    )

    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.warning(
                "Не удалось отправить анкету организатору %s: %s",
                admin_id,
                exc,
            )


@router.message(Command("show_profile"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_show_profile(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    event = await get_event_by_chat_id(session, message.chat.id)
    if event is None:
        await message.answer("Этот чат не привязан к встрече.")
        return

    target_user = None

    if message.reply_to_message and message.reply_to_message.from_user:
        reply_user = message.reply_to_message.from_user
        if not reply_user.is_bot:
            await upsert_telegram_user(session, reply_user)
            target_user = await get_user_by_telegram_id(session, reply_user.id)

    if target_user is None:
        raw = (command.args or "").strip()
        if not raw:
            await message.answer(
                "Используй:\n"
                "<code>/show_profile @username</code>\n\n"
                "или ответь этой командой на сообщение участника."
            )
            return

        target_user = await get_user_by_username(session, raw)

    if target_user is None:
        await message.answer("Не удалось найти участника.")
        return

    profile = await get_confirmed_profile(session, event.id, target_user.id)
    if profile is None:
        await message.answer("У этого участника нет подтвержденной анкеты для этой встречи.")
        return

    await message.answer(
        f"👤 <b>Анкета участника</b>\n\n{profile.public_profile_text}"
    )


@router.message(F.chat.type.in_({"group", "supergroup"}), F.new_chat_members)
async def on_new_chat_members(
    message: Message,
    bot: Bot,
    session: AsyncSession,
) -> None:
    event = await get_event_by_chat_id(session, message.chat.id)
    if event is None:
        return

    for tg_user in message.new_chat_members:
        if tg_user.is_bot:
            continue

        await upsert_telegram_user(session, tg_user)
        user = await get_user_by_telegram_id(session, tg_user.id)
        if user is None:
            continue

        profile = await get_confirmed_profile(session, event.id, user.id)
        if profile is None:
            await message.answer(
                f"⚠️ У участника <b>{escape(tg_user.first_name)}</b> нет подтвержденной анкеты для этой встречи."
            )
            continue

        is_first_join = await mark_participant_joined(session, event.id, user.id)
        if not is_first_join:
            continue

        await message.answer(
            f"👋 Новый участник встречи\n\n{profile.public_profile_text}"
        )

        await notify_organizers(
            bot=bot,
            event_title=event.title,
            organizer_profile_text=profile.organizer_profile_text or "Полная анкета пока не собрана.",
        )