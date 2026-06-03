import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import (
    create_user, get_user, create_ticket, get_ticket,
    get_user_tickets, assign_ticket, complete_ticket,
    add_balance, update_ticket_status
)
from keyboards import (
    user_menu, profile_keyboard, cancel_keyboard,
    admin_ticket_keyboard
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("8821027720:AAG70ztoJJlwD46zZVv5guQaaV2s-PBQRAs")
ADMIN_ID = int(os.getenv("1613119562"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class MaxStates(StatesGroup):
    waiting_phone = State()
    waiting_code = State()


# ==================== START ====================
@dp.message(CommandStart())
async def start(message: Message):
    create_user(message.from_user.id)
    await message.answer(
        "👋 <b>Добро пожаловать в MaxRentik</b>\n\n"
        "Здесь можно сдавать MAX и карты.",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )


# ==================== PROFILE ====================
@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    user = get_user(call.from_user.id)
    tickets = get_user_tickets(call.from_user.id)
    
    max_count = sum(1 for t in tickets if t[2] == "MAX" and t[3] == "done")
    card_count = sum(1 for t in tickets if t[2] == "CARD" and t[3] == "done")
    balance = user[3] if user and len(user) > 3 else 0

    text = f"""<b>👤 Профиль</b>

🆔 <code>{call.from_user.id}</code>
📦 MAX сдано: <b>{max_count}</b>
💳 Карт сдано: <b>{card_count}</b>
💰 Баланс: <b>{balance} USDT</b>"""

    await call.message.edit_text(text, reply_markup=profile_keyboard(), parse_mode="HTML")


# ==================== CREATE TICKET ====================
@dp.callback_query(F.data.in_(["max", "card"]))
async def create_ticket_handler(call: CallbackQuery, state: FSMContext):
    ticket_type = "MAX" if call.data == "max" else "CARD"
    ticket_id = create_ticket(call.from_user.id, ticket_type)

    if ticket_type == "MAX":
        await call.message.edit_text(
            "📱 Отправьте номер телефона для MAX\nФормат: <code>+79xxxxxxxxx</code>",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(ticket_id)
        )
        await state.set_state(MaxStates.waiting_phone)
        await state.update_data(ticket_id=ticket_id)
    else:
        # CARD — сразу даём админа
        await call.message.edit_text(
            f"✅ Заявка на карту создана (#{ticket_id})\n\n"
            f"Перейдите в личку к админу для дальнейшей работы:\n"
            f"@{ (await bot.get_me()).username } или напрямую пишите админу.",
            parse_mode="HTML"
        )
        # Уведомляем админа
        await bot.send_message(
            ADMIN_ID,
            f"🆕 Новая CARD заявка #{ticket_id}\nПользователь: {call.from_user.id}"
        )


# ==================== MAX PHONE ====================
@dp.message(MaxStates.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    
    update_ticket_status(ticket_id, "phone_received", message.text)
    
    await message.answer(
        "🔄 Номер принят. Ожидайте код от админа.",
        reply_markup=cancel_keyboard(ticket_id)
    )
    await bot.send_message(
        ADMIN_ID,
        f"📱 MAX заявка #{ticket_id}\nНомер: {message.text}\nПользователь: {message.from_user.id}"
    )
    await state.clear()


# ==================== ADMIN PANEL ====================
@dp.message(F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    tickets = get_user_tickets(None)  # можно улучшить
    new_tickets = [t for t in get_user_tickets(None) if t[3] == 'new']  # упрощённо

    if not new_tickets:
        await message.answer("📭 Нет новых заявок")
        return

    for t in new_tickets:
        await message.answer(
            f"🆕 Заявка #{t[0]} | {t[2]}\nПользователь: {t[1]}",
            reply_markup=admin_ticket_keyboard(t[0]),
            parse_mode="HTML"
        )


# ==================== CALLBACKS ====================
@dp.callback_query(F.data.startswith("take:"))
async def take_ticket(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    assign_ticket(tid, call.from_user.id)
    t = get_ticket(tid)
    await bot.send_message(t[1], "🟡 Заявка взята в работу")
    await call.answer("✅ Взял в работу")


@dp.callback_query(F.data.startswith("done:"))
async def done_ticket(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    complete_ticket(tid, 50)  # пример выплаты 50 USDT за MAX
    t = get_ticket(tid)
    await bot.send_message(t[1], "✅ Заявка успешно завершена! Деньги начислены.")
    await call.answer("✅ Завершено")


# ==================== RUN ====================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())