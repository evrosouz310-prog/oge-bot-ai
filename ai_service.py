"""
ai_service.py — обращение к нейросети.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

import aiohttp

log = logging.getLogger(__name__)

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
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self._timeout))
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def ask(self, question: str) -> str:
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
            delay = 1.5 * attempt
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
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            log.error("Неожиданный формат ответа ИИ: %r", str(data)[:300])
            raise AIError("Нейросеть вернула ответ в неожиданном формате. Попробуй ещё раз.") from None

        text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
        if not text:
            raise AIError("Нейросеть вернула пустой ответ. Попробуй переформулировать вопрос.")
        return text

    # ==================== НОВЫЙ МЕТОД ДЛЯ ГЕНЕРАЦИИ ВОПРОСОВ ====================
    async def generate_question(self) -> dict:
        """Просит нейросеть сгенерировать новый вопрос для теста в формате JSON."""
        prompt = (
            "Придумай один сложный вопрос по информатике для подготовки к ОГЭ. "
            "Верни ответ СТРОГО в формате JSON без лишнего текста:\n"
            '{"question": "Текст вопроса", "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"], "correct": 0, "explanation": "Объяснение"}\n'
            "Где correct — это индекс правильного ответа (от 0 до 3)."
        )
        response_text = await self.ask(prompt)
        
        # Очищаем ответ от возможных маркеров Markdown, которые может добавить ИИ
        response_text = response_text.strip().strip("`").strip()
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()
            
        try:
            data = json.loads(response_text)
            return data
        except json.JSONDecodeError:
            raise AIError("ИИ не смог сгенерировать вопрос в правильном формате. Попробуй еще раз.")
