from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.keyboards.inline import build_support_reply_keyboard
from app.services.support import (
    add_support_notification,
    claim_support_request,
    close_support_request,
    create_support_request,
    get_support_request,
    list_support_notifications,
    reopen_support_request,
)
from app.services.users import get_user_by_id, get_user_by_telegram_id, upsert_telegram_user
from app.support.callbacks import SupportReplyCallback
from app.support.states import SupportStates

router = Router(name="support")


def render_support_request_text(user, request_id: int, issue_text: str) -> str:
    username_line = f"@{escape(user.username)}" if user.username else "нет username"

    return (
        f"🆘 <b>Новое обращение #{request_id}</b>\n\n"
        f"<b>Имя:</b> {escape(user.first_name or '—')}\n"
        f"<b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
        f"<b>Username:</b> {username_line}\n\n"
        f"<b>Проблема:</b>\n{escape(issue_text)}"
    )


async def hide_support_buttons(bot: Bot, session: AsyncSession, request_id: int) -> None:
    notifications = await list_support_notifications(session, request_id)

    for notification in notifications:
        try:
            await bot.edit_message_reply_markup(
                chat_id=notification.chat_id,
                message_id=notification.message_id,
                reply_markup=None,
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            pass


async def restore_support_buttons(bot: Bot, session: AsyncSession, request_id: int) -> None:
    notifications = await list_support_notifications(session, request_id)

    for notification in notifications:
        try:
            await bot.edit_message_reply_markup(
                chat_id=notification.chat_id,
                message_id=notification.message_id,
                reply_markup=build_support_reply_keyboard(request_id),
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            pass


async def dispatch_support_request_to_admins(
    bot: Bot,
    session: AsyncSession,
    request_id: int,
    user,
    issue_text: str,
) -> int:
    settings = get_settings()
    delivered = 0

    text = render_support_request_text(user, request_id, issue_text)

    for admin_tg_id in settings.admin_ids:
        try:
            sent = await bot.send_message(
                admin_tg_id,
                text,
                reply_markup=build_support_reply_keyboard(request_id),
            )
            await add_support_notification(
                session=session,
                request_id=request_id,
                admin_telegram_id=admin_tg_id,
                chat_id=sent.chat.id,
                message_id=sent.message_id,
            )
            delivered += 1
        except (TelegramBadRequest, TelegramForbiddenError):
            continue

    return delivered


async def submit_support_issue(
    message: Message,
    issue_text: str,
    session: AsyncSession,
    bot: Bot,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    issue_text = issue_text.strip()
    if not issue_text:
        await message.answer("Опиши проблему текстом.")
        return

    if len(issue_text) > 2000:
        await message.answer("Сообщение слишком длинное. Максимум: 2000 символов.")
        return

    user = await upsert_telegram_user(session, message.from_user)
    request = await create_support_request(
        session=session,
        user_id=user.id,
        issue_text=issue_text,
    )

    delivered = await dispatch_support_request_to_admins(
        bot=bot,
        session=session,
        request_id=request.id,
        user=user,
        issue_text=issue_text,
    )

    await state.clear()

    if delivered == 0:
        await message.answer(
            "Я сохранил обращение, но не смог доставить его администраторам.\n"
            "Попробуй позже."
        )
        return

    await message.answer(
        f"Обращение отправлено администраторам ✅\n"
        f"Номер обращения: <code>{request.id}</code>"
    )


@router.message(Command("support"), F.chat.type == "private")
async def cmd_support(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    bot: Bot,
    state: FSMContext,
) -> None:
    text = (command.args or "").strip()

    if text:
        await submit_support_issue(message, text, session, bot, state)
        return

    await state.set_state(SupportStates.waiting_user_issue)
    await message.answer(
        "Опиши проблему одним сообщением.\n"
        "Можно отменить командой /cancel"
    )


@router.message(SupportStates.waiting_user_issue, Command("cancel"), F.chat.type == "private")
async def cancel_user_support_issue(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отправка обращения отменена.")


@router.message(SupportStates.waiting_user_issue, F.chat.type == "private")
async def process_user_support_issue(
    message: Message,
    session: AsyncSession,
    bot: Bot,
    state: FSMContext,
) -> None:
    if message.text is None:
        await message.answer("Нужно отправить текстовое сообщение.")
        return

    await submit_support_issue(message, message.text, session, bot, state)


@router.callback_query(SupportReplyCallback.filter())
async def process_support_reply_button(
    callback: CallbackQuery,
    callback_data: SupportReplyCallback,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    request, status = await claim_support_request(
        session=session,
        request_id=callback_data.request_id,
        admin_telegram_id=callback.from_user.id,
    )

    if request is None:
        await callback.message.answer("Обращение не найдено.")
        return

    if status == "closed":
        await callback.message.answer("Это обращение уже закрыто.")
        return

    if status == "claimed_by_other":
        await callback.message.answer("Это обращение уже взял другой администратор.")
        return

    await hide_support_buttons(bot, session, request.id)

    await state.set_state(SupportStates.waiting_admin_reply)
    await state.update_data(support_request_id=request.id)

    await callback.message.answer(
        f"Ты отвечаешь на обращение #{request.id}.\n"
        "Напиши ответ одним сообщением.\n"
        "Если передумал(а), используй /cancel — кнопка ответа вернется."
    )


@router.message(SupportStates.waiting_admin_reply, Command("cancel"), F.chat.type == "private")
async def cancel_admin_support_reply(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    if message.from_user is None:
        return

    data = await state.get_data()
    request_id = data.get("support_request_id")

    if request_id is not None:
        await reopen_support_request(
            session=session,
            request_id=request_id,
            admin_telegram_id=message.from_user.id,
        )
        await restore_support_buttons(bot, session, request_id)

    await state.clear()
    await message.answer("Ответ отменен. Обращение снова доступно администраторам.")


@router.message(SupportStates.waiting_admin_reply, F.chat.type == "private")
async def process_admin_support_reply(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    if message.from_user is None or message.text is None:
        await message.answer("Нужно отправить текстовый ответ.")
        return

    reply_text = message.text.strip()
    if not reply_text:
        await message.answer("Ответ не должен быть пустым.")
        return

    data = await state.get_data()
    request_id = data.get("support_request_id")
    if request_id is None:
        await state.clear()
        await message.answer("Не удалось определить обращение.")
        return

    request = await get_support_request(session, request_id)
    if request is None:
        await state.clear()
        await message.answer("Обращение не найдено.")
        return

    if request.status != "claimed" or request.claimed_by_admin_telegram_id != message.from_user.id:
        await state.clear()
        await message.answer("Это обращение уже недоступно для ответа.")
        return

    user = await get_user_by_id(session, request.user_id)
    if user is None:
        await state.clear()
        await message.answer("Не удалось найти участника.")
        return

    try:
        await bot.send_message(
            user.telegram_id,
            "📩 <b>Ответ администратора</b>\n\n"
            f"{escape(reply_text)}"
        )
    except (TelegramBadRequest, TelegramForbiddenError):
        await message.answer(
            "Не удалось отправить ответ участнику.\n"
            "Возможно, он закрыл диалог с ботом или ограничил сообщения."
        )
        return

    await close_support_request(
        session=session,
        request_id=request.id,
        admin_telegram_id=message.from_user.id,
        response_text=reply_text,
    )

    await state.clear()
    await message.answer(f"Ответ на обращение #{request.id} отправлен ✅")