from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data import Question, TheoryTopic

BTN_THEORY = "📚 Теория"
BTN_TEST = "📝 Пройти тест"
BTN_AI = "🤖 Спросить ИИ"
BTN_STATS = "📊 Моя статистика"
BTN_CANCEL = "↩️ В меню"

LETTERS = "ABCDEF"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_THEORY), KeyboardButton(text=BTN_TEST)],
            [KeyboardButton(text=BTN_AI), KeyboardButton(text=BTN_STATS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери действие 👇",
    )


def ai_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
        input_field_placeholder="Напиши вопрос по информатике…",
    )


def theory_menu(topics: dict[str, TheoryTopic]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for topic in topics.values():
        builder.button(text=topic.title, callback_data=f"theory:{topic.key}")
    builder.adjust(1)
    return builder.as_markup()


def theory_back() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К темам", callback_data="theory:menu")
    return builder.as_markup()


def topics_menu(topics: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Все темы", callback_data="test:start:all")
    for index, topic in enumerate(topics):
        builder.button(text=topic, callback_data=f"test:start:{index}")
    builder.adjust(1)
    return builder.as_markup()


def question_kb(question: Question) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(question.options):
        builder.button(text=f"{LETTERS[index]}) {option}", callback_data=f"ans:{question.id}:{index}")
    builder.adjust(1)
    return builder.as_markup()


def after_answer_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Следующий вопрос", callback_data="test:next")
    builder.button(text="📊 Статистика", callback_data="stats")
    builder.adjust(1)
    return builder.as_markup()


def restart_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Пройти заново", callback_data="test:reset")
    builder.button(text="📚 К темам", callback_data="test:menu")
    builder.adjust(1)
    return builder.as_markup()


def stats_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎯 Работа над ошибками", callback_data="test:mistakes")
    builder.button(text="📝 Пройти тест", callback_data="test:menu")
    builder.adjust(1)
    return builder.as_markup()
