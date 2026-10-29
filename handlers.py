from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import get_main_keyboard # Предполагаем, что эта функция есть в твоем файле

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я твой помощник по подготовке к ОГЭ по информатике.\n"
        "Выбери действие:",
        reply_markup=get_main_keyboard()
    )

@router.callback_query(F.data == "theory")
async def show_theory(callback: types.CallbackQuery):
    text = (
        "📖 <b>Шпаргалка: Системы счисления</b>\n\n"
        "1️⃣ <b>Из 10-й в 2-ю:</b> Делим число на 2 и записываем остатки с конца.\n"
        "2️⃣ <b>Из 2-й в 10-ю:</b> Умножаем каждую цифру на 2 в степени её позиции."
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "test")
async def start_test(callback: types.CallbackQuery):
    # Здесь можно добавить логику теста
    await callback.message.answer("📝 Тест скоро появится! Пока что нажми /start.")
    await callback.answer()

@router.callback_query(F.data == "ask_ai")
async def ask_ai(callback: types.CallbackQuery):
    await callback.message.answer("🤖 Напиши свой вопрос по информатике, и я отвечу с помощью ИИ!")
    await callback.answer()

@router.message(F.text)
async def handle_text(message: types.Message, ai_service):
    # Отправляем текст в нейросеть
    await message.answer("⏳ Думаю над ответом...")
    answer = await ai_service.get_answer(message.text)
    await message.answer(answer)
