import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import load_settings
from database import Database
from handlers import router
from ai_service import AIService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def health(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def main():
    settings = load_settings()

    if settings.telegram_api_url:
        api_server = TelegramAPIServer.from_base(settings.telegram_api_url)
        session = AiohttpSession(api=api_server)
    else:
        session = AiohttpSession()

    bot = Bot(token=settings.bot_token, session=session)
    dp = Dispatcher()

    db = Database(sqlite_path=settings.sqlite_path, database_url=settings.database_url)
    ai_service = AIService(settings.ai_api_key, settings.ai_base_url, settings.ai_model)

    dp["db"] = db
    dp["ai_service"] = ai_service
    dp["settings"] = settings

    dp.include_router(router)

    runner: web.AppRunner | None = None
    try:
        await db.init()
        logger.info("Хранилище данных: %s", db.backend)

        if settings.use_webhook:
            app = web.Application()
            app.router.add_get("/health", health)
            webhook_requests_handler = SimpleRequestHandler(
                dispatcher=dp,
                bot=bot,
                secret_token=settings.webhook_secret,
            )
            webhook_requests_handler.register(app, path=settings.webhook_path)
            setup_application(app, dp, bot=bot)

            await bot.set_webhook(url=settings.webhook_url, secret_token=settings.webhook_secret)

            logger.info("Бот запущен в режиме Webhook на порту %s", settings.port)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", settings.port)
            await site.start()

            await asyncio.Event().wait()
        else:
            logger.info("Бот запущен в режиме Polling")
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
    finally:
        logger.info("Останавливаю бота…")
        if runner is not None:
            await runner.cleanup()
        await ai_service.close()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
