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

from keyboards import user_menu, admin_ticket

logging.basicConfig(level=logging.INFO)

# === Правильная загрузка из .env ===
BOT_TOKEN = os.getenv("8821027720:AAG70ztoJJlwD46zZVv5guQaaV2s-PBQRAs")
ADMIN_ID = int(os.getenv("1613119562") or 0)

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")
if ADMIN_ID == 0:
    raise ValueError("❌ ADMIN_ID не найден в .env файле!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------------- START ----------------
@dp.message(CommandStart())
async def start(message: Message):
    create_user(message.from_user.id)
    await message.answer(
        "🚀 SaaS CRM активирован\n\nВыберите действие:",
        reply_markup=user_menu()
    )


# ---------------- CREATE TICKETS ----------------
@dp.callback_query(F.data == "max")
async def max(call: CallbackQuery):
    create_ticket(call.from_user.id, "MAX")
    await call.message.answer("📦 MAX заявка создана")


@dp.callback_query(F.data == "card")
async def card(call: CallbackQuery):
    ticket_id = create_ticket(call.from_user.id, "CARD")
    await call.message.answer(
        f"✅ CARD заявка #{ticket_id} создана\n\n"
        f"Перейдите в личку к админу для сдачи данных карты:\n"
        f"@{ (await bot.get_me()).username }"
    )


# ---------------- MY TICKETS ----------------
@dp.callback_query(F.data == "my")
async def my(call: CallbackQuery):
    tickets = get_new_tickets()  # можно доработать под пользователя
    await call.message.answer(f"📊 Активных заявок в системе: {len(tickets)}")


# ---------------- ADMIN PANEL ----------------
@dp.message(F.from_user.id == ADMIN_ID)
async def admin(message: Message):
    tickets = get_new_tickets()

    if not tickets:
        await message.answer("📭 Очередь пуста")
        return

    for t in tickets:
        await message.answer(
            f"🆕 Ticket #{t[0]}\nТип: {t[2]}\nПользователь: {t[1]}",
            reply_markup=admin_ticket(t[0])
        )


# ---------------- TAKE ----------------
@dp.callback_query(F.data.startswith("take:"))
async def take(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    assign_ticket(tid, call.from_user.id)
    t = get_ticket(tid)
    await bot.send_message(t[1], "🟡 Заявка взята в работу")


# ---------------- CHAT ----------------
@dp.callback_query(F.data.startswith("chat:"))
async def chat(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    await call.message.answer(f"💬 Чат с тикетом #{tid} открыт — пиши сообщения")


# ---------------- MESSAGE ROUTER ----------------
@dp.message()
async def router(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠 Ответ отправлен (логика чата позже)")
        return
    await message.answer("📩 Сообщение принято в обработку")


# ---------------- DONE ----------------
@dp.callback_query(F.data.startswith("done:"))
async def done(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    close_ticket(tid)
    t = get_ticket(tid)
    await bot.send_message(t[1], "✅ Заявка завершена")


# ---------------- RUN ----------------
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())