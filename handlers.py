from aiogram import Router, types, F
from aiogram.filters import Command

from keyboards import (
    main_menu, ai_menu, theory_menu, question_kb, 
    after_answer_kb, restart_kb, theory_back,
    BTN_THEORY, BTN_TEST, BTN_AI, BTN_STATS, BTN_CANCEL
)
# Импортируем ПРАВИЛЬНЫЕ названия из твоего data.py
from data import THEORY, QUESTIONS 

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я твой помощник по подготовке к ОГЭ/ЕГЭ по информатике.\n"
        "Выбери действие на клавиатуре ниже:",
        reply_markup=main_menu()
    )

# --- ТЕОРИЯ ---
@router.message(F.text == BTN_THEORY)
async def show_theory_menu(message: types.Message):
    await message.answer(
        "📚 Выбери тему для изучения:",
        reply_markup=theory_menu(THEORY)
    )

@router.callback_query(F.data.startswith("theory:"))
async def show_theory_text(callback: types.CallbackQuery):
    topic_key = callback.data.split(":")[1]
    if topic_key == "menu":
        await callback.message.edit_text(
            "📚 Выбери тему для изучения:",
            reply_markup=theory_menu(THEORY)
        )
    else:
        topic = THEORY.get(topic_key)
        if topic:
            await callback.message.edit_text(
                topic.text, # Используем .text, как в твоем data.py
                parse_mode="HTML",
                reply_markup=theory_back()
            )
    await callback.answer()

# --- ТЕСТ ---
@router.message(F.text == BTN_TEST)
async def start_test(message: types.Message, db):
    await db.reset_progress(message.from_user.id)
    question = QUESTIONS[0]
    await message.answer(
        f"📝 Вопрос: {question.text}",
        reply_markup=question_kb(question)
    )

@router.callback_query(F.data.startswith("ans:"))
async def check_answer(callback: types.CallbackQuery, db):
    _, question_id, answer_index = callback.data.split(":")
    answer_index = int(answer_index)
    question_id = int(question_id)
    
    question = next((q for q in QUESTIONS if q.id == question_id), None)
    if not question:
        await callback.answer("Вопрос не найден")
        return

    is_correct = (answer_index == question.correct) # Используем .correct
    await db.save_answer(callback.from_user.id, question.id, is_correct)

    if is_correct:
        text = "✅ Правильно!"
    else:
        correct_letter = "ABCDEF"[question.correct]
        text = f"❌ Неверно. Правильный ответ: {correct_letter}"

    await callback.message.edit_text(
        f"{text}\n\n{question.explanation or ''}",
        reply_markup=after_answer_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "test:next")
async def next_question(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🏆 Тест завершен! Нажми кнопку ниже, чтобы пройти заново.",
        reply_markup=restart_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "test:reset")
async def reset_test(callback: types.CallbackQuery):
    question = QUESTIONS[0]
    await callback.message.edit_text(
        f"📝 Вопрос: {question.text}",
        reply_markup=question_kb(question)
    )
    await callback.answer()

# --- СТАТИСТИКА ---
@router.message(F.text == BTN_STATS)
async def show_stats(message: types.Message, db):
    stats = await db.get_stats(message.from_user.id)
    await message.answer(
        f"📊 <b>Твоя статистика:</b>\n"
        f"Правильных ответов: {stats.get('correct', 0)}\n"
        f"Всего ответов: {stats.get('total', 0)}",
        parse_mode="HTML"
    )

# --- ИИ ---
@router.message(F.text == BTN_AI)
async def start_ai(message: types.Message):
    await message.answer(
        "🤖 Я готов отвечать на твои вопросы по информатике!\n"
        "Напиши свой вопрос:",
        reply_markup=ai_menu()
    )

@router.message(F.text == BTN_CANCEL)
async def cancel_ai(message: types.Message):
    await message.answer(
        "Возвращаемся в главное меню.",
        reply_markup=main_menu()
    )

@router.message(F.text & ~F.text.startswith("/"))
async def handle_ai_text(message: types.Message, ai_service):
    if message.text in [BTN_THEORY, BTN_TEST, BTN_AI, BTN_STATS]:
        return
        
    await message.answer("⏳ Думаю над ответом...")
    answer = await ai_service.get_answer(message.text)
    await message.answer(answer)
