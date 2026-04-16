from aiogram.filters.callback_data import CallbackData


class EventSelectCallback(CallbackData, prefix="event"):
    event_id: int


class AnswerChoiceCallback(CallbackData, prefix="answer"):
    question_code: str
    option_index: int


class VisibilityChoiceCallback(CallbackData, prefix="vis"):
    question_code: str
    visibility: str


class ProfileConfirmCallback(CallbackData, prefix="profile"):
    action: str


class ProfileEditCallback(CallbackData, prefix="profile_edit"):
    event_id: int


class ProfileDeleteCallback(CallbackData, prefix="profile_delete"):
    action: str


class ProfileEditFieldCallback(CallbackData, prefix="profile_edit_field"):
    event_id: int
    question_code: str


class ProfileEditActionCallback(CallbackData, prefix="profile_edit_action"):
    event_id: int
    action: str