from aiogram.filters.callback_data import CallbackData


class GameActionCallback(CallbackData, prefix="game_action"):
    game: str
    action: str