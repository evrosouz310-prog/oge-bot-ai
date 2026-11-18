"""
keyboards.py вЂ” СЃРѕР·РґР°РЅРёРµ РєРЅРѕРїРѕРє.

Р”РІР° РІРёРґР° РєР»Р°РІРёР°С‚СѓСЂ РІ Telegram:
  вЂў Reply-РєР»Р°РІРёР°С‚СѓСЂР° вЂ” РїРѕСЃС‚РѕСЏРЅРЅС‹Рµ РєРЅРѕРїРєРё РїРѕРґ РїРѕР»РµРј РІРІРѕРґР° (РіР»Р°РІРЅРѕРµ РјРµРЅСЋ);
  вЂў Inline-РєР»Р°РІРёР°С‚СѓСЂР° вЂ” РєРЅРѕРїРєРё РїРѕРґ СЃРѕРѕР±С‰РµРЅРёРµРј; РїСЂРё РЅР°Р¶Р°С‚РёРё Р±РѕС‚Сѓ РїСЂРёС…РѕРґРёС‚ callback_data.

Р¤РѕСЂРјР°С‚ callback_data (РґРѕ 64 Р±Р°Р№С‚):
  theory:<РєР»СЋС‡ С‚РµРјС‹> | theory:menu
  ans:<id РІРѕРїСЂРѕСЃР°>:<РЅРѕРјРµСЂ РІР°СЂРёР°РЅС‚Р°>
  test:menu | test:start:all | test:start:<РЅРѕРјРµСЂ С‚РµРјС‹>
  test:next | test:reset | test:mistakes | stats
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data import Question, TheoryTopic

# РўРµРєСЃС‚С‹ РєРЅРѕРїРѕРє РіР»Р°РІРЅРѕРіРѕ РјРµРЅСЋ (РёСЃРїРѕР»СЊР·СѓСЋС‚СЃСЏ Рё РІ handlers.py РґР»СЏ С„РёР»СЊС‚СЂРѕРІ).
BTN_THEORY = "рџ“љ РўРµРѕСЂРёСЏ"
BTN_TEST = "рџ“ќ РџСЂРѕР№С‚Рё С‚РµСЃС‚"
BTN_AI = "рџ¤– РЎРїСЂРѕСЃРёС‚СЊ РР"
BTN_STATS = "рџ“Љ РњРѕСЏ СЃС‚Р°С‚РёСЃС‚РёРєР°"
BTN_CANCEL = "в†©пёЏ Р’ РјРµРЅСЋ"

LETTERS = "ABCDEF"


def main_menu() -> ReplyKeyboardMarkup:
    """Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ: 4 РєРЅРѕРїРєРё РІ РґРІР° СЂСЏРґР°."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_THEORY), KeyboardButton(text=BTN_TEST)],
            [KeyboardButton(text=BTN_AI), KeyboardButton(text=BTN_STATS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Р’С‹Р±РµСЂРё РґРµР№СЃС‚РІРёРµ рџ‘‡",
    )


def ai_menu() -> ReplyKeyboardMarkup:
    """РљР»Р°РІРёР°С‚СѓСЂР° РЅР° РІСЂРµРјСЏ РґРёР°Р»РѕРіР° СЃ РР: РѕРґРЅР° РєРЅРѕРїРєР° РІС‹С…РѕРґР°."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
        input_field_placeholder="РќР°РїРёС€Рё РІРѕРїСЂРѕСЃ РїРѕ РёРЅС„РѕСЂРјР°С‚РёРєРµвЂ¦",
    )


def theory_menu(topics: dict[str, TheoryTopic]) -> InlineKeyboardMarkup:
    """РЎРїРёСЃРѕРє С‚РµРј С‚РµРѕСЂРёРё (РїРѕ РѕРґРЅРѕР№ РєРЅРѕРїРєРµ РІ СЃС‚СЂРѕРєРµ)."""
    builder = InlineKeyboardBuilder()
    for topic in topics.values():
        builder.button(text=topic.title, callback_data=f"theory:{topic.key}")
    builder.adjust(1)
    return builder.as_markup()


def theory_back() -> InlineKeyboardMarkup:
    """РљРЅРѕРїРєР° РІРѕР·РІСЂР°С‚Р° Рє СЃРїРёСЃРєСѓ С‚РµРј."""
    builder = InlineKeyboardBuilder()
    builder.button(text="в¬…пёЏ Рљ С‚РµРјР°Рј", callback_data="theory:menu")
    return builder.as_markup()


def topics_menu(topics: list[str]) -> InlineKeyboardMarkup:
    """Р’С‹Р±РѕСЂ С‚РµРјС‹ РїРµСЂРµРґ РЅР°С‡Р°Р»РѕРј С‚СЂРµРЅРёСЂРѕРІРєРё."""
    builder = InlineKeyboardBuilder()
    builder.button(text="рџ“љ Р’СЃРµ С‚РµРјС‹", callback_data="test:start:all")
    for index, topic in enumerate(topics):
        builder.button(text=topic, callback_data=f"test:start:{index}")
    builder.adjust(1)
    return builder.as_markup()


def question_kb(question: Question) -> InlineKeyboardMarkup:
    """Р’Р°СЂРёР°РЅС‚С‹ РѕС‚РІРµС‚Р° РЅР° РІРѕРїСЂРѕСЃ С‚РµСЃС‚Р°."""
    builder = InlineKeyboardBuilder()
    for index, option in enumerate(question.options):
        builder.button(text=f"{LETTERS[index]}) {option}", callback_data=f"ans:{question.id}:{index}")
    builder.adjust(1)
    return builder.as_markup()


def after_answer_kb() -> InlineKeyboardMarkup:
    """РљРЅРѕРїРєРё РїРѕСЃР»Рµ РѕС‚РІРµС‚Р° РЅР° РІРѕРїСЂРѕСЃ."""
    builder = InlineKeyboardBuilder()
    builder.button(text="вћЎпёЏ РЎР»РµРґСѓСЋС‰РёР№ РІРѕРїСЂРѕСЃ", callback_data="test:next")
    builder.button(text="рџ“Љ РЎС‚Р°С‚РёСЃС‚РёРєР°", callback_data="stats")
    builder.adjust(1)
    return builder.as_markup()


def restart_kb() -> InlineKeyboardMarkup:
    """РљРЅРѕРїРєРё РїРѕСЃР»Рµ Р·Р°РІРµСЂС€РµРЅРёСЏ С‚СЂРµРЅРёСЂРѕРІРєРё."""
    builder = InlineKeyboardBuilder()
    builder.button(text="рџ”„ РџСЂРѕР№С‚Рё Р·Р°РЅРѕРІРѕ", callback_data="test:reset")
    builder.button(text="рџ“љ Рљ С‚РµРјР°Рј", callback_data="test:menu")
    builder.adjust(1)
    return builder.as_markup()


def stats_kb() -> InlineKeyboardMarkup:
    """РљРЅРѕРїРєРё РїРѕРґ СЌРєСЂР°РЅРѕРј СЃС‚Р°С‚РёСЃС‚РёРєРё."""
    builder = InlineKeyboardBuilder()
    builder.button(text="рџЋЇ Р Р°Р±РѕС‚Р° РЅР°Рґ РѕС€РёР±РєР°РјРё", callback_data="test:mistakes")
    builder.button(text="рџ“ќ РџСЂРѕР№С‚Рё С‚РµСЃС‚", callback_data="test:menu")
    builder.adjust(1)
    return builder.as_markup()
