"""
ai_service.py — обращение к нейросети.

Используется OpenAI-совместимый формат (POST /chat/completions), поэтому один и тот же код
работает и с Groq, и с OpenRouter — меняются только переменные окружения
AI_BASE_URL, AI_MODEL и AI_API_KEY.

Надёжность: таймаут, повторные попытки при 429/5xx/сетевых сбоях и
понятные сообщения об ошибках для пользователя (класс AIError).
"""
from __future__ import annotations

import asyncio
import logging
import re

import aiohttp

log = logging.getLogger(__name__)

# Системная инструкция: задаёт «роль» нейросети и формат ответа.
SYSTEM_PROMPT = (
    "Ты — доброжелательный репетитор по информатике для школьников, "
    "которые готовятся к ОГЭ и ЕГЭ. Отвечай на русском языке, кратко и по шагам "
    "(не больше 1500 символов). Объясняй простыми словами, приводи небольшой пример. "
    "Если нужен код — пиши на Python. "
    "Не используй Markdown-разметку (звёздочки, решётки, обратные кавычки): "
    "пиши обычным текстом, а код оформляй отступами. "
    "Если вопрос не относится к информатике, вежливо скажи, что помогаешь только по информатике."
)


class AIError(Exception):
    """Ошибка работы с нейросетью. user_message можно безопасно показать пользователю."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class AIService:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 40.0,
        max_attempts: int = 3,
    ) -> None:
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        """Сессия создаётся лениво (уже внутри работающего event loop)."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self._timeout))
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def ask(self, question: str) -> str:
        """Отправить вопрос нейросети и вернуть текст ответа."""
        if not self._api_key:
            raise AIError("ИИ-помощник пока не настроен: не указан API-ключ.")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            "temperature": 0.3,
            "max_tokens": 800,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_error = "Нейросеть сейчас недоступна. Попробуй чуть позже."
        for attempt in range(1, self._max_attempts + 1):
            delay = 1.5 * attempt  # пауза перед следующей попыткой
            try:
                async with self._get_session().post(self._url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        return self._extract_text(data)

                    body = (await resp.text())[:300]
                    log.warning("ИИ вернул HTTP %s (попытка %s): %s", resp.status, attempt, body)

                    if resp.status in (401, 403):
                        raise AIError("API-ключ нейросети недействителен. Сообщи администратору бота.")
                    if resp.status == 404:
                        raise AIError("Модель нейросети не найдена. Сообщи администратору бота.")
                    if resp.status == 429 or resp.status >= 500:
                        last_error = "Нейросеть перегружена или превышен лимит запросов. Попробуй через минуту."
                        retry_after = resp.headers.get("Retry-After", "")
                        if retry_after.isdigit():
                            delay = min(float(retry_after), 8.0)
                    else:
                        raise AIError(
                            f"Нейросеть отклонила запрос (код {resp.status}). Попробуй переформулировать вопрос."
                        )
            except AIError:
                raise
            except asyncio.TimeoutError:
                last_error = "Нейросеть слишком долго отвечает. Попробуй ещё раз."
                log.warning("Таймаут запроса к ИИ (попытка %s)", attempt)
            except aiohttp.ClientError as exc:
                last_error = "Не удалось связаться с нейросетью. Попробуй позже."
                log.warning("Сетевая ошибка при обращении к ИИ (попытка %s): %s", attempt, exc)

            if attempt < self._max_attempts:
                await asyncio.sleep(delay)

        raise AIError(last_error)

    @staticmethod
    def _extract_text(data: dict) -> str:
        """Достать текст ответа из JSON и почистить его."""
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            log.error("Неожиданный формат ответа ИИ: %r", str(data)[:300])
            raise AIError("Нейросеть вернула ответ в неожиданном формате. Попробуй ещё раз.") from None

        # Некоторые модели добавляют «рассуждения» в тегах <think> — убираем их.
        text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
        if not text:
            raise AIError("Нейросеть вернула пустой ответ. Попробуй переформулировать вопрос.")
        return text
