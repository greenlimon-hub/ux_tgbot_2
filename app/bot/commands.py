from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
)


async def set_commands(bot: Bot) -> None:
    private_commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="events", description="Список встреч"),
        BotCommand(command="questionnaire", description="Заполнить анкету"),
        BotCommand(command="profile", description="Моя анкета"),
        BotCommand(command="edit_profile", description="Изменить анкету"),
        BotCommand(command="delete_profile", description="Удалить профиль"),
        BotCommand(command="support", description="Написать администратору"),
        BotCommand(command="cancel", description="Отменить текущий шаг"),
        BotCommand(command="whoami", description="Показать мой Telegram ID"),
        BotCommand(command="create_demo_event", description="Создать тестовую встречу"),
        BotCommand(command="create_event", description="Создать встречу"),
        BotCommand(command="games", description="Показать мини-игры"),
        BotCommand(command="question", description="Случайный вопрос"),
        BotCommand(command="topics", description="3 темы для разговора"),
        BotCommand(command="jeff", description="Дилемма для обсуждения"),
    ]

    group_commands = [
        BotCommand(command="whoami", description="Показать мой Telegram ID"),
        BotCommand(command="bind_event", description="Привязать чат к встрече"),
        BotCommand(command="announce", description="Опубликовать сообщение от бота"),
        BotCommand(command="meeting", description="Шаблон анонса встречи"),
        BotCommand(command="where", description="Обновить место встречи"),
        BotCommand(command="when", description="Обновить время встречи"),
        BotCommand(command="important", description="Важное сообщение"),
        BotCommand(command="poll_custom", description="Создать кастомный опрос"),
        BotCommand(command="games", description="Показать мини-игры"),
        BotCommand(command="question", description="Случайный вопрос"),
        BotCommand(command="topics", description="3 темы для разговора"),
        BotCommand(command="match", description="Игра Найди совпадение"),
        BotCommand(command="match_results", description="Собрать ответы игры"),
        BotCommand(command="jeff", description="Дилемма для обсуждения"),
        BotCommand(command="show_profile", description="Показать анкету участника"),
    ]

    await bot.set_my_commands(
        private_commands,
        scope=BotCommandScopeAllPrivateChats(),
    )
    await bot.set_my_commands(
        group_commands,
        scope=BotCommandScopeAllGroupChats(),
    )