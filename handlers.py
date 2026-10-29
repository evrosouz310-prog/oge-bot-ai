from aiogram import Router, types, F
from aiogram.filters import Command

from keyboards import (
    main_menu, ai_menu, theory_menu, question_kb, 
    after_answer_kb, restart_kb, theory_back,
    BTN_THEORY, BTN_TEST, BTN_AI, BTN_STATS, BTN_CANCEL
)
from data import THEORY, QUESTIONS, Question
from ai_service import AIError

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, db):
    await db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
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
                topic.text,
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
        parse_mode="HTML", # <--- Добавлено, чтобы не было тегов <code>
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

    is_correct = (answer_index == question.correct)
    await db.record_answer(callback.from_user.id, question.id, is_correct)

    if is_correct:
        text = "✅ Правильно!"
    else:
        correct_letter = "ABCDEF"[question.correct]
        text = f"❌ Неверно. Правильный ответ: {correct_letter}"

    await callback.message.edit_text(
        f"{text}\n\n{question.explanation or ''}",
        parse_mode="HTML", # <--- Добавлено для красивого объяснения
        reply_markup=after_answer_kb()
    )
    await callback.answer()

@router.callback_query(F.data == "test:next")
async def next_question(callback: types.CallbackQuery):
    # Временное решение: берем случайный вопрос из списка
    import random
    next_q = random.choice(QUESTIONS) 
    
    await callback.message.edit_text(
        f"📝 Вопрос: {next_q.text}",
        parse_mode="HTML",
        reply_markup=question_kb(next_q)
    )
    await callback.answer()

@router.callback_query(F.data == "test:reset")
async def reset_test(callback: types.CallbackQuery):
    question = QUESTIONS[0]
    await callback.message.edit_text(
        f"📝 Вопрос: {question.text}",
        parse_mode="HTML", # <--- Добавлено
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
        f"Всего ответов: {stats.get('attempts', 0)}",
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
async def handle_ai_text(message: types.Message, ai_service, db):
    if message.text in [BTN_THEORY, BTN_TEST, BTN_AI, BTN_STATS]:
        return
        
    await message.answer("⏳ Думаю над ответом...")
    try:
        answer = await ai_service.ask(message.text)
        await message.answer(answer)
        await db.increment_ai_requests(message.from_user.id)
    except AIError as e:
        await message.answer(f"⚠️ {e.user_message}")
    except Exception as e:
        await message.answer(f"Произошла непредвиденная ошибка: {e}")

# --- ГЕНЕРАЦИЯ ВОПРОСА ЧЕРЕЗ ИИ (НОВАЯ ФУНКЦИЯ) ---
@router.message(Command("ai_test"))
async def generate_ai_question(message: types.Message, ai_service):
    await message.answer("🧠 Придумываю новый вопрос...")
    try:
        q_data = await ai_service.generate_question()
        
        new_question = Question(
            id=999, 
            topic="ИИ-вопрос",
            text=q_data["question"],
            options=tuple(q_data["options"]),
            correct=q_data["correct"],
            explanation=q_data["explanation"]
        )
        
        await message.answer(
            f"📝 Вопрос от ИИ: {new_question.text}",
            parse_mode="HTML",
            reply_markup=question_kb(new_question)
        )
    except Exception as e:
        await message.answer(f"Ошибка генерации: {e}")
