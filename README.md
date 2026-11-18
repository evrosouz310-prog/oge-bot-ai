# OGE Bot AI

Telegram-бот для подготовки к ОГЭ и ЕГЭ по информатике: теория, тесты с объяснениями,
ИИ-репетитор и статистика прогресса.

Бот: [@helper_for_shcool_bot](https://t.me/helper_for_shcool_bot)

## Возможности

- **Теория** — 6 тем: системы счисления, измерение информации, логика, алгоритмы и Python,
  файлы и адреса, электронные таблицы.
- **Тесты** — выбор темы, варианты A–D, объяснение после каждого ответа.
- **Работа над ошибками** — отдельный режим по вопросам, где последний ответ был неверным.
- **ИИ-репетитор** — отвечает на вопросы по информатике простыми словами.
- **`/ai_test`** — нейросеть сама придумывает вопрос и проверяет, что он в корректном формате.
- **Статистика** — решено вопросов, точность, разбивка по темам.
- **Защита расходов на ИИ** — дневной лимит на пользователя и кэш одинаковых вопросов.

## Структура проекта

```
main.py        — запуск (polling или webhook), graceful shutdown
config.py      — настройки из переменных окружения
handlers.py    — команды, кнопки, логика тестов и ИИ
ai_service.py  — запросы к нейросети, повторные попытки, валидация ответа
database.py    — SQLite или PostgreSQL, прогресс, лимиты и кэш ИИ
data.py        — теория и банк вопросов
keyboards.py   — клавиатуры и меню
```

## Локальный запуск

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# впишите BOT_TOKEN и AI_API_KEY
python main.py
```

По умолчанию используется SQLite (`data/bot.db`) и режим polling.

## Запуск на Render

1. Создайте Web Service из репозитория GitHub.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `python main.py`
4. В Environment задайте `BOT_TOKEN`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`,
   `AI_DAILY_LIMIT`, при необходимости `DATABASE_URL`.
5. Адрес webhook подставится автоматически из `RENDER_EXTERNAL_URL`,
   health-check доступен по `/health`.

Бесплатный Render стирает локальные файлы при перезапуске, поэтому для сохранения
прогресса подключите PostgreSQL (например, Neon) через `DATABASE_URL`.

## Проверка

```bash
python -m compileall .
python -m pytest
```

Мини-тесты лежат в `tests/test_core.py`.
