from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.reply import private_main_menu
from app.services.events import list_open_events
from app.services.users import upsert_telegram_user

router = Router(name="private")


def render_events_text(events: list) -> str:
    if not events:
        return "Сейчас открытых встреч нет."

    lines = []
    for event in events:
        title = escape(event.title)
        city = escape(event.city) if event.city else "Не указан"
        start_at = escape(event.start_at) if event.start_at else "Скоро"

        lines.append(
            f"• <b>{title}</b>\n"
            f"  Город: {city}\n"
            f"  Когда: {start_at}\n"
            f"  slug: <code>{escape(event.slug)}</code>"
        )

    return "\n\n".join(lines)


@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return

    await upsert_telegram_user(session, message.from_user)
    events = await list_open_events(session)

    text = (
    "Привет! 👋\n\n"
    "Этот бот помогает знакомиться и участвовать в офлайн-встречах.\n\n"
    "<b>Вот что нужно сделать, чтобы попасть на встречу:</b>\n\n"
    "1️⃣ Заполни анкету — команда /questionnaire\n"
    "Бот задаст несколько вопросов о тебе, твоих интересах и ожиданиях. Это займёт всего пару минут.\n\n"
    "2️⃣ Подтверди анкету\n"
    "После заполнения бот покажет твою анкету — просто нажми «Подтвердить».\n"
    "(Важно: без подтверждения ты не сможешь попасть в чат встречи)\n\n"
    "3️⃣ Получи ссылку на чат\n"
    "Как только анкета будет подтверждена, бот сразу пришлёт тебе одноразовую ссылку на закрытый чат встречи.\n\n"
    "4️⃣ Заходи в чат и знакомься\n"
    "После того как ты вступишь в чат, бот автоматически покажет твою публичную карточку остальным участникам.\n\n"
    "\n\n"
    "<b>Что ещё можно делать в боте:</b>\n\n"
    "📋 /profile — посмотреть свою анкету\n"
    "✏️ /edit_profile — отредактировать анкету\n"
    "🗑️ /delete_profile — удалить анкету (если передумал участвовать)\n"
    "🎲 /games — вопросы и игры для знакомства\n"
    "📢 /events — посмотреть список встреч\n"
    "🆘 /support — написать организаторам\n\n"
    "Если захочешь выйти из чата встречи — просто удали свою анкету через /delete_profile.\n\n"
    "Приятного общения! ✨"
)

    if events:
        text += "\n\n<b>Открытые встречи:</b>\n" + render_events_text(events)
    else:
        text += "\n\nПока открытых встреч нет."

    await message.answer(text, reply_markup=private_main_menu())


@router.message(Command("help"), F.chat.type == "private")
@router.message(F.text == "Помощь", F.chat.type == "private")
async def cmd_help(message: Message) -> None:
    text = (
        "<b>Что уже умеет бот:</b>\n"
        "• регистрирует пользователя в базе\n"
        "• показывает открытые встречи\n"
        "• запускает анкету\n"
        "• сохраняет ответы в базу\n"
        "• собирает публичную и организаторскую карточки\n"
        "• показывает вопросы и мини-игры в ЛС\n\n"
        "<b>Команды:</b>\n"
        "/start\n"
        "/events\n"
        "/questionnaire\n"
        "/profile\n"
        "/edit_profile\n"
        "/delete_profile\n"
        "/support\n"
        "/games\n"
        "/question\n"
        "/topics\n"
        "/jeff\n"
        "/cancel\n"
        "/whoami"
    )
    await message.answer(text, reply_markup=private_main_menu())


@router.message(Command("events"), F.chat.type == "private")
@router.message(F.text == "Список встреч", F.chat.type == "private")
async def cmd_events(message: Message, session: AsyncSession) -> None:
    events = await list_open_events(session)
    text = "<b>Список открытых встреч:</b>\n\n" + render_events_text(events)
    await message.answer(text, reply_markup=private_main_menu())


@router.message(F.chat.type == "private")
async def fallback_private(message: Message) -> None:
    await message.answer(
        "Пока я не понял это сообщение.\n"
        "Используй /help или кнопки ниже.",
        reply_markup=private_main_menu(),
    )
