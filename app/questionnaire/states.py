from aiogram.fsm.state import State, StatesGroup


class QuestionnaireStates(StatesGroup):
    choosing_event = State()
    answering = State()
    answering_other = State()
    privacy = State()
    confirming = State()

    edit_select_field = State()
    edit_answering = State()
    edit_answering_other = State()
    edit_review = State()