# FILE: bot.py

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
    add_message,
    get_messages
)

from keyboards import user_menu, admin_ticket

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("8821027720:AAG70ztoJJlwD46zZVv5guQaaV2s-PBQRAs")
ADMIN_ID = int(os.getenv("1613119562"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------------- START ----------------
@dp.message(CommandStart())
async def start(message: Message):
    create_user(message.from_user.id)

    await message.answer(
        "🚀 SaaS CRM активирован",
        reply_markup=user_menu()
    )


# ---------------- USER CREATE ----------------
@dp.callback_query(F.data == "max")
async def max(call: CallbackQuery):
    create_ticket(call.from_user.id, "MAX")
    await call.message.answer("📦 MAX заявка создана")


@dp.callback_query(F.data == "card")
async def card(call: CallbackQuery):
    create_ticket(call.from_user.id, "CARD")
    await call.message.answer("💳 CARD заявка создана")


# ---------------- USER LIST ----------------
@dp.callback_query(F.data == "my")
async def my(call: CallbackQuery):
    tickets = get_new_tickets()

    await call.message.answer(f"📊 У вас {len(tickets)} активных заявок")


# ---------------- ADMIN PANEL ----------------
@dp.message(F.from_user.id == ADMIN_ID)
async def admin(message: Message):
    tickets = get_new_tickets()

    if not tickets:
        await message.answer("📭 Очередь пуста")
        return

    for t in tickets:
        await message.answer(
            f"🆕 Ticket #{t[0]}\nType: {t[2]}",
            reply_markup=admin_ticket(t[0])
        )


# ---------------- TAKE ----------------
@dp.callback_query(F.data.startswith("take:"))
async def take(call: CallbackQuery):
    tid = int(call.data.split(":")[1])

    assign_ticket(tid, call.from_user.id)

    t = get_ticket(tid)

    await bot.send_message(t[1], "🟡 Взято в работу")


# ---------------- CHAT MODE ----------------
@dp.callback_query(F.data.startswith("chat:"))
async def chat(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    await call.message.answer(f"💬 Чат с ticket #{tid} — просто пиши сообщения")


# ---------------- MESSAGE ROUTING ----------------
@dp.message()
async def router(message: Message):
    text = message.text

    # если админ отвечает — надо привязать позже (упрощённо MVP логика)
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠 Ответ отправлен")
        return

    # обычный пользователь → просто логируем
    await message.answer("📩 Принято в обработку")


# ---------------- CLOSE ----------------
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