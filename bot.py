import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from db import (
    create_user,
    create_ticket,
    get_new_tickets,
    assign_ticket,
    close_ticket,
    get_ticket,
)

from keyboards import user_menu, admin_ticket_keyboard   # ← исправлено

logging.basicConfig(level=logging.INFO)

# === ЗАГРУЗКА ПЕРЕМЕННЫХ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env!")
if not ADMIN_ID:
    raise ValueError("❌ ADMIN_ID не найден в .env!")

ADMIN_ID = int(ADMIN_ID)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------------- START ----------------
@dp.message(CommandStart())
async def start(message: Message):
    create_user(message.from_user.id)
    await message.answer(
        "🚀 <b>MaxRentik CRM</b> активирован\n\nВыберите действие:",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )


# ---------------- CREATE TICKETS ----------------
@dp.callback_query(F.data == "max")
async def max_handler(call: CallbackQuery):
    create_ticket(call.from_user.id, "MAX")
    await call.message.answer("📦 MAX заявка создана")


@dp.callback_query(F.data == "card")
async def card_handler(call: CallbackQuery):
    ticket_id = create_ticket(call.from_user.id, "CARD")
    await call.message.answer(
        f"✅ CARD заявка #{ticket_id} создана\n\n"
        f"Напишите данные карты админу в личку:\n"
        f"@{ (await bot.get_me()).username }",
        parse_mode="HTML"
    )


# ---------------- ADMIN PANEL ----------------
@dp.message(F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    tickets = get_new_tickets()

    if not tickets:
        await message.answer("📭 Очередь пуста")
        return

    for t in tickets:
        await message.answer(
            f"🆕 Ticket #{t[0]}\nТип: {t[2]}\nПользователь: {t[1]}",
            reply_markup=admin_ticket_keyboard(t[0])   # ← исправлено
        )


# ---------------- TAKE & DONE ----------------
@dp.callback_query(F.data.startswith("take:"))
async def take(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    assign_ticket(tid, call.from_user.id)
    t = get_ticket(tid)
    await bot.send_message(t[1], "🟡 Заявка взята в работу")


@dp.callback_query(F.data.startswith("done:"))
async def done(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    close_ticket(tid)
    t = get_ticket(tid)
    await bot.send_message(t[1], "✅ Заявка завершена")


# ---------------- OTHER ----------------
@dp.message()
async def any_message(message: Message):
    await message.answer("📩 Сообщение принято")


# ---------------- RUN ----------------
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())