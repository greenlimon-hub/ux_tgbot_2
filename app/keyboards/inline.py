from aiogram.utils.keyboard import InlineKeyboardBuilder

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
from app.support.callbacks import SupportReplyCallback
from app.questionnaire.definitions import QUESTIONNAIRE


def build_events_keyboard(events):
    builder = InlineKeyboardBuilder()

    for event in events:
        builder.button(
            text=event.title,
            callback_data=EventSelectCallback(event_id=event.id),
        )

    builder.adjust(1)
    return builder.as_markup()


def build_single_choice_keyboard(question):
    builder = InlineKeyboardBuilder()

    for index, option in enumerate(question.options):
        builder.button(
            text=option,
            callback_data=AnswerChoiceCallback(
                question_code=question.code,
                option_index=index,
            ),
        )

    if not question.required:
        builder.button(
            text="Пропустить",
            callback_data=AnswerChoiceCallback(
                question_code=question.code,
                option_index=-1,
            ),
        )

    builder.adjust(1)
    return builder.as_markup()


def build_yes_no_keyboard(question):
    builder = InlineKeyboardBuilder()
    options = ["Да", "Нет"]

    for index, option in enumerate(options):
        builder.button(
            text=option,
            callback_data=AnswerChoiceCallback(
                question_code=question.code,
                option_index=index,
            ),
        )

    if not question.required:
        builder.button(
            text="Пропустить",
            callback_data=AnswerChoiceCallback(
                question_code=question.code,
                option_index=-1,
            ),
        )

    builder.adjust(2)
    return builder.as_markup()


def build_privacy_keyboard(question_code: str):
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Показывать участникам",
        callback_data=VisibilityChoiceCallback(
            question_code=question_code,
            visibility="public",
        ),
    )
    builder.button(
        text="Только организаторам",
        callback_data=VisibilityChoiceCallback(
            question_code=question_code,
            visibility="organizers_only",
        ),
    )

    builder.adjust(1)
    return builder.as_markup()


def build_profile_confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Подтвердить анкету",
        callback_data=ProfileConfirmCallback(action="confirm"),
    )
    builder.button(
        text="Пройти настройку видимости заново",
        callback_data=ProfileConfirmCallback(action="restart_visibility"),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_profile_actions_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Изменить анкету",
        callback_data=ProfileEditCallback(event_id=event_id),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_delete_profile_confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Да, удалить профиль",
        callback_data=ProfileDeleteCallback(action="confirm"),
    )
    builder.button(
        text="Отмена",
        callback_data=ProfileDeleteCallback(action="cancel"),
    )
    builder.adjust(1)
    return builder.as_markup()


def build_profile_edit_fields_keyboard(event_id: int, draft_answers: dict | None = None):
    draft_answers = draft_answers or {}

    builder = InlineKeyboardBuilder()

    for question in QUESTIONNAIRE:
        prefix = "✏️ " if question.code in draft_answers else ""
        builder.button(
            text=f"{prefix}{question.label}",
            callback_data=ProfileEditFieldCallback(
                event_id=event_id,
                question_code=question.code,
            ),
        )

    builder.button(
        text="Проверить изменения",
        callback_data=ProfileEditActionCallback(
            event_id=event_id,
            action="review",
        ),
    )
    builder.button(
        text="Отмена без сохранения",
        callback_data=ProfileEditActionCallback(
            event_id=event_id,
            action="cancel",
        ),
    )

    builder.adjust(1)
    return builder.as_markup()


def build_profile_edit_review_keyboard(event_id: int):
    builder = InlineKeyboardBuilder()

    builder.button(
        text="Подтвердить изменения",
        callback_data=ProfileEditActionCallback(
            event_id=event_id,
            action="confirm",
        ),
    )
    builder.button(
        text="Продолжить редактирование",
        callback_data=ProfileEditActionCallback(
            event_id=event_id,
            action="back",
        ),
    )
    builder.button(
        text="Отмена без сохранения",
        callback_data=ProfileEditActionCallback(
            event_id=event_id,
            action="cancel",
        ),
    )

    builder.adjust(1)
    return builder.as_markup()

def build_support_reply_keyboard(request_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Ответить участнику",
        callback_data=SupportReplyCallback(request_id=request_id),
    )
    builder.adjust(1)
    return builder.as_markup()