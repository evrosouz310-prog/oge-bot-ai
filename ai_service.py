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

    # ==================== ГЕНЕРАЦИЯ ВОПРОСОВ ====================
    async def generate_question(self) -> dict:
        """Просит нейросеть сгенерировать новый вопрос и проверяет его формат."""
        prompt = (
            "Придумай один вопрос по информатике для подготовки к ОГЭ. "
            "Верни ответ СТРОГО в формате JSON без лишнего текста и без Markdown:\n"
            '{"question": "Текст вопроса", "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"], '
            '"correct": 0, "explanation": "Объяснение"}\n'
            "Где correct — индекс правильного ответа (от 0 до 3). "
            "Вариантов должно быть от 2 до 6, все разные, без нумерации в тексте."
        )

        last_error: AIError | None = None
        for _ in range(2):
            response_text = await self.ask(prompt)
            try:
                return self._parse_question(response_text)
            except AIError as exc:
                last_error = exc
                log.warning("Не удалось разобрать вопрос от ИИ: %s", exc)

        raise last_error or AIError(
            "ИИ не смог сгенерировать вопрос в правильном формате. Попробуй ещё раз."
        )

    @staticmethod
    def _parse_question(text: str) -> dict:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()

        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise AIError("ИИ вернул вопрос не в формате JSON. Попробуй ещё раз.")

        try:
            data = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            raise AIError("ИИ вернул вопрос не в формате JSON. Попробуй ещё раз.") from None

        if not isinstance(data, dict):
            raise AIError("ИИ вернул вопрос не в формате JSON. Попробуй ещё раз.")

        question = str(data.get("question", "")).strip()
        options = data.get("options")
        correct = data.get("correct")
        explanation = str(data.get("explanation", "")).strip()

        if not question:
            raise AIError("ИИ придумал вопрос без текста. Попробуй ещё раз.")
        if not isinstance(options, list) or not 2 <= len(options) <= 6:
            raise AIError("ИИ вернул неверное число вариантов ответа. Попробуй ещё раз.")

        cleaned_options = [str(option).strip() for option in options]
        if any(not option for option in cleaned_options):
            raise AIError("ИИ вернул пустой вариант ответа. Попробуй ещё раз.")
        if len(set(cleaned_options)) != len(cleaned_options):
            raise AIError("ИИ вернул повторяющиеся варианты ответа. Попробуй ещё раз.")
        if isinstance(correct, bool) or not isinstance(correct, int):
            raise AIError("ИИ не указал правильный ответ. Попробуй ещё раз.")
        if not 0 <= correct < len(cleaned_options):
            raise AIError("ИИ указал правильный ответ вне диапазона. Попробуй ещё раз.")
        if not explanation:
            explanation = f"Правильный ответ: {cleaned_options[correct]}."

        return {
            "question": question,
            "options": cleaned_options,
            "correct": correct,
            "explanation": explanation,
        }
