import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.commands import set_commands
from app.config import get_settings
from app.db.session import close_engine, init_models, session_maker
from app.handlers.admin import router as admin_router
from app.handlers.games import router as games_router
from app.handlers.group import router as group_router
from app.handlers.private import router as private_router
from app.handlers.questionnaire import router as questionnaire_router
from app.logger import setup_logging
from app.middlewares.db import DbSessionMiddleware
from app.handlers.support import router as support_router


async def main() -> None:
    setup_logging()
    settings = get_settings()

    logging.info("Initializing database...")
    await init_models()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.update.middleware(DbSessionMiddleware(session_maker))

    dp.include_router(admin_router)
    dp.include_router(support_router)
    dp.include_router(questionnaire_router)
    dp.include_router(group_router)
    dp.include_router(games_router)
    dp.include_router(private_router)

    await set_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)

    logging.info("Bot is starting...")
    try:
        await dp.start_polling(bot)
    finally:
        await close_engine()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
