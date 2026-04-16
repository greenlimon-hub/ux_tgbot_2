import random
from collections import defaultdict

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.games.callbacks import GameActionCallback
from app.games.render import (
    render_games_menu,
    render_jeff_card,
    render_match_results,
    render_match_start,
    render_random_question,
    render_topics,
)
from app.services.games import (
    get_random_jeff_card,
    get_random_match_topic,
    get_random_question,
    get_random_topics,
)

router = Router(name="games")

ACTIVE_MATCH_GAMES: dict[int, dict] = {}
MATCH_REPLIES: dict[int, list[dict]] = defaultdict(list)


def build_game_action_keyboard(game: str, action: str, button_text: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text=button_text,
        callback_data=GameActionCallback(game=game, action=action),
    )
    builder.adjust(1)
    return builder.as_markup()


async def disable_old_keyboard(callback: CallbackQuery) -> None:
    if callback.message is None:
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


def collect_unique_match_answers(chat_id: int) -> list[str]:
    latest_by_user: dict[int, str] = {}

    for item in MATCH_REPLIES.get(chat_id, []):
        latest_by_user[item["user_id"]] = f'{item["name"]}: {item["text"]}'

    return list(latest_by_user.values())


async def send_next_question(target_message: Message) -> None:
    question = get_random_question()
    await target_message.answer(
        render_random_question(question),
        reply_markup=build_game_action_keyboard("question", "next", "Следующий вопрос"),
    )


async def send_next_topics(target_message: Message) -> None:
    topics = get_random_topics()
    await target_message.answer(
        render_topics(topics),
        reply_markup=build_game_action_keyboard("topics", "next", "Следующие темы"),
    )


async def send_next_match(target_message: Message) -> None:
    topic = get_random_match_topic()
    sent = await target_message.answer(
        render_match_start(topic),
        reply_markup=build_game_action_keyboard("match", "finish", "Завершить и показать ответы"),
    )

    ACTIVE_MATCH_GAMES[target_message.chat.id] = {
        "topic": topic,
        "message_id": sent.message_id,
    }
    MATCH_REPLIES[target_message.chat.id] = []


async def send_match_results_message(target_message: Message) -> None:
    game = ACTIVE_MATCH_GAMES.get(target_message.chat.id)
    if not game:
        await target_message.answer("Сейчас нет активной игры «Найди совпадение».")
        return

    answers = collect_unique_match_answers(target_message.chat.id)

    await target_message.answer(
        render_match_results(game["topic"], answers),
        reply_markup=build_game_action_keyboard("match", "next", "Следующая тема"),
    )

    ACTIVE_MATCH_GAMES.pop(target_message.chat.id, None)
    MATCH_REPLIES[target_message.chat.id] = []


async def send_next_jeff(target_message: Message) -> None:
    _, card = get_random_jeff_card()
    followup = random.choice(card["followups"])

    await target_message.answer(
        render_jeff_card(card["title"], followup),
        reply_markup=build_game_action_keyboard("jeff", "next", "Следующая дилемма"),
    )


@router.message(F.chat.type.in_({"private", "group", "supergroup"}), Command("games"))
async def cmd_games(message: Message) -> None:
    await message.answer(render_games_menu(message.chat.type))


@router.message(F.chat.type.in_({"private", "group", "supergroup"}), Command("question"))
async def cmd_question(message: Message) -> None:
    await send_next_question(message)


@router.message(F.chat.type.in_({"private", "group", "supergroup"}), Command("topics"))
async def cmd_topics(message: Message) -> None:
    await send_next_topics(message)


@router.message(F.chat.type.in_({"group", "supergroup"}), Command("match"))
async def cmd_match(message: Message) -> None:
    await send_next_match(message)


@router.message(F.chat.type.in_({"group", "supergroup"}), Command("match_results"))
async def cmd_match_results(message: Message) -> None:
    await send_match_results_message(message)


@router.message(F.chat.type.in_({"private", "group", "supergroup"}), Command("jeff"))
async def cmd_jeff(message: Message) -> None:
    await send_next_jeff(message)


@router.callback_query(GameActionCallback.filter())
async def process_game_action(callback: CallbackQuery, callback_data: GameActionCallback) -> None:
    await callback.answer()

    if callback.message is None:
        return

    await disable_old_keyboard(callback)

    if callback_data.game == "question" and callback_data.action == "next":
        await send_next_question(callback.message)
        return

    if callback_data.game == "topics" and callback_data.action == "next":
        await send_next_topics(callback.message)
        return

    if callback_data.game == "jeff" and callback_data.action == "next":
        await send_next_jeff(callback.message)
        return

    if callback_data.game == "match" and callback_data.action == "finish":
        if callback.message.chat.type not in {"group", "supergroup"}:
            await callback.message.answer("Эта игра доступна только в группе.")
            return

        await send_match_results_message(callback.message)
        return

    if callback_data.game == "match" and callback_data.action == "next":
        if callback.message.chat.type not in {"group", "supergroup"}:
            await callback.message.answer("Эта игра доступна только в группе.")
            return

        await send_next_match(callback.message)
        return


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def collect_match_replies(message: Message) -> None:
    game = ACTIVE_MATCH_GAMES.get(message.chat.id)
    if not game:
        return

    if not message.reply_to_message:
        return

    if message.reply_to_message.message_id != game["message_id"]:
        return

    if message.from_user is None or message.text is None:
        return

    if message.text.startswith("/"):
        return

    display_name = message.from_user.first_name
    if message.from_user.username:
        display_name = f"@{message.from_user.username}"

    MATCH_REPLIES[message.chat.id].append(
        {
            "user_id": message.from_user.id,
            "name": display_name,
            "text": message.text.strip(),
        }
    )