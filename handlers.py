import hashlib
import html
import logging
from datetime import datetime, timezone
from itertools import count

from aiogram import F, Router, types
from aiogram.filters import Command

from ai_service import AIError
from config import Settings
from data import QUESTIONS, QUESTIONS_BY_ID, THEORY, Question
from keyboards import (
    BTN_AI, BTN_CANCEL, BTN_STATS, BTN_TEST, BTN_THEORY,
    after_answer_kb, ai_menu, main_menu, question_kb, restart_kb,
    stats_kb, topics_menu, theory_back, theory_menu,
)

log = logging.getLogger(__name__)
router = Router()

TOPICS = list(dict.fromkeys(q.topic for q in QUESTIONS))

AI_QUESTION_ID_START = 10_000
AI_QUESTION_TTL = 60 * 60
AI_CACHE_TTL_HOURS = 24 * 7

_ai_ids = count(AI_QUESTION_ID_START)
_ai_questions: dict[tuple[int, int], tuple[Question, datetime]] = {}
_sessions: dict[int, dict] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> str:
    return _now().date().isoformat()


def _remember_ai_question(user_id: int, question: Question) -> None:
    _ai_questions[(user_id, question.id)] = (question, _now())
    for key, (_, created) in list(_ai_questions.items()):
        if (_now() - created).total_seconds() > AI_QUESTION_TTL:
            _ai_questions.pop(key, None)


def _find_question(user_id: int, question_id: int) -> Question | None:
    question = QUESTIONS_BY_ID.get(question_id)
    if question is not None:
        return question
    entry = _ai_questions.get((user_id, question_id))
    return entry[0] if entry else None


async def _collect_ids(db, user_id: int, mode: str, key: str) -> tuple[list[int], str]:
    if mode == "mistakes":
        wrong = await db.get_wrong_ids(user_id)
        return [q.id for q in QUESTIONS if q.id in wrong], "Р Р°Р±РѕС‚Р° РЅР°Рґ РѕС€РёР±РєР°РјРё"
    if mode == "topic":
        try:
            index = int(key)
        except (TypeError, ValueError):
            index = -1
        if not 0 <= index < len(TOPICS):
            return [], ""
        topic = TOPICS[index]
        return [q.id for q in QUESTIONS if q.topic == topic], topic
    solved = await db.get_solved_ids(user_id)
    remaining = [q.id for q in QUESTIONS if q.id not in solved]
    return (remaining or [q.id for q in QUESTIONS]), "Р’СЃРµ С‚РµРјС‹"


def _session_question(user_id: int) -> Question | None:
    session = _sessions.get(user_id)
    if not session:
        return None
    while session["pos"] < len(session["ids"]):
        question = QUESTIONS_BY_ID.get(session["ids"][session["pos"]])
        if question is not None:
            return question
        session["pos"] += 1
    return None


async def _show_current(callback: types.CallbackQuery, db) -> None:
    user_id = callback.from_user.id
    question = _session_question(user_id)
    if question is None:
        await _finish(callback, db)
        return
    await callback.message.edit_text(
        f"рџ“ќ Р’РѕРїСЂРѕСЃ: {question.text}",
        parse_mode="HTML",
        reply_markup=question_kb(question),
    )


async def _launch(callback: types.CallbackQuery, db, mode: str, key: str) -> None:
    user_id = callback.from_user.id
    ids, title = await _collect_ids(db, user_id, mode, key)
    if not ids:
        _sessions.pop(user_id, None)
        text = (
            "рџЋ‰ РћС€РёР±РѕРє РЅРµС‚ вЂ” РІСЃРµ РІРѕРїСЂРѕСЃС‹ СЂРµС€РµРЅС‹ РІРµСЂРЅРѕ!"
            if mode == "mistakes"
            else "Р’ СЌС‚РѕР№ С‚РµРјРµ РїРѕРєР° РЅРµС‚ РІРѕРїСЂРѕСЃРѕРІ."
        )
        await callback.message.edit_text(text, reply_markup=topics_menu(TOPICS))
        await callback.answer()
        return
    _sessions[user_id] = {"mode": mode, "key": key, "title": title, "ids": ids, "pos": 0}
    await _show_current(callback, db)
    await callback.answer()


async def _finish(callback: types.CallbackQuery, db) -> None:
    user_id = callback.from_user.id
    session = _sessions.get(user_id)
    title = session["title"] if session else "Р’СЃРµ С‚РµРјС‹"
    if session:
        session["pos"] = len(session["ids"])
    stats = await db.get_stats(user_id)
    await callback.message.edit_text(
        f"рџЏЃ РўСЂРµРЅРёСЂРѕРІРєР° Р·Р°РІРµСЂС€РµРЅР° вЂ” В«{title}В».\n\n"
        f"Р РµС€РµРЅРѕ СѓРЅРёРєР°Р»СЊРЅС‹С… РІРѕРїСЂРѕСЃРѕРІ: {stats['solved']} РёР· {len(QUESTIONS)}\n"
        f"РџСЂР°РІРёР»СЊРЅС‹С… РѕС‚РІРµС‚РѕРІ: {stats['correct']} РёР· {stats['attempts']}",
        parse_mode="HTML",
        reply_markup=restart_kb(),
    )


async def _stats_text(db, user_id: int) -> str:
    stats = await db.get_stats(user_id)
    progress = await db.get_progress(user_id)

    by_topic: dict[str, dict[str, int]] = {}
    for question_id, item in progress.items():
        question = QUESTIONS_BY_ID.get(question_id)
        if question is None:
            continue
        bucket = by_topic.setdefault(question.topic, {"attempts": 0, "correct": 0})
        bucket["attempts"] += item["attempts"]
        bucket["correct"] += item["correct"]

    lines = [
        "рџ“Љ <b>РўРІРѕСЏ СЃС‚Р°С‚РёСЃС‚РёРєР°:</b>",
        f"Р РµС€РµРЅРѕ СѓРЅРёРєР°Р»СЊРЅС‹С… РІРѕРїСЂРѕСЃРѕРІ: {stats['solved']} РёР· {len(QUESTIONS)}",
        f"РџСЂР°РІРёР»СЊРЅС‹С… РѕС‚РІРµС‚РѕРІ: {stats['correct']} РёР· {stats['attempts']}",
    ]
    if stats["attempts"]:
        percent = round(100 * stats["correct"] / stats["attempts"])
        lines.append(f"РўРѕС‡РЅРѕСЃС‚СЊ: {percent}%")
    lines.append(f"Р’РѕРїСЂРѕСЃРѕРІ Рє РЅРµР№СЂРѕСЃРµС‚Рё: {stats['ai_requests']}")

    if by_topic:
        lines.append("")
        lines.append("<b>РџРѕ С‚РµРјР°Рј:</b>")
        for topic, item in by_topic.items():
            lines.append(f"вЂў {topic}: {item['correct']} РёР· {item['attempts']}")

    return "\n".join(lines)


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "рџ¤– <b>РЎРїРёСЃРѕРє РґРѕСЃС‚СѓРїРЅС‹С… РєРѕРјР°РЅРґ:</b>\n\n"
        "рџ”№ /start вЂ” РџРµСЂРµР·Р°РїСѓСЃС‚РёС‚СЊ Р±РѕС‚Р° Рё РїРѕРєР°Р·Р°С‚СЊ РіР»Р°РІРЅРѕРµ РјРµРЅСЋ.\n"
        "рџ”№ /help вЂ” РџРѕРєР°Р·Р°С‚СЊ СЌС‚Рѕ СЃРѕРѕР±С‰РµРЅРёРµ СЃ РєРѕРјР°РЅРґР°РјРё.\n"
        "рџ”№ /ai_test вЂ” РџСЂРёРґСѓРјР°С‚СЊ РЅРѕРІС‹Р№ РІРѕРїСЂРѕСЃ СЃ РїРѕРјРѕС‰СЊСЋ РЅРµР№СЂРѕСЃРµС‚Рё.\n\n"
        "рџ’Ў <b>РљР°Рє РїРѕР»СЊР·РѕРІР°С‚СЊСЃСЏ:</b>\n"
        "вЂў РќР°Р¶РёРјР°Р№ РєРЅРѕРїРєРё РЅР° РєР»Р°РІРёР°С‚СѓСЂРµ РЅРёР¶Рµ, С‡С‚РѕР±С‹ РїРµСЂРµР№С‚Рё РІ С‚РµРѕСЂРёСЋ РёР»Рё С‚РµСЃС‚.\n"
        "вЂў Р’ С‚РµСЃС‚Рµ РјРѕР¶РЅРѕ РІС‹Р±СЂР°С‚СЊ С‚РµРјСѓ РёР»Рё РїСЂРѕР№С‚Рё В«Р Р°Р±РѕС‚Сѓ РЅР°Рґ РѕС€РёР±РєР°РјРёВ».\n"
        "вЂў Р’С‹Р±РµСЂРё В«РЎРїСЂРѕСЃРёС‚СЊ РРВ», С‡С‚РѕР±С‹ Р·Р°РґР°С‚СЊ Р»СЋР±РѕР№ РІРѕРїСЂРѕСЃ РїРѕ РёРЅС„РѕСЂРјР°С‚РёРєРµ.\n\n"
        "вљ пёЏ РЈ РІРѕРїСЂРѕСЃРѕРІ Рє РЅРµР№СЂРѕСЃРµС‚Рё РµСЃС‚СЊ РґРЅРµРІРЅРѕР№ Р»РёРјРёС‚."
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("start"))
async def cmd_start(message: types.Message, db):
    await db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(
        f"РџСЂРёРІРµС‚, {message.from_user.first_name}! рџ‘‹\n"
        "РЇ С‚РІРѕР№ РїРѕРјРѕС‰РЅРёРє РїРѕ РїРѕРґРіРѕС‚РѕРІРєРµ Рє РћР“Р­/Р•Р“Р­ РїРѕ РёРЅС„РѕСЂРјР°С‚РёРєРµ.\n"
        "Р’С‹Р±РµСЂРё РґРµР№СЃС‚РІРёРµ РЅР° РєР»Р°РІРёР°С‚СѓСЂРµ РЅРёР¶Рµ.\n\n"
        "рџ’Ў <i>РџРѕРґСЃРєР°Р·РєР°: РЅР°РїРёС€Рё /help, С‡С‚РѕР±С‹ СѓРІРёРґРµС‚СЊ РІСЃРµ РєРѕРјР°РЅРґС‹.</i>",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# --- РўР•РћР РРЇ ---
@router.message(F.text == BTN_THEORY)
async def show_theory_menu(message: types.Message):
    await message.answer(
        "рџ“љ Р’С‹Р±РµСЂРё С‚РµРјСѓ РґР»СЏ РёР·СѓС‡РµРЅРёСЏ:",
        reply_markup=theory_menu(THEORY)
    )


@router.callback_query(F.data.startswith("theory:"))
async def show_theory_text(callback: types.CallbackQuery):
    topic_key = callback.data.split(":")[1]
    if topic_key == "menu":
        await callback.message.edit_text(
            "рџ“љ Р’С‹Р±РµСЂРё С‚РµРјСѓ РґР»СЏ РёР·СѓС‡РµРЅРёСЏ:",
            reply_markup=theory_menu(THEORY)
        )
    else:
        topic = THEORY.get(topic_key)
        if topic:
            await callback.message.edit_text(
                topic.text,
                parse_mode="HTML",
                reply_markup=theory_back()
            )
    await callback.answer()


# --- РўР•РЎРў ---
@router.message(F.text == BTN_TEST)
async def start_test(message: types.Message):
    await message.answer(
        "рџ“ќ Р’С‹Р±РµСЂРё С‚РµРјСѓ РґР»СЏ С‚СЂРµРЅРёСЂРѕРІРєРё:",
        reply_markup=topics_menu(TOPICS)
    )


@router.callback_query(F.data == "test:menu")
async def show_test_topics(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "рџ“ќ Р’С‹Р±РµСЂРё С‚РµРјСѓ РґР»СЏ С‚СЂРµРЅРёСЂРѕРІРєРё:",
        reply_markup=topics_menu(TOPICS)
    )
    await callback.answer()


@router.callback_query(F.data == "test:start:all")
async def start_test_all(callback: types.CallbackQuery, db):
    await _launch(callback, db, "all", "")


@router.callback_query(F.data.startswith("test:start:"))
async def start_test_session(callback: types.CallbackQuery, db):
    await _launch(callback, db, "topic", callback.data.split(":", 2)[2])


@router.callback_query(F.data == "test:mistakes")
async def start_mistakes(callback: types.CallbackQuery, db):
    await _launch(callback, db, "mistakes", "")


@router.callback_query(F.data.startswith("ans:"))
async def check_answer(callback: types.CallbackQuery, db):
    try:
        _, raw_id, raw_index = callback.data.split(":")
        question_id = int(raw_id)
        answer_index = int(raw_index)
    except ValueError:
        await callback.answer("РќРµРєРѕСЂСЂРµРєС‚РЅР°СЏ РєРЅРѕРїРєР°", show_alert=True)
        return

    question = _find_question(callback.from_user.id, question_id)
    if question is None:
        await callback.answer("Р’РѕРїСЂРѕСЃ СѓСЃС‚Р°СЂРµР» вЂ” РЅР°С‡РЅРё С‚СЂРµРЅРёСЂРѕРІРєСѓ Р·Р°РЅРѕРІРѕ", show_alert=True)
        return
    if not 0 <= answer_index < len(question.options):
        await callback.answer()
        return

    is_correct = answer_index == question.correct
    if question_id < AI_QUESTION_ID_START:
        await db.record_answer(callback.from_user.id, question.id, is_correct)

    if is_correct:
        text = "вњ… РџСЂР°РІРёР»СЊРЅРѕ!"
    else:
        correct_letter = "ABCDEF"[question.correct]
        text = f"вќЊ РќРµРІРµСЂРЅРѕ. РџСЂР°РІРёР»СЊРЅС‹Р№ РѕС‚РІРµС‚: {correct_letter}"

    await callback.message.edit_text(
        f"{text}\n\n{question.explanation or ''}",
        parse_mode="HTML",
        reply_markup=after_answer_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "test:next")
async def next_question(callback: types.CallbackQuery, db):
    user_id = callback.from_user.id
    session = _sessions.get(user_id)
    if not session:
        ids, title = await _collect_ids(db, user_id, "all", "")
        session = {"mode": "all", "key": "", "title": title, "ids": ids, "pos": -1}
        _sessions[user_id] = session

    session["pos"] += 1
    await _show_current(callback, db)
    await callback.answer()


@router.callback_query(F.data == "test:reset")
async def reset_test(callback: types.CallbackQuery, db):
    user_id = callback.from_user.id
    session = _sessions.get(user_id)
    if not session:
        await callback.message.edit_text(
            "рџ“ќ Р’С‹Р±РµСЂРё С‚РµРјСѓ РґР»СЏ С‚СЂРµРЅРёСЂРѕРІРєРё:",
            reply_markup=topics_menu(TOPICS),
        )
        await callback.answer()
        return
    await _launch(callback, db, session["mode"], session["key"])


# --- РЎРўРђРўРРЎРўРРљРђ ---
@router.message(F.text == BTN_STATS)
async def show_stats(message: types.Message, db):
    await db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(await _stats_text(db, message.from_user.id), parse_mode="HTML")


@router.callback_query(F.data == "stats")
async def show_stats_callback(callback: types.CallbackQuery, db):
    await callback.message.edit_text(
        await _stats_text(db, callback.from_user.id),
        parse_mode="HTML",
        reply_markup=stats_kb(),
    )
    await callback.answer()


# --- РР ---
@router.message(F.text == BTN_AI)
async def start_ai(message: types.Message):
    await message.answer(
        "рџ¤– РЇ РіРѕС‚РѕРІ РѕС‚РІРµС‡Р°С‚СЊ РЅР° С‚РІРѕРё РІРѕРїСЂРѕСЃС‹ РїРѕ РёРЅС„РѕСЂРјР°С‚РёРєРµ!\n"
        "РќР°РїРёС€Рё СЃРІРѕР№ РІРѕРїСЂРѕСЃ:",
        reply_markup=ai_menu()
    )


@router.message(F.text == BTN_CANCEL)
async def cancel_ai(message: types.Message):
    await message.answer(
        "Р’РѕР·РІСЂР°С‰Р°РµРјСЃСЏ РІ РіР»Р°РІРЅРѕРµ РјРµРЅСЋ.",
        reply_markup=main_menu()
    )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_ai_text(message: types.Message, ai_service, db, settings: Settings):
    if message.text in [BTN_THEORY, BTN_TEST, BTN_AI, BTN_STATS, BTN_CANCEL]:
        return

    text = message.text.strip()
    if len(text) < 3:
        await message.answer("РќР°РїРёС€Рё РІРѕРїСЂРѕСЃ С‡СѓС‚СЊ РїРѕРґСЂРѕР±РЅРµРµ.")
        return
    if len(text) > 500:
        await message.answer("Р’РѕРїСЂРѕСЃ СЃР»РёС€РєРѕРј РґР»РёРЅРЅС‹Р№ вЂ” СЃРѕРєСЂР°С‚Рё РµРіРѕ РґРѕ 500 СЃРёРјРІРѕР»РѕРІ.")
        return

    user_id = message.from_user.id
    day = _today()
    used = await db.get_ai_used(user_id, day)

    cache_key = hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()
    cached = await db.get_cached_answer(cache_key, AI_CACHE_TTL_HOURS)
    if cached:
        await message.answer(cached)
        await db.increment_ai_requests(user_id)
        return

    if used >= settings.ai_daily_limit:
        await message.answer(
            f"вљ пёЏ РќР° СЃРµРіРѕРґРЅСЏ Р»РёРјРёС‚ РІРѕРїСЂРѕСЃРѕРІ Рє РЅРµР№СЂРѕСЃРµС‚Рё РёСЃС‡РµСЂРїР°РЅ ({settings.ai_daily_limit}).\n"
            "Р’РѕР·РІСЂР°С‰Р°Р№СЃСЏ Р·Р°РІС‚СЂР° вЂ” С‚РµРѕСЂРёСЏ Рё С‚РµСЃС‚С‹ СЂР°Р±РѕС‚Р°СЋС‚ Р±РµР· РѕРіСЂР°РЅРёС‡РµРЅРёР№."
        )
        return

    await message.answer("вЏі Р”СѓРјР°СЋ РЅР°Рґ РѕС‚РІРµС‚РѕРј...")
    try:
        answer = await ai_service.ask(text)
    except AIError as exc:
        await message.answer(f"вљ пёЏ {exc.user_message}")
        return
    except Exception:
        log.exception("РќРµРѕР¶РёРґР°РЅРЅР°СЏ РѕС€РёР±РєР° РїСЂРё Р·Р°РїСЂРѕСЃРµ Рє РЅРµР№СЂРѕСЃРµС‚Рё")
        await message.answer("вљ пёЏ Р§С‚Рѕ-С‚Рѕ РїРѕС€Р»Рѕ РЅРµ С‚Р°Рє. РџРѕРїСЂРѕР±СѓР№ РµС‰С‘ СЂР°Р· С‡СѓС‚СЊ РїРѕР·Р¶Рµ.")
        return

    await message.answer(answer)
    await db.increment_ai_requests(user_id)
    await db.increment_ai_used(user_id, day)
    await db.save_cached_answer(cache_key, answer)


@router.message(Command("ai_test"))
async def generate_ai_question(message: types.Message, ai_service, db, settings: Settings):
    user_id = message.from_user.id
    day = _today()
    used = await db.get_ai_used(user_id, day)
    if used >= settings.ai_daily_limit:
        await message.answer(
            f"вљ пёЏ РќР° СЃРµРіРѕРґРЅСЏ Р»РёРјРёС‚ РІРѕРїСЂРѕСЃРѕРІ Рє РЅРµР№СЂРѕСЃРµС‚Рё РёСЃС‡РµСЂРїР°РЅ ({settings.ai_daily_limit})."
        )
        return

    await message.answer("рџ§  РџСЂРёРґСѓРјС‹РІР°СЋ РЅРѕРІС‹Р№ РІРѕРїСЂРѕСЃ...")
    try:
        data = await ai_service.generate_question()
    except AIError as exc:
        await message.answer(f"вљ пёЏ {exc.user_message}")
        return
    except Exception:
        log.exception("РќРµРѕР¶РёРґР°РЅРЅР°СЏ РѕС€РёР±РєР° РїСЂРё РіРµРЅРµСЂР°С†РёРё РІРѕРїСЂРѕСЃР°")
        await message.answer("вљ пёЏ РќРµ РїРѕР»СѓС‡РёР»РѕСЃСЊ РїСЂРёРґСѓРјР°С‚СЊ РІРѕРїСЂРѕСЃ. РџРѕРїСЂРѕР±СѓР№ РµС‰С‘ СЂР°Р· С‡СѓС‚СЊ РїРѕР·Р¶Рµ.")
        return

    question = Question(
        id=next(_ai_ids),
        topic="РР-РІРѕРїСЂРѕСЃ",
        text=html.escape(data["question"]),
        options=tuple(data["options"]),
        correct=data["correct"],
        explanation=html.escape(data["explanation"]),
    )
    _remember_ai_question(user_id, question)

    await db.increment_ai_used(user_id, day)
    await message.answer(
        f"рџ“ќ Р’РѕРїСЂРѕСЃ РѕС‚ РР: {question.text}",
        parse_mode="HTML",
        reply_markup=question_kb(question),
    )
