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

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Загружаем настройки из переменных окружения
    settings = load_settings()

    # Настраиваем сессию (через Cloudflare Worker, если указан)
    if settings.telegram_api_url:
        api_server = TelegramAPIServer.from_base(settings.telegram_api_url)
        session = AiohttpSession(api=api_server)
    else:
        session = AiohttpSession()

    # Инициализируем бота и диспетчер
    bot = Bot(token=settings.bot_token, session=session)
    dp = Dispatcher()

    # Инициализируем базу данных и AI сервис
    db = Database(sqlite_path=settings.sqlite_path, database_url=settings.database_url)
    await db.init()
    
    ai_service = AIService(settings.ai_api_key, settings.ai_base_url, settings.ai_model)

    # Передаем зависимости в хендлеры (через middleware или напрямую)
    dp["db"] = db
    dp["ai_service"] = ai_service

    # Подключаем роутер с командами (из файла handlers.py)
    dp.include_router(router)

    if settings.use_webhook:
        # Режим Webhook (для Render)
        app = web.Application()
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=settings.webhook_secret,
        )
        webhook_requests_handler.register(app, path=settings.webhook_path)
        setup_application(app, dp, bot=bot)

        # Устанавливаем вебхук в Telegram
        await bot.set_webhook(url=settings.webhook_url, secret_token=settings.webhook_secret)
        
        logger.info(f"Бот запущен в режиме Webhook на порту {settings.port}")
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", settings.port)
        await site.start()
        
        # Держим сервер запущенным
        await asyncio.Event().wait()
    else:
        # Режим Polling (для локального запуска)
        logger.info("Бот запущен в режиме Polling")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
