import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

from db import get_user, create_user, add_request, create_ticket
from services import check_limit, create_invoice

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------- UI ----------
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Кабинет", callback_data="cabinet")],
        [InlineKeyboardButton(text="🎫 Тикет", callback_data="ticket")],
        [InlineKeyboardButton(text="💳 Оплата", callback_data="pay")]
    ])


# ---------- START ----------
@dp.message(CommandStart())
async def start(message: Message):
    create_user(message.from_user.id)

    await message.answer(
        "🚀 SaaS бот запущен",
        reply_markup=menu()
    )


# ---------- CABINET ----------
@dp.callback_query(F.data == "cabinet")
async def cabinet(call: CallbackQuery):
    user = get_user(call.from_user.id)

    await call.message.edit_text(
        f"""📊 Кабинет

ID: {call.from_user.id}
Тариф: {user[1]}
Запросов: {user[2]}/лимит"""
    )


# ---------- TICKET ----------
@dp.callback_query(F.data == "ticket")
async def ticket(call: CallbackQuery):
    create_ticket(call.from_user.id, "test ticket")

    await call.message.answer("🎫 Заявка создана")


# ---------- PAYMENT ----------
@dp.callback_query(F.data == "pay")
async def pay(call: CallbackQuery):
    invoice = await create_invoice(5)

    await call.message.answer(
        f"💳 Оплата создана:\n{invoice}"
    )


# ---------- SIMPLE USAGE + LIMIT ----------
@dp.message()
async def all_messages(message: Message):
    user = get_user(message.from_user.id)

    if not check_limit(user):
        await message.answer("❌ Лимит исчерпан. Обновите тариф")
        return

    add_request(message.from_user.id)

    await message.answer("✅ Запрос принят")


# ---------- ADMIN ----------
@dp.message(F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    await message.answer("🛠 Admin mode active")


# ---------- RUN ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())