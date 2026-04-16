from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.inline import (
    build_delete_profile_confirm_keyboard,
    build_events_keyboard,
    build_privacy_keyboard,
    build_profile_actions_keyboard,
    build_profile_confirm_keyboard,
    build_profile_edit_fields_keyboard,
    build_profile_edit_review_keyboard,
    build_single_choice_keyboard,
    build_yes_no_keyboard,
)
from app.keyboards.reply import private_main_menu
from app.questionnaire.callbacks import (
    AnswerChoiceCallback,
    EventSelectCallback,
    ProfileConfirmCallback,
    ProfileDeleteCallback,
    ProfileEditActionCallback,
    ProfileEditCallback,
    ProfileEditFieldCallback,
    VisibilityChoiceCallback,
)
from app.questionnaire.definitions import QUESTIONNAIRE, SKIP_TOKENS, get_question_by_code
from app.questionnaire.render import (
    answer_has_content,
    build_privacy_queue,
    format_question_text,
    format_visibility_label,
)
from app.questionnaire.states import QuestionnaireStates
from app.services.events import get_event_by_id, list_open_events
from app.services.questionnaire import (
    apply_draft_answers,
    build_and_save_profiles,
    build_profile_previews_from_draft,
    confirm_questionnaire,
    delete_all_user_profiles_and_participation,
    ensure_event_participant,
    get_answers_map,
    get_next_unanswered_question_index,
    list_profiles_for_user,
    list_user_event_chats,
    reset_questionnaire_for_event,
    set_answer_visibility,
    upsert_answer,
)
from app.services.users import get_user_by_telegram_id, upsert_telegram_user

router = Router(name="questionnaire")


async def get_or_create_local_user(session: AsyncSession, tg_user: TelegramUser):
    user = await get_user_by_telegram_id(session, tg_user.id)
    if user is None:
        user = await upsert_telegram_user(session, tg_user)
    return user

def get_question_index_by_code(question_code: str) -> int:
    for index, question in enumerate(QUESTIONNAIRE):
        if question.code == question_code:
            return index
    raise ValueError(f"Unknown question code: {question_code}")


def format_edit_question_text(question, current_text: str) -> str:
    lines = [
        f"<b>Редактирование поля: {escape(question.label)}</b>",
        "",
        escape(question.prompt),
        "",
        f"<b>Текущий ответ:</b> {escape(current_text)}",
    ]

    if question.kind == "number":
        lines.append("")
        lines.append("Отправь число сообщением.")

    if question.kind == "multi_select" and question.options:
        lines.append("")
        lines.append("Выбери один или несколько вариантов и отправь номера через запятую.")
        lines.append("Например: <code>1,3,5</code>")
        lines.append("")
        for idx, option in enumerate(question.options, start=1):
            lines.append(f"{idx}. {escape(option)}")

    if question.kind == "text":
        lines.append("")
        lines.append("Ответь обычным сообщением.")

    if question.kind == "textarea":
        lines.append("")
        lines.append("Можно ответить в свободной форме одним сообщением.")

    if question.kind in {"single_select", "yes_no"}:
        lines.append("")
        lines.append("Выбери вариант кнопкой ниже.")

    if not question.required:
        lines.append("")
        lines.append("Если хочешь очистить ответ, отправь <code>-</code>.")

    return "\n".join(lines)


async def stage_edit_answer(
    state: FSMContext,
    question_code: str,
    answer_text: str | None,
    answer_json: dict | list | None,
) -> None:
    data = await state.get_data()
    draft_answers = dict(data.get("edit_draft_answers", {}))
    draft_answers[question_code] = {
        "answer_text": answer_text,
        "answer_json": answer_json,
    }
    await state.update_data(edit_draft_answers=draft_answers)


async def show_edit_menu(
    reply_target: Message,
    state: FSMContext,
    session: AsyncSession,
    event_id: int,
    actor_tg_user: TelegramUser,
) -> None:
    user = await get_or_create_local_user(session, actor_tg_user)
    event = await get_event_by_id(session, event_id)
    if event is None:
        await reply_target.answer("Встреча не найдена.")
        return

    data = await state.get_data()
    draft_answers = data.get("edit_draft_answers", {})

    await state.set_state(QuestionnaireStates.edit_select_field)
    await state.update_data(edit_event_id=event_id)

    text = (
        f"<b>Редактирование анкеты для встречи {escape(event.title)}</b>\n\n"
        "Выбери поле, которое хочешь изменить.\n"
        "Изменения пока сохранены только как черновик и не затрагивают текущую анкету."
    )

    if draft_answers:
        text += f"\n\nЧерновик измененных полей: <b>{len(draft_answers)}</b>"

    await reply_target.answer(
        text,
        reply_markup=build_profile_edit_fields_keyboard(event_id, draft_answers),
    )


async def ask_edit_question(
    reply_target: Message,
    state: FSMContext,
    session: AsyncSession,
    event_id: int,
    user_id: int,
) -> None:
    data = await state.get_data()
    question_code = data["edit_selected_question_code"]
    draft_answers = data.get("edit_draft_answers", {})

    question = get_question_by_code(question_code)
    answers_map = await get_answers_map(session, event_id, user_id)

    if question_code in draft_answers:
        current_answer_text = draft_answers[question_code].get("answer_text") or "—"
    else:
        current_answer = answers_map.get(question_code)
        current_answer_text = current_answer.answer_text if current_answer and answer_has_content(current_answer) else "—"

    text = format_edit_question_text(question, current_answer_text)

    await state.set_state(QuestionnaireStates.edit_answering)

    if question.kind == "single_select":
        await reply_target.answer(text, reply_markup=build_single_choice_keyboard(question))
        return

    if question.kind == "yes_no":
        await reply_target.answer(text, reply_markup=build_yes_no_keyboard(question))
        return

    await reply_target.answer(text)


async def show_edit_review(
    reply_target: Message,
    state: FSMContext,
    session: AsyncSession,
    event_id: int,
    actor_tg_user: TelegramUser,
) -> None:
    user = await get_or_create_local_user(session, actor_tg_user)
    data = await state.get_data()
    draft_answers = data.get("edit_draft_answers", {})

    public_text, organizer_text = await build_profile_previews_from_draft(
        session=session,
        event_id=event_id,
        user=user,
        draft_answers=draft_answers,
    )

    await state.set_state(QuestionnaireStates.edit_review)

    text = (
        "<b>Проверь изменения перед сохранением</b>\n\n"
        "<b>Обновленная карточка для участников:</b>\n"
        f"{public_text or 'Пока пусто'}\n\n"
        "<b>Обновленная карточка для организаторов:</b>\n"
        f"{organizer_text or 'Пока пусто'}"
    )

    await reply_target.answer(
        text,
        reply_markup=build_profile_edit_review_keyboard(event_id),
    )


async def start_edit_profile_flow(
    reply_target: Message,
    state: FSMContext,
    session: AsyncSession,
    event_id: int,
    actor_tg_user: TelegramUser,
) -> None:
    await state.clear()
    await state.update_data(
        edit_event_id=event_id,
        edit_draft_answers={},
    )
    await show_edit_menu(
        reply_target=reply_target,
        state=state,
        session=session,
        event_id=event_id,
        actor_tg_user=actor_tg_user,
    )


async def start_questionnaire_entry(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    await upsert_telegram_user(session, message.from_user)
    events = await list_open_events(session)

    if not events:
        await message.answer("Сейчас нет открытых встреч для заполнения анкеты.")
        return

    if len(events) == 1:
        await begin_questionnaire_for_event(
            reply_target=message,
            actor_tg_user=message.from_user,
            state=state,
            session=session,
            event_id=events[0].id,
        )
        return

    await state.set_state(QuestionnaireStates.choosing_event)
    await message.answer(
        "Выбери встречу, для которой хочешь заполнить анкету:",
        reply_markup=build_events_keyboard(events),
    )


async def begin_questionnaire_for_event(
    reply_target: Message,
    actor_tg_user: TelegramUser,
    state: FSMContext,
    session: AsyncSession,
    event_id: int,
) -> None:
    user = await get_or_create_local_user(session, actor_tg_user)
    event = await get_event_by_id(session, event_id)

    if event is None or event.status != "open":
        await reply_target.answer("Эта встреча недоступна.")
        return

    await ensure_event_participant(session, event.id, user.id)

    next_index = await get_next_unanswered_question_index(session, event.id, user.id)

    if next_index is None:
        await start_privacy_flow(reply_target, state, session, event.id, user.id, actor_tg_user)
        return

    await state.set_state(QuestionnaireStates.answering)
    await state.update_data(event_id=event.id, question_index=next_index)

    await reply_target.answer(
        f"Начинаем анкету для встречи <b>{escape(event.title)}</b>.\n"
        f"Можно отменить текущий шаг командой /cancel.",
        reply_markup=private_main_menu(),
    )
    await ask_current_question(reply_target, state)


async def ask_current_question(reply_target: Message, state: FSMContext) -> None:
    data = await state.get_data()
    question_index = data["question_index"]

    question = QUESTIONNAIRE[question_index]
    text = format_question_text(question, question_index, len(QUESTIONNAIRE))

    if question.kind == "single_select":
        await reply_target.answer(text, reply_markup=build_single_choice_keyboard(question))
        return

    if question.kind == "yes_no":
        await reply_target.answer(text, reply_markup=build_yes_no_keyboard(question))
        return

    await reply_target.answer(text)


def parse_text_answer(question, raw_text: str) -> tuple[str | None, dict | list | None, str | None]:
    text = raw_text.strip()

    if not text:
        return None, None, "Ответ не должен быть пустым."

    if text.casefold() in SKIP_TOKENS:
        if question.required:
            return None, None, "Этот вопрос обязательный, его нельзя пропустить."
        return None, {"skipped": True}, None

    if question.kind == "number":
        try:
            value = int(text)
        except ValueError:
            return None, None, "Нужно отправить число."

        if question.min_value is not None and value < question.min_value:
            return None, None, f"Число должно быть не меньше {question.min_value}."

        if question.max_value is not None and value > question.max_value:
            return None, None, f"Число должно быть не больше {question.max_value}."

        return str(value), {"value": value}, None

    if question.kind in {"text", "textarea"}:
        if question.max_length is not None and len(text) > question.max_length:
            return None, None, f"Слишком длинный ответ. Максимум: {question.max_length} символов."
        return text, {"value": text}, None

    if question.kind == "multi_select":
        pieces = [part.strip() for part in text.replace(" ", "").split(",") if part.strip()]
        if not pieces:
            return None, None, "Нужно прислать номера вариантов через запятую. Например: 1,3,5"

        selected_indexes: list[int] = []
        for piece in pieces:
            if not piece.isdigit():
                return None, None, "Каждый вариант должен быть числом. Например: 1,3,5"
            index = int(piece)
            if index < 1 or index > len(question.options):
                return None, None, f"Номер {index} выходит за пределы списка."
            selected_indexes.append(index)

        selected_indexes = sorted(set(selected_indexes))
        selected_values = [question.options[index - 1] for index in selected_indexes]

        if "Другое" in selected_values:
            selected_values = [value for value in selected_values if value != "Другое"]
            return ", ".join(selected_values) if selected_values else None, {
                "selected_values": selected_values,
                "needs_other_text": True,
            }, None

        return ", ".join(selected_values), {"selected_values": selected_values}, None

    return None, None, "Этот тип вопроса ожидает другой формат ответа."


async def save_and_move_next(
    reply_target: Message,
    actor_tg_user: TelegramUser,
    state: FSMContext,
    session: AsyncSession,
    answer_text: str | None,
    answer_json: dict | list | None,
) -> None:
    user = await get_or_create_local_user(session, actor_tg_user)

    data = await state.get_data()
    event_id = data["event_id"]
    question_index = data["question_index"]
    question = QUESTIONNAIRE[question_index]

    await upsert_answer(
        session=session,
        event_id=event_id,
        user_id=user.id,
        question_code=question.code,
        answer_text=answer_text,
        answer_json=answer_json,
        visibility=question.default_visibility,
    )

    next_index = question_index + 1
    if next_index >= len(QUESTIONNAIRE):
        await start_privacy_flow(reply_target, state, session, event_id, user.id, actor_tg_user)
        return

    await state.set_state(QuestionnaireStates.answering)
    await state.update_data(question_index=next_index)
    await ask_current_question(reply_target, state)


async def start_privacy_flow(
    reply_target: Message,
    state: FSMContext,
    session: AsyncSession,
    event_id: int,
    user_id: int,
    actor_tg_user: TelegramUser,
) -> None:
    answers_map = await get_answers_map(session, event_id, user_id)
    privacy_codes = build_privacy_queue(answers_map)

    if not privacy_codes:
        await build_and_show_confirmation(reply_target, state, session, event_id, actor_tg_user)
        return

    await state.set_state(QuestionnaireStates.privacy)
    await state.update_data(
        event_id=event_id,
        privacy_codes=privacy_codes,
        privacy_index=0,
    )

    await reply_target.answer(
        "Теперь выбери, какие из некоторых ответов можно показывать другим участникам.\n"
        "Остальные поля увидят только организаторы."
    )
    await ask_current_privacy_question(reply_target, state, session, event_id, user_id)


async def ask_current_privacy_question(
    reply_target: Message,
    state: FSMContext,
    session: AsyncSession,
    event_id: int,
    user_id: int,
) -> None:
    data = await state.get_data()
    privacy_codes = data["privacy_codes"]
    privacy_index = data["privacy_index"]
    question_code = privacy_codes[privacy_index]

    answers_map = await get_answers_map(session, event_id, user_id)
    answer = answers_map.get(question_code)

    question = next(q for q in QUESTIONNAIRE if q.code == question_code)

    current_visibility = answer.visibility if answer else question.default_visibility
    current_text = answer.answer_text if answer and answer_has_content(answer) else "—"

    text = (
        f"<b>Настройка видимости {privacy_index + 1}/{len(privacy_codes)}</b>\n\n"
        f"<b>Поле:</b> {escape(question.label)}\n"
        f"<b>Ответ:</b> {escape(current_text)}\n"
        f"<b>Сейчас:</b> {escape(format_visibility_label(current_visibility))}\n\n"
        f"Показывать это другим участникам?"
    )

    await reply_target.answer(
        text,
        reply_markup=build_privacy_keyboard(question_code),
    )


async def build_and_show_confirmation(
    reply_target: Message,
    state: FSMContext,
    session: AsyncSession,
    event_id: int,
    actor_tg_user: TelegramUser,
) -> None:
    user = await get_or_create_local_user(session, actor_tg_user)
    profile = await build_and_save_profiles(session, event_id, user)

    await state.set_state(QuestionnaireStates.confirming)
    await state.update_data(event_id=event_id)

    text = (
        "<b>Проверь анкету перед подтверждением</b>\n\n"
        "<b>Карточка для участников:</b>\n"
        f"{profile.public_profile_text or 'Пока пусто'}\n\n"
        "<b>Карточка для организаторов:</b>\n"
        f"{profile.organizer_profile_text or 'Пока пусто'}"
    )

    await reply_target.answer(
        text,
        reply_markup=build_profile_confirm_keyboard(),
    )


@router.message(Command("questionnaire"), F.chat.type == "private")
@router.message(F.text == "Заполнить анкету", F.chat.type == "private")
async def cmd_questionnaire(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await start_questionnaire_entry(message, session, state)


@router.message(Command("cancel"), F.chat.type == "private")
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Сейчас нет активного шага, который нужно отменять.")
        return

    await state.clear()

    if "edit_" in current_state:
        await message.answer(
            "Редактирование отменено.\n"
            "Несохраненные изменения отброшены, старая анкета осталась без изменений.",
            reply_markup=private_main_menu(),
        )
        return

    await message.answer(
        "Текущий шаг отменен.\n"
        "Ты можешь снова запустить анкету командой /questionnaire.",
        reply_markup=private_main_menu(),
    )


@router.callback_query(
    QuestionnaireStates.choosing_event,
    EventSelectCallback.filter(),
)
async def callback_select_event(
    callback: CallbackQuery,
    callback_data: EventSelectCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    await begin_questionnaire_for_event(
        reply_target=callback.message,
        actor_tg_user=callback.from_user,
        state=state,
        session=session,
        event_id=callback_data.event_id,
    )


@router.message(QuestionnaireStates.answering, F.chat.type == "private")
async def process_text_question(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    data = await state.get_data()
    question_index = data["question_index"]
    question = QUESTIONNAIRE[question_index]

    if question.kind in {"single_select", "yes_no"}:
        await message.answer("Для этого вопроса нужно нажать кнопку под сообщением.")
        return

    if message.text is None:
        await message.answer("Нужен текстовый ответ.")
        return

    answer_text, answer_json, error = parse_text_answer(question, message.text)

    if error:
        await message.answer(error)
        await ask_current_question(message, state)
        return

    if question.kind == "multi_select" and isinstance(answer_json, dict) and answer_json.get("needs_other_text"):
        await state.set_state(QuestionnaireStates.answering_other)
        await state.update_data(
            other_question_code=question.code,
            other_base_values=answer_json.get("selected_values", []),
        )
        await message.answer("Напиши свой вариант для ответа «Другое».")
        return

    await save_and_move_next(
        reply_target=message,
        actor_tg_user=message.from_user,
        state=state,
        session=session,
        answer_text=answer_text,
        answer_json=answer_json,
    )


@router.callback_query(
    QuestionnaireStates.answering,
    AnswerChoiceCallback.filter(),
)
async def process_choice_question(
    callback: CallbackQuery,
    callback_data: AnswerChoiceCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    data = await state.get_data()
    question_index = data["question_index"]
    question = QUESTIONNAIRE[question_index]

    if question.code != callback_data.question_code:
        await callback.message.answer("Эта кнопка относится к старому вопросу. Используй актуальное сообщение ниже.")
        return

    if callback_data.option_index == -1:
        if question.required:
            await callback.message.answer("Этот вопрос обязательный, его нельзя пропустить.")
            return

        await save_and_move_next(
            reply_target=callback.message,
            actor_tg_user=callback.from_user,
            state=state,
            session=session,
            answer_text=None,
            answer_json={"skipped": True},
        )
        return

    if question.kind == "yes_no":
        options = ["Да", "Нет"]
        if callback_data.option_index < 0 or callback_data.option_index >= len(options):
            await callback.message.answer("Некорректный вариант ответа.")
            return

        selected = options[callback_data.option_index]
        await save_and_move_next(
            reply_target=callback.message,
            actor_tg_user=callback.from_user,
            state=state,
            session=session,
            answer_text=selected,
            answer_json={"value": selected == "Да"},
        )
        return

    if question.kind == "single_select":
        if callback_data.option_index < 0 or callback_data.option_index >= len(question.options):
            await callback.message.answer("Некорректный вариант ответа.")
            return

        selected = question.options[callback_data.option_index]

        if selected == "Другое":
            await state.set_state(QuestionnaireStates.answering_other)
            await state.update_data(
                other_question_code=question.code,
                other_base_values=[],
            )
            await callback.message.answer("Напиши свой вариант для ответа «Другое».")
            return

        await save_and_move_next(
            reply_target=callback.message,
            actor_tg_user=callback.from_user,
            state=state,
            session=session,
            answer_text=selected,
            answer_json={"value": selected},
        )
        return

    await callback.message.answer("Для этого вопроса нужен текстовый ответ.")


@router.message(QuestionnaireStates.answering_other, F.chat.type == "private")
async def process_other_text(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if message.from_user is None or message.text is None:
        await message.answer("Нужно отправить текстовый вариант.")
        return

    custom_text = message.text.strip()
    if not custom_text:
        await message.answer("Ответ не должен быть пустым.")
        return

    if len(custom_text) > 150:
        await message.answer("Слишком длинный ответ. Максимум: 150 символов.")
        return

    data = await state.get_data()
    base_values = data.get("other_base_values", [])

    if base_values:
        full_values = [*base_values, f"Другое: {custom_text}"]
        answer_text = ", ".join(full_values)
        answer_json = {
            "selected_values": full_values,
            "custom_other_text": custom_text,
        }
    else:
        answer_text = custom_text
        answer_json = {
            "value": custom_text,
            "custom_other_text": custom_text,
        }

    await state.set_state(QuestionnaireStates.answering)
    await save_and_move_next(
        reply_target=message,
        actor_tg_user=message.from_user,
        state=state,
        session=session,
        answer_text=answer_text,
        answer_json=answer_json,
    )


@router.callback_query(
    QuestionnaireStates.privacy,
    VisibilityChoiceCallback.filter(),
)
async def process_visibility_choice(
    callback: CallbackQuery,
    callback_data: VisibilityChoiceCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    user = await get_or_create_local_user(session, callback.from_user)

    data = await state.get_data()
    event_id = data["event_id"]
    privacy_codes = data["privacy_codes"]
    privacy_index = data["privacy_index"]

    current_code = privacy_codes[privacy_index]
    if current_code != callback_data.question_code:
        await callback.message.answer("Эта кнопка относится к старому шагу. Используй актуальное сообщение ниже.")
        return

    await set_answer_visibility(
        session=session,
        event_id=event_id,
        user_id=user.id,
        question_code=current_code,
        visibility=callback_data.visibility,
    )

    next_index = privacy_index + 1
    if next_index >= len(privacy_codes):
        await build_and_show_confirmation(
            reply_target=callback.message,
            state=state,
            session=session,
            event_id=event_id,
            actor_tg_user=callback.from_user,
        )
        return

    await state.update_data(privacy_index=next_index)
    await ask_current_privacy_question(callback.message, state, session, event_id, user.id)


@router.callback_query(
    QuestionnaireStates.confirming,
    ProfileConfirmCallback.filter(),
)
async def process_profile_confirm(
    callback: CallbackQuery,
    callback_data: ProfileConfirmCallback,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    user = await get_or_create_local_user(session, callback.from_user)

    data = await state.get_data()
    event_id = data["event_id"]

    if callback_data.action == "restart_visibility":
        answers_map = await get_answers_map(session, event_id, user.id)
        privacy_codes = build_privacy_queue(answers_map)

        await state.set_state(QuestionnaireStates.privacy)
        await state.update_data(
            event_id=event_id,
            privacy_codes=privacy_codes,
            privacy_index=0,
        )

        await callback.message.answer("Хорошо, пройдем настройку видимости заново.")
        await ask_current_privacy_question(callback.message, state, session, event_id, user.id)
        return

    if callback_data.action == "confirm":
        await confirm_questionnaire(session, event_id, user.id)
        await state.clear()

        event = await get_event_by_id(session, event_id)

        base_text = "Анкета сохранена и подтверждена ✅"

        if event is None:
            await callback.message.answer(
                base_text + "\n\nНо я не смог найти встречу в базе."
            )
            return

        if not event.chat_id:
            await callback.message.answer(
                base_text
                + "\n\nЧат для этой встречи пока не привязан."
                + "\nПопроси организатора добавить бота в чат и выполнить /bind_event."
            )
            return

        try:
            invite = await bot.create_chat_invite_link(
                chat_id=event.chat_id,
                name=f"{event.slug}-{user.telegram_id}",
                member_limit=1,
            )

            await callback.message.answer(
                base_text
                + f"\n\nВот ссылка на чат встречи <b>{escape(event.title)}</b>:\n"
                + f"{invite.invite_link}"
            )
        except TelegramForbiddenError:
            await callback.message.answer(
                base_text
                + "\n\nЯ не смог создать ссылку на чат."
                + "\nСкорее всего, меня не сделали администратором чата."
            )
        except TelegramBadRequest as exc:
            await callback.message.answer(
                base_text
                + "\n\nЯ не смог создать ссылку на чат."
                + "\nПроверь, что бот добавлен в нужную группу, назначен администратором"
                + " и у него есть право приглашать пользователей."
                + f"\n\nТехническая причина: <code>{escape(str(exc))}</code>"
            )
        return


@router.callback_query(ProfileEditCallback.filter())
async def process_profile_edit(
    callback: CallbackQuery,
    callback_data: ProfileEditCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    event = await get_event_by_id(session, callback_data.event_id)
    if event is None:
        await callback.message.answer("Встреча не найдена.")
        return

    await callback.message.answer(
        f"Начинаем редактирование анкеты для встречи <b>{escape(event.title)}</b>."
    )

    await start_edit_profile_flow(
        reply_target=callback.message,
        state=state,
        session=session,
        event_id=event.id,
        actor_tg_user=callback.from_user,
    )

@router.callback_query(ProfileEditFieldCallback.filter())
async def process_profile_edit_field(
    callback: CallbackQuery,
    callback_data: ProfileEditFieldCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    user = await get_or_create_local_user(session, callback.from_user)

    await state.update_data(
        edit_event_id=callback_data.event_id,
        edit_selected_question_code=callback_data.question_code,
    )

    await ask_edit_question(
        reply_target=callback.message,
        state=state,
        session=session,
        event_id=callback_data.event_id,
        user_id=user.id,
    )


@router.message(QuestionnaireStates.edit_answering, F.chat.type == "private")
async def process_edit_text_question(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    data = await state.get_data()
    question_code = data["edit_selected_question_code"]
    event_id = data["edit_event_id"]
    question = get_question_by_code(question_code)

    if question.kind in {"single_select", "yes_no"}:
        await message.answer("Для этого вопроса нужно нажать кнопку под сообщением.")
        return

    if message.text is None:
        await message.answer("Нужен текстовый ответ.")
        return

    answer_text, answer_json, error = parse_text_answer(question, message.text)

    if error:
        await message.answer(error)
        await ask_edit_question(
            reply_target=message,
            state=state,
            session=session,
            event_id=event_id,
            user_id=(await get_or_create_local_user(session, message.from_user)).id,
        )
        return

    if question.kind == "multi_select" and isinstance(answer_json, dict) and answer_json.get("needs_other_text"):
        await state.set_state(QuestionnaireStates.edit_answering_other)
        await state.update_data(
            other_question_code=question.code,
            other_base_values=answer_json.get("selected_values", []),
        )
        await message.answer("Напиши свой вариант для ответа «Другое».")
        return

    await stage_edit_answer(
        state=state,
        question_code=question.code,
        answer_text=answer_text,
        answer_json=answer_json,
    )

    await message.answer("Изменение добавлено в черновик. Старая анкета пока не изменена.")

    await show_edit_menu(
        reply_target=message,
        state=state,
        session=session,
        event_id=event_id,
        actor_tg_user=message.from_user,
    )


@router.callback_query(
    QuestionnaireStates.edit_answering,
    AnswerChoiceCallback.filter(),
)
async def process_edit_choice_question(
    callback: CallbackQuery,
    callback_data: AnswerChoiceCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    data = await state.get_data()
    question_code = data["edit_selected_question_code"]
    event_id = data["edit_event_id"]
    question = get_question_by_code(question_code)

    if question.code != callback_data.question_code:
        await callback.message.answer("Эта кнопка относится к старому шагу. Используй актуальное сообщение ниже.")
        return

    if callback_data.option_index == -1:
        if question.required:
            await callback.message.answer("Этот вопрос обязательный, его нельзя очистить.")
            return

        await stage_edit_answer(
            state=state,
            question_code=question.code,
            answer_text=None,
            answer_json={"skipped": True},
        )

        await callback.message.answer("Изменение добавлено в черновик. Старая анкета пока не изменена.")

        await show_edit_menu(
            reply_target=callback.message,
            state=state,
            session=session,
            event_id=event_id,
            actor_tg_user=callback.from_user,
        )
        return

    if question.kind == "yes_no":
        options = ["Да", "Нет"]
        if callback_data.option_index < 0 or callback_data.option_index >= len(options):
            await callback.message.answer("Некорректный вариант ответа.")
            return

        selected = options[callback_data.option_index]

        await stage_edit_answer(
            state=state,
            question_code=question.code,
            answer_text=selected,
            answer_json={"value": selected == "Да"},
        )

        await callback.message.answer("Изменение добавлено в черновик. Старая анкета пока не изменена.")

        await show_edit_menu(
            reply_target=callback.message,
            state=state,
            session=session,
            event_id=event_id,
            actor_tg_user=callback.from_user,
        )
        return

    if question.kind == "single_select":
        if callback_data.option_index < 0 or callback_data.option_index >= len(question.options):
            await callback.message.answer("Некорректный вариант ответа.")
            return

        selected = question.options[callback_data.option_index]

        if selected == "Другое":
            await state.set_state(QuestionnaireStates.edit_answering_other)
            await state.update_data(
                other_question_code=question.code,
                other_base_values=[],
            )
            await callback.message.answer("Напиши свой вариант для ответа «Другое».")
            return

        await stage_edit_answer(
            state=state,
            question_code=question.code,
            answer_text=selected,
            answer_json={"value": selected},
        )

        await callback.message.answer("Изменение добавлено в черновик. Старая анкета пока не изменена.")

        await show_edit_menu(
            reply_target=callback.message,
            state=state,
            session=session,
            event_id=event_id,
            actor_tg_user=callback.from_user,
        )
        return

    await callback.message.answer("Для этого вопроса нужен текстовый ответ.")


@router.message(QuestionnaireStates.edit_answering_other, F.chat.type == "private")
async def process_edit_other_text(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if message.from_user is None or message.text is None:
        await message.answer("Нужно отправить текстовый вариант.")
        return

    custom_text = message.text.strip()
    if not custom_text:
        await message.answer("Ответ не должен быть пустым.")
        return

    if len(custom_text) > 150:
        await message.answer("Слишком длинный ответ. Максимум: 150 символов.")
        return

    data = await state.get_data()
    event_id = data["edit_event_id"]
    question_code = data["other_question_code"]
    base_values = data.get("other_base_values", [])

    if base_values:
        full_values = [*base_values, f"Другое: {custom_text}"]
        answer_text = ", ".join(full_values)
        answer_json = {
            "selected_values": full_values,
            "custom_other_text": custom_text,
        }
    else:
        answer_text = custom_text
        answer_json = {
            "value": custom_text,
            "custom_other_text": custom_text,
        }

    await stage_edit_answer(
        state=state,
        question_code=question_code,
        answer_text=answer_text,
        answer_json=answer_json,
    )

    await message.answer("Изменение добавлено в черновик. Старая анкета пока не изменена.")

    await show_edit_menu(
        reply_target=message,
        state=state,
        session=session,
        event_id=event_id,
        actor_tg_user=message.from_user,
    )


@router.callback_query(ProfileEditActionCallback.filter())
async def process_profile_edit_action(
    callback: CallbackQuery,
    callback_data: ProfileEditActionCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    user = await get_or_create_local_user(session, callback.from_user)
    data = await state.get_data()
    event_id = data.get("edit_event_id", callback_data.event_id)
    draft_answers = data.get("edit_draft_answers", {})

    if callback_data.action == "cancel":
        await state.clear()
        await callback.message.answer(
            "Редактирование отменено.\n"
            "Несохраненные изменения отброшены, старая анкета осталась без изменений."
        )
        return

    if callback_data.action == "back":
        await show_edit_menu(
            reply_target=callback.message,
            state=state,
            session=session,
            event_id=event_id,
            actor_tg_user=callback.from_user,
        )
        return

    if callback_data.action == "review":
        if not draft_answers:
            await callback.message.answer("Ты пока не изменил(а) ни одного поля.")
            await show_edit_menu(
                reply_target=callback.message,
                state=state,
                session=session,
                event_id=event_id,
                actor_tg_user=callback.from_user,
            )
            return

        await show_edit_review(
            reply_target=callback.message,
            state=state,
            session=session,
            event_id=event_id,
            actor_tg_user=callback.from_user,
        )
        return

    if callback_data.action == "confirm":
        if not draft_answers:
            await callback.message.answer("Нет изменений для сохранения.")
            await show_edit_menu(
                reply_target=callback.message,
                state=state,
                session=session,
                event_id=event_id,
                actor_tg_user=callback.from_user,
            )
            return

        await apply_draft_answers(
            session=session,
            event_id=event_id,
            user_id=user.id,
            draft_answers=draft_answers,
        )
        await build_and_save_profiles(session, event_id, user)
        await state.clear()

        await callback.message.answer(
            "Изменения сохранены ✅\n"
            "Анкета обновлена только сейчас, после подтверждения."
        )

@router.message(Command("edit_profile"), F.chat.type == "private")
async def cmd_edit_profile(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    await upsert_telegram_user(session, message.from_user)
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if user is None:
        await message.answer("Пока анкеты нет. Используй /questionnaire")
        return

    profiles = await list_profiles_for_user(session, user.id)

    if not profiles:
        await message.answer("Пока анкеты нет. Используй /questionnaire")
        return

    if len(profiles) == 1:
        _, event = profiles[0]

        await message.answer(
            f"Начинаем редактирование анкеты для встречи <b>{escape(event.title)}</b>."
        )

        await start_edit_profile_flow(
            reply_target=message,
            state=state,
            session=session,
            event_id=event.id,
            actor_tg_user=message.from_user,
        )
        return

    await message.answer("У тебя несколько анкет. Выбери, какую редактировать:")

    for profile, event in profiles:
        await message.answer(
            f"<b>{escape(event.title)}</b>\n\n"
            f"{profile.public_profile_text or 'Пока не собрана'}",
            reply_markup=build_profile_actions_keyboard(event.id),
        )

@router.message(Command("delete_profile"), F.chat.type == "private")
async def cmd_delete_profile(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if message.from_user is None:
        return

    await upsert_telegram_user(session, message.from_user)
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if user is None:
        await message.answer("Пока удалять нечего: анкеты еще нет.")
        return

    profiles = await list_profiles_for_user(session, user.id)
    if not profiles:
        await message.answer("Пока удалять нечего: анкеты еще нет.")
        return

    await state.clear()

    await message.answer(
        "Ты точно хочешь удалить свой профиль?\n\n"
        "После подтверждения:\n"
        "• анкеты для всех встреч будут удалены\n"
        "• ты будешь удален(а) из всех чатов встреч, к которым бот привязан\n\n"
        "Это действие нельзя отменить.",
        reply_markup=build_delete_profile_confirm_keyboard(),
    )

@router.callback_query(ProfileDeleteCallback.filter())
async def process_profile_delete(
    callback: CallbackQuery,
    callback_data: ProfileDeleteCallback,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    if callback_data.action == "cancel":
        await callback.message.answer("Удаление профиля отменено.")
        return

    user = await get_or_create_local_user(session, callback.from_user)
    await state.clear()

    events = await list_user_event_chats(session, user.id)

    removed_from_chats = 0
    failed_chats = 0

    for event in events:
        if not event.chat_id:
            continue

        try:
            await bot.ban_chat_member(
                chat_id=event.chat_id,
                user_id=user.telegram_id,
                revoke_messages=False,
            )
            await bot.unban_chat_member(
                chat_id=event.chat_id,
                user_id=user.telegram_id,
                only_if_banned=True,
            )
            removed_from_chats += 1
        except (TelegramBadRequest, TelegramForbiddenError):
            failed_chats += 1

    await delete_all_user_profiles_and_participation(session, user.id)

    text = (
        "Профиль удален ✅\n\n"
        "Что сделано:\n"
        f"• удалено анкет: для всех твоих встреч\n"
        f"• обработано чатов встреч: {len([e for e in events if e.chat_id])}\n"
        f"• успешно удален(а) из чатов: {removed_from_chats}"
    )

    if failed_chats:
        text += (
            f"\n• не удалось удалить из чатов: {failed_chats}"
            "\n\nСкорее всего, у бота нет прав администратора в части чатов."
        )

    await callback.message.answer(text)

@router.message(Command("profile"), F.chat.type == "private")
@router.message(F.text == "Моя анкета", F.chat.type == "private")
async def cmd_profile(message: Message, session: AsyncSession) -> None:
    if message.from_user is None:
        return

    await upsert_telegram_user(session, message.from_user)
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if user is None:
        await message.answer("Пока анкеты нет. Используй /questionnaire")
        return

    profiles = await list_profiles_for_user(session, user.id)

    if not profiles:
        await message.answer("Пока анкеты нет. Используй /questionnaire")
        return

    for profile, event in profiles:
        await message.answer(
            f"<b>{escape(event.title)}</b>\n\n"
            f"<b>Публичная карточка:</b>\n"
            f"{profile.public_profile_text or 'Пока не собрана'}\n\n"
            f"<b>Карточка для организаторов:</b>\n"
            f"{profile.organizer_profile_text or 'Пока не собрана'}",
            reply_markup=build_profile_actions_keyboard(event.id),
        )