"""
config.py — все настройки проекта.

Секреты (токен бота, ключ нейросети) НИКОГДА не хранятся в коде:
они читаются из переменных окружения. Локально их можно положить в файл .env,
на Render.com — в разделе Environment.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

# python-dotenv нужен только для локального запуска (чтение файла .env).
# На хостинге переменные задаются в панели, поэтому отсутствие библиотеки — не ошибка.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def _env(name: str, default: str = "") -> str:
    """Прочитать переменную окружения и убрать лишние пробелы по краям."""
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    """Неизменяемый набор настроек (frozen — чтобы случайно не изменить в коде)."""

    # --- Telegram ---
    bot_token: str
    # Адрес Cloudflare Worker, через который идут запросы к Telegram API.
    # Пусто = ходить напрямую на api.telegram.org (так можно на Render).
    telegram_api_url: str

    # --- Webhook ---
    webhook_base_url: str  # https://имя-сервиса.onrender.com ; пусто = режим polling
    webhook_path: str      # путь, на который Telegram присылает обновления
    webhook_secret: str    # секрет: Telegram добавляет его в заголовок каждого запроса
    port: int              # порт, который выдаёт хостинг (Render кладёт его в PORT)

    # --- Нейросеть (любой OpenAI-совместимый API: Groq, OpenRouter и т.д.) ---
    ai_api_key: str
    ai_base_url: str
    ai_model: str

    # --- База данных ---
    database_url: str  # если задан — PostgreSQL, иначе SQLite
    sqlite_path: str

    @property
    def use_webhook(self) -> bool:
        """Webhook включается, если известен публичный https-адрес сервиса."""
        return bool(self.webhook_base_url)

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_base_url}{self.webhook_path}"


def load_settings() -> Settings:
    """Собрать настройки и проверить, что обязательные значения заданы."""
    token = _env("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Не задана переменная окружения BOT_TOKEN. "
            "Получите токен у @BotFather и добавьте его в .env или в настройки Render."
        )

    # Render сам выставляет RENDER_EXTERNAL_URL (публичный адрес сервиса).
    base_url = _env("WEBHOOK_BASE_URL") or _env("RENDER_EXTERNAL_URL")
    if _env("FORCE_POLLING") == "1":  # для локальных тестов
        base_url = ""
    base_url = base_url.rstrip("/")
    if base_url and not base_url.startswith("https://"):
        raise RuntimeError("WEBHOOK_BASE_URL должен начинаться с https:// (требование Telegram).")

    # Секрет для проверки, что запрос к /webhook действительно пришёл от Telegram.
    # Если не задан вручную — выводим его из токена (стабильно между перезапусками).
    secret = _env("WEBHOOK_SECRET") or hashlib.sha256(token.encode()).hexdigest()[:64]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret):
        raise RuntimeError("WEBHOOK_SECRET может содержать только буквы, цифры, '_' и '-'.")

    try:
        port = int(_env("PORT", "8080"))
    except ValueError:
        raise RuntimeError("PORT должен быть числом.") from None

    return Settings(
        bot_token=token,
        telegram_api_url=_env("TELEGRAM_API_URL").rstrip("/"),
        webhook_base_url=base_url,
        webhook_path="/webhook",
        webhook_secret=secret,
        port=port,
        ai_api_key=_env("AI_API_KEY") or _env("GROQ_API_KEY"),
        ai_base_url=_env("AI_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/"),
        ai_model=_env("AI_MODEL", "llama-3.1-8b-instant"),
        database_url=_env("DATABASE_URL"),
        sqlite_path=_env("SQLITE_PATH", "data/bot.db"),
    )
