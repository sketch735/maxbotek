import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import (
    create_user,
    get_user,
    update_user_balance,
    create_ticket,
    get_new_tickets,
    get_user_tickets,
    assign_ticket,
    update_ticket_data,
    complete_ticket,
    get_ticket,
    close_ticket,
    cur,
    DB
)

from keyboards import user_menu, admin_ticket_keyboard, profile_keyboard, cancel_keyboard

logging.basicConfig(level=logging.INFO)

# Загружаем переменные окружения
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

# Фиксированные цены за сдачу ресурсов
MAX_PRICE = 50   
CARD_PRICE = 100 

# Состояния FSM для процесса вывода средств
class TicketStates(StatesGroup):
    waiting_withdraw_amount = State()
    waiting_withdraw_link = State()

# ---------------- START ----------------
@dp.message(CommandStart())
async def start(message: Message):
    create_user(message.from_user.id)
    if message.from_user.id == ADMIN_ID:
        await message.answer("👔 Добро пожаловать, Администратор! Панель управления доступна по команде /admin.")
    else:
        await message.answer(
            "🚀 <b>MaxRentik CRM</b> активирован\n\nВыберите действие:",
            reply_markup=user_menu(),
            parse_mode="HTML"
        )

# ---------------- ADMIN PANEL ----------------
@dp.message(F.text == "/admin", F.from_user.id == ADMIN_ID)
async def admin_panel(message: Message):
    tickets = get_new_tickets()
    if not tickets:
        await message.answer("📭 Очередь заявок пуста.")
        return
    for t in tickets:
        await message.answer(
            f"🆕 Заявка #{t[0]} | Тип: <b>{t[2]}</b>\nПользователь: <code>{t[1]}</code>\nДанные: {t[4] or 'нет'}",
            reply_markup=admin_ticket_keyboard(t[0]),
            parse_mode="HTML"
        )

# ---------------- USER CALLBACKS ----------------
@dp.callback_query(F.data == "max")
async def max_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    ticket_id = create_ticket(call.from_user.id, "MAX")
    await call.message.edit_text(
        f"📦 <b>Заявка MAX #{ticket_id} создана!</b>\n\n"
        f"Для дальнейших действий, пожалуйста, напишите администратору в ЛС.\n"
        f"Ожидайте подтверждения от администратора.",
        reply_markup=cancel_keyboard(ticket_id),
        parse_mode="HTML"
    )
    # Уведомляем только админа
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>Новая заявка MAX #{ticket_id}</b>\n"
        f"От пользователя: {call.from_user.id} (@{call.from_user.username or 'нет'})",
        reply_markup=admin_ticket_keyboard(ticket_id),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "card")
async def card_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    ticket_id = create_ticket(call.from_user.id, "CARD")
    await call.message.edit_text(
        f"💳 <b>Заявка CARD #{ticket_id} создана!</b>\n\n"
        f"Для дальнейших действий, пожалуйста, напишите администратору в ЛС.\n"
        f"Ожидайте подтверждения от администратора.",
        reply_markup=cancel_keyboard(ticket_id),
        parse_mode="HTML"
    )
    # Уведомляем только админа
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>Новая заявка CARD #{ticket_id}</b>\n"
        f"От пользователя: {call.from_user.id} (@{call.from_user.username or 'нет'})",
        reply_markup=admin_ticket_keyboard(ticket_id),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "profile")
async def profile_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(call.from_user.id)
    if not user:
        create_user(call.from_user.id)
        user = get_user(call.from_user.id)
    balance = user[2]
    await call.message.edit_text(
        f"👤 <b>Ваш Профиль</b>\n\n"
        f"🆔 Ваш ID: <code>{call.from_user.id}</code>\n"
        f"💰 Баланс: <b>{balance} USDT</b>",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "main")
async def back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🚀 <b>MaxRentik CRM</b> активирован\n\nВыберите действие:",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )
    await call.answer()

# ---------------- WITHDRAW FLOW (USER) ----------------
@dp.callback_query(F.data == "withdraw")
async def withdraw_init(call: CallbackQuery, state: FSMContext):
    user = get_user(call.from_user.id)
    balance = user[2] if user else 0
    if balance <= 0:
        await call.answer("❌ У вас нет доступных средств для вывода!", show_alert=True)
        return
    await call.message.edit_text(
        f"💰 <b>Вывод средств</b>\n\n"
        f"Ваш текущий баланс: <b>{balance} USDT</b>\n"
        f"Введите сумму в $, которую вы хотите вывести:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="profile")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(TicketStates.waiting_withdraw_amount)
    await call.answer()

@dp.message(TicketStates.waiting_withdraw_amount)
async def withdraw_amount_received(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число:")
        return
    if amount <= 0:
        await message.answer("❌ Сумма должна быть больше нуля:")
        return
    user = get_user(message.from_user.id)
    balance = user[2] if user else 0
    if amount > balance:
        await message.answer(f"❌ Недостаточно средств! Ваш баланс: {balance} USDT. Введите другую сумму:")
        return
    
    await state.update_data(withdraw_amount=amount)
    await message.answer(
        f"ℹ️ Вы выбрали вывод <b>{amount} USDT</b>.\n\n"
        f"Теперь перейдите в @CryptoBot, создайте там Чековую ссылку или Счет (Invoice) на эту сумму, "
        f"и отправьте полученную ссылку сюда в чат:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="profile")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(TicketStates.waiting_withdraw_link)

@dp.message(TicketStates.waiting_withdraw_link)
async def withdraw_link_received(message: Message, state: FSMContext):
    link = message.text.strip()
    if "t.me/CryptoBot" not in link and "crypto.bot" not in link and not link.startswith("http"):
        await message.answer("❌ Пожалуйста, отправьте корректную ссылку на чек/счет CryptoBot:")
        return
    
    data = await state.get_data()
    amount = data.get("withdraw_amount")
    
    # Сразу холдируем баланс пользователя, чтобы избежать абуза
    update_user_balance(message.from_user.id, -amount)
    
    ticket_id = create_ticket(message.from_user.id, "WITHDRAW")
    update_ticket_data(ticket_id, f"Сумма: {amount} USDT\nСсылка: {link}")
    
    await message.answer(
        f"✅ <b>Заявка на вывод #{ticket_id} успешно создана!</b>\n\n"
        f"Сумма: <b>{amount} USDT</b>\n"
        f"Администратор проверит ссылку и выплатит средства. Ожидайте.",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )
    
    # Отправляем заявку в админ-панель
    await bot.send_message(
        ADMIN_ID,
        f"💰 <b>ЗАЯВКА НА ВЫВОД #{ticket_id}</b>\n\n"
        f"Пользователь: {message.from_user.id} (@{message.from_user.username or 'нет'})\n"
        f"Сумма к выплате: <b>{amount} USDT</b>\n"
        f"Ссылка для оплаты:\n{link}",
        reply_markup=admin_ticket_keyboard(ticket_id),
        parse_mode="HTML"
    )
    await state.clear()

# ---------------- ADMIN CALLBACKS ----------------
@dp.callback_query(F.data.startswith("take:"))
async def take(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Доступ только для админа", show_alert=True)
        return
    tid = int(call.data.split(":")[1])
    assign_ticket(tid, call.from_user.id)
    t = get_ticket(tid)
    if t:
        await bot.send_message(t[1], f"🟡 Ваша заявка #{tid} ({t[2]}) взята в работу админом. Ожидайте.")
    await call.answer("✅ Взято в работу")

@dp.callback_query(F.data.startswith("done:"))
async def done(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Доступ только для админа", show_alert=True)
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    if not t:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return
    if t[3] in ['done', 'rejected', 'canceled']:
        await call.answer("⚠️ Заявка уже обработана", show_alert=True)
        return
        
    if t[2] == "WITHDRAW":
        close_ticket(tid)
        await bot.send_message(t[1], f"✅ Ваша заявка на вывод #{tid} успешно выполнена и выплачена!")
    else:
        payout = MAX_PRICE if t[2] == "MAX" else CARD_PRICE
        complete_ticket(tid, payout)
        await bot.send_message(t[1], f"✅ Заявка #{tid} успешно завершена! Начислено {payout} USDT.")
        
    await call.message.edit_text(f"✅ Заявка #{tid} успешно закрыта как выполненная.")
    await call.answer("✅ Успешно завершено")

@dp.callback_query(F.data.startswith("admin_cancel:"))
async def admin_cancel(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Доступ только для админа", show_alert=True)
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    if not t:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return
    if t[3] in ['done', 'rejected', 'canceled']:
        await call.answer("⚠️ Заявка уже обработана", show_alert=True)
        return
        
    # Если отменяется вывод — возвращаем холдированные средства на баланс пользователя
    if t[2] == "WITHDRAW":
        try:
            lines = t[4].split("\n")
            amount_str = lines[0].replace("Сумма: ", "").replace(" USDT", "").strip()
            amount = float(amount_str)
            update_user_balance(t[1], amount)
        except Exception:
            pass
            
    cur.execute("UPDATE tickets SET status='rejected', completed_at=? WHERE id=?", 
                (datetime.utcnow().isoformat(), tid))
    DB.commit()
    
    await bot.send_message(t[1], f"❌ Ваша заявка #{tid} ({t[2]}) была отклонена администратором.")
    await call.message.edit_text(f"❌ Заявка #{tid} успешно отклонена администратором.")
    await call.answer("❌ Заявка отклонена")

# ---------------- USER CANCEL ----------------
@dp.callback_query(F.data.startswith("cancel:"))
async def cancel_ticket(call: CallbackQuery, state: FSMContext):
    await state.clear()
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    if t and t[3] == 'new':
        cur.execute("UPDATE tickets SET status='canceled', completed_at=? WHERE id=?", 
                    (datetime.utcnow().isoformat(), tid))
        DB.commit()
        await call.message.edit_text(f"❌ Вы отменили заявку #{tid}.", reply_markup=user_menu())
        await bot.send_message(ADMIN_ID, f"🚫 Пользователь отменил свою заявку #{tid}")
    else:
        await call.answer("⚠️ Заявку нельзя отменить, так как она уже в работе или закрыта.", show_alert=True)

# ---------------- RUN POLLING ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())