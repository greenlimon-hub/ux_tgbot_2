from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def private_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Список встреч"), KeyboardButton(text="Заполнить анкету")],
            [KeyboardButton(text="Моя анкета"), KeyboardButton(text="Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие",
    )