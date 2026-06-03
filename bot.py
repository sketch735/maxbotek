import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import (
    create_user,
    get_user,
    create_ticket,
    get_new_tickets,
    get_user_tickets,
    assign_ticket,
    complete_ticket,
    get_ticket,
    update_ticket_data,
    close_ticket
)

from keyboards import user_menu, admin_ticket_keyboard, profile_keyboard, cancel_keyboard

logging.basicConfig(level=logging.INFO)

# Загружаем переменные из .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env!")
if not ADMIN_ID:
    raise ValueError("❌ ADMIN_ID не найден в .env!")

ADMIN_ID = int(ADMIN_ID)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

MAX_PRICE = 50   
CARD_PRICE = 100 

class TicketStates(StatesGroup):
    waiting_phone = State()


# ---------------- START ----------------
@dp.message(CommandStart())
async def start(message: Message):
    create_user(message.from_user.id)
    await message.answer(
        "🚀 <b>MaxRentik CRM</b> активирован\n\nВыберите действие:",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )


# ---------------- PROFILE ----------------
@dp.callback_query(F.data == "profile")
async def profile_handler(call: CallbackQuery):
    user = get_user(call.from_user.id)
    tickets = get_user_tickets(call.from_user.id)
    
    max_count = sum(1 for t in tickets if t[2] == "MAX" and t[3] == "done")
    card_count = sum(1 for t in tickets if t[2] == "CARD" and t[3] == "done")
    
    max_usd = max_count * MAX_PRICE
    card_usd = card_count * CARD_PRICE
    
    balance = user[2] if user else 0
    username = f"@{call.from_user.username}" if call.from_user.username else "Не установлен"

    text = f"""<b>👤 Ваш профиль:</b>

Юзернейм: <b>{username}</b>
ID: <code>{call.from_user.id}</code>

📦 <b>Сдано MAX:</b> {max_count} шт. ({max_usd} $)
💳 <b>Сдано карт:</b> {card_count} шт. ({card_usd} $)

💰 <b>Баланс:</b> {balance} USDT"""

    await call.message.edit_text(text, reply_markup=profile_keyboard(), parse_mode="HTML")


# ---------------- CREATE TICKETS ----------------
@dp.callback_query(F.data == "max")
async def max_handler(call: CallbackQuery, state: FSMContext):
    ticket_id = create_ticket(call.from_user.id, "MAX")
    
    await call.message.edit_text(
        "📱 <b>Отправьте номер начиная с цифры +7</b>\n(только номера РФ)",
        reply_markup=cancel_keyboard(ticket_id),
        parse_mode="HTML"
    )
    await state.set_state(TicketStates.waiting_phone)
    await state.update_data(ticket_id=ticket_id)


@dp.callback_query(F.data == "card")
async def card_handler(call: CallbackQuery):
    ticket_id = create_ticket(call.from_user.id, "CARD")
    
    await call.message.edit_text(
        "💳 <b>Для сдачи карты, пожалуйста, отпишите администратору @yorknft для дальнейших действий.</b>",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )
    
    username = f"@{call.from_user.username}" if call.from_user.username else "Нет юзернейма"
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>Новая заявка на КАРТУ #{ticket_id}</b>\n"
        f"Пользователь: {username} (ID: <code>{call.from_user.id}</code>)\n"
        f"Ожидайте сообщения от клиента.",
        parse_mode="HTML"
    )


# ---------------- FSM: RECEIVE PHONE ----------------
@dp.message(TicketStates.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    state_data = await state.get_data()
    ticket_id = state_data.get("ticket_id")
    phone = message.text

    update_ticket_data(ticket_id, phone)
    
    await message.answer(
        "🔄 <b>Номер принят.</b> Админ отправит код на этот номер и свяжется с вами для работы.",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )
    
    username = f"@{message.from_user.username}" if message.from_user.username else "Нет юзернейма"
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>Новая заявка MAX #{ticket_id}</b>\n"
        f"📱 Номер: <code>{phone}</code>\n"
        f"👤 Пользователь: {username} (ID: <code>{message.from_user.id}</code>)",
        parse_mode="HTML"
    )
    await state.clear()


# ---------------- ADMIN PANEL ----------------
@dp.message(F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    tickets = get_new_tickets()

    if not tickets:
        await message.answer("📭 Очередь пуста")
        return

    for t in tickets:
        phone_info = f"\nДанные: <code>{t[4]}</code>" if t[4] else ""
        await message.answer(
            f"🆕 Ticket #{t[0]}\nТип: {t[2]}\nПользователь: {t[1]}{phone_info}",
            reply_markup=admin_ticket_keyboard(t[0]),
            parse_mode="HTML"
        )


# ---------------- TAKE & DONE & CANCEL ----------------
@dp.callback_query(F.data.startswith("take:"))
async def take(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    assign_ticket(tid, call.from_user.id)
    t = get_ticket(tid)
    await bot.send_message(t[1], "🟡 Ваша заявка взята в работу админом. Ожидайте.")
    await call.answer("✅ Взято в работу")


@dp.callback_query(F.data.startswith("done:"))
async def done(call: CallbackQuery):
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    
    payout = MAX_PRICE if t[2] == "MAX" else CARD_PRICE
    complete_ticket(tid, payout)
    
    await bot.send_message(t[1], f"✅ Заявка #{tid} успешно завершена! Начислено {payout} USDT.")
    await call.answer(f"✅ Завершено (+{payout} USDT)")


@dp.callback_query(F.data.startswith("cancel:"))
async def cancel_ticket(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "❌ Заявка отменена.",
        reply_markup=user_menu()
    )


@dp.callback_query(F.data == "main")
async def back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🚀 <b>MaxRentik CRM</b> активирован\n\nВыберите действие:",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )


# ---------------- OTHER ----------------
@dp.message()
async def any_message(message: Message):
    await message.answer("📩 Сообщение принято")


# ---------------- RUN ----------------
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())