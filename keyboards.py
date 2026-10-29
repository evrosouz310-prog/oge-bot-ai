"""
keyboards.py — создание кнопок.

Два вида клавиатур в Telegram:
  • Reply-клавиатура — постоянные кнопки под полем ввода (главное меню);
  • Inline-клавиатура — кнопки под сообщением; при нажатии боту приходит callback_data.

Формат callback_data (до 64 байт):
  theory:<ключ темы> | theory:menu
  ans:<id вопроса>:<номер варианта>
  test:next | test:reset | stats
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data import Question, TheoryTopic

# Тексты кнопок главного меню (используются и в handlers.py для фильтров).
BTN_THEORY = "📚 Теория"
BTN_TEST = "📝 Пройти тест"
BTN_AI = "🤖 Спросить ИИ"
BTN_STATS = "📊 Моя статистика"
BTN_CANCEL = "↩️ В меню"

LETTERS = "ABCDEF"


def main_menu() -> ReplyKeyboardMarkup:
    """Главное меню: 4 кнопки в два ряда."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_THEORY), KeyboardButton(text=BTN_TEST)],
            [KeyboardButton(text=BTN_AI), KeyboardButton(text=BTN_STATS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие 👇",
    )


def ai_menu() -> ReplyKeyboardMarkup:
    """Клавиатура на время диалога с ИИ: одна кнопка выхода."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
        input_field_placeholder="Напиши вопрос по информатике…",
    )


def theory_menu(topics: dict[str, TheoryTopic]) -> InlineKeyboardMarkup:
    """Список тем теории (по одной кнопке в строке)."""
    builder = InlineKeyboardBuilder()
    for topic in topics.values():
        builder.button(text=topic.title, callback_data=f"theory:{topic.key}")
    builder.adjust(1)
    return builder.as_markup()


def theory_back() -> InlineKeyboardMarkup:
    """Кнопка возврата к списку тем."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К темам", callback_data="theory:menu")
    return builder.as_markup()


def question_kb(question: Question) -> InlineKeyboardMarkup:
    """Варианты ответа на вопрос теста."""
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(question.options):
        builder.button(text=f"{LETTERS[index]}) {option}", callback_data=f"ans:{question.id}:{index}")
    builder.adjust(1)
    return builder.as_markup()


def after_answer_kb() -> InlineKeyboardMarkup:
    """Кнопки после ответа на вопрос."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Следующий вопрос", callback_data="test:next")
    builder.button(text="📊 Статистика", callback_data="stats")
    builder.adjust(1)
    return builder.as_markup()


def restart_kb() -> InlineKeyboardMarkup:
    """Кнопка «начать заново» — когда решены все вопросы."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Пройти заново", callback_data="test:reset")
    return builder.as_markup()
