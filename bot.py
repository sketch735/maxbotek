import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext\nfrom aiogram.fsm.state import State, StatesGroup

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
    reject_ticket_db,
    cur,
    DB
)

from keyboards import user_menu, admin_ticket_keyboard, profile_keyboard, back_to_main

logging.basicConfig(level=logging.INFO)

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

MAX_PRICE = 50.0   
CARD_PRICE = 100.0 

class BotStates(StatesGroup):
    waiting_phone = State()
    waiting_withdraw_amount = State()

# ==================== USER FLOW ====================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    create_user(message.from_user.id)
    await message.answer(
        "🚀 <b>MaxRentik CRM активирован</b>\n\nВыберите действие в меню ниже:",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "main")
async def back_to_main_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🚀 <b>MaxRentik CRM активирован</b>\n\nВыберите действие в меню ниже:",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )
    await call.answer()

# ---- 1.1 СДАТЬ MAX (НОМЕР РФ) ----
@dp.callback_query(F.data == "max")
async def hand_over_max(call: CallbackQuery, state: FSMContext):
    await state.set_state(BotStates.waiting_phone)
    await call.message.edit_text(
        "📦 <b>Сдача MAX (Номера РФ)</b>\n\nВведите ваш номер телефона (каждый с новой строки, если их несколько):",
        reply_markup=back_to_main(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.message(BotStates.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    phones = message.text.strip()
    ticket_id = create_ticket(message.from_user.id, "MAX", data=phones)
    await state.clear()
    
    await message.answer(
        f"✅ <b>Заявка #{ticket_id} на номер(а) успешно отправлена!</b>\n"
        f"Администратор проверяет её. Пожалуйста, ожидайте уведомлений.",
        reply_markup=back_to_main(),
        parse_mode="HTML"
    )
    
    # Отправка администратору
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>Новая заявка #{ticket_id} [MAX]</b>\n"
        f"Пользователь: {message.from_user.id} (@{message.from_user.username})\n"
        f"Номера:\n<code>{phones}</code>",
        reply_markup=admin_ticket_keyboard(ticket_id, "MAX"),
        parse_mode="HTML"
    )

# ---- 1.2 СДАТЬ КАРТУ ----
@dp.callback_query(F.data == "card")
async def hand_over_card(call: CallbackQuery):
    # Автоматически создаем фоновую заявку, чтобы админ мог её подтвердить через бота
    ticket_id = create_ticket(call.from_user.id, "CARD", data="Сделка в ЛС")
    
    # Получаем юзернейм админа
    try:
        admin_chat = await bot.get_chat(ADMIN_ID)
        admin_username = admin_chat.username if admin_chat.username else "admin"
    except Exception:
        admin_username = "admin"

    await call.message.edit_text(
        f"💳 <b>Сдача карты происходит через администратора!</b>\n\n"
        f"Для проведения сделки напишите напрямую в личные сообщения:\n"
        f"👉 @{admin_username}\n\n"
        f"<i>Сообщите админу, что вы создали заявку #{ticket_id}. "
        f"После успешной сдачи карты админ подтвердит её в боте, и деньги поступят на баланс.</i>",
        reply_markup=back_to_main(),
        parse_mode="HTML"
    )
    
    # Уведомляем админа о намерении сдать карту
    await bot.send_message(
        ADMIN_ID,
        f"💳 <b>Пользователь хочет сдать карту! Заявка #{ticket_id}</b>\n"
        f"Пользователь: {call.from_user.id} (@{call.from_user.username})\n"
        f"Ожидайте сообщения в ЛС.",
        reply_markup=admin_ticket_keyboard(ticket_id, "CARD"),
        parse_mode="HTML"
    )
    await call.answer()

# ---- ЛОГИКА ПРОФИЛЯ И СТАТИСТИКИ ----
@dp.callback_query(F.data == "profile")
async def show_profile(call: CallbackQuery):
    user = get_user(call.from_user.id)
    tickets = get_user_tickets(call.from_user.id)
    
    balance = user[2] if user else 0.0
    
    # Считаем статистику по статусам
    waiting_count = len([t for t in tickets if t[3] == 'new'])
    processing_count = len([t for t in tickets if t[3] == 'processing'])
    done_count = len([t for t in tickets if t[3] == 'done'])
    error_count = len([t for t in tickets if t[3] == 'rejected'])
    
    await call.message.edit_text(
        f"👤 <b>Ваш профиль и статистика:</b>\n\n"
        f"💰 <b>Текущий баланс:</b> {balance} USDT\n\n"
        f"⏳ В ожидании: {waiting_count}\n"
        f"🛠 В работе: {processing_count}\n"
        f"✅ Засчитано: {done_count}\n"
        f"❌ Ошибки: {error_count}\n",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )
    await call.answer()

# ---- 1.3 ВЫВОД СРЕДСТВ (ЗАЩИТА ОТ КРАЖИ) ----
@dp.callback_query(F.data == "withdraw")
async def withdraw_start(call: CallbackQuery, state: FSMContext):
    user = get_user(call.from_user.id)
    balance = user[2] if user else 0.0
    
    if balance < 3.0:
        await call.answer("❌ Минимальная сумма для вывода составляет $3!", show_alert=True)
        return
        
    await state.set_state(BotStates.waiting_withdraw_amount)
    await call.message.edit_text(
        f"💰 <b>Вывод средств через Crypto Bot</b>\n\n"
        f"Ваш текущий баланс: {balance} USDT\n"
        f"Минимальная сумма: $3\n\n"
        f"Введите сумму вывода:",
        reply_markup=back_to_main(),
        parse_mode="HTML"
    )
    await call.answer()

@dp.message(BotStates.waiting_withdraw_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    balance = user[2] if user else 0.0
    
    try:
        amount = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число (например, 5 или 10.50).")
        return

    if amount < 3.0:
        await message.answer("❌ Минимальная сумма вывода составляет $3.")
        return

    # СТРОГАЯ ПРОВЕРКА (1.3): Сумма не может превышать текущий баланс
    if amount > balance:
        await message.answer(
            f"❌ <b>Ошибка безопасности!</b>\n"
            f"Запрошенная сумма ({amount} USDT) превышает ваш текущий баланс ({balance} USDT).\n"
            f"Пожалуйста, введите корректную сумму.",
            reply_markup=back_to_main(),
            parse_mode="HTML"
        )
        return

    # Списываем баланс сразу во избежание повторных запросов до обработки заявки
    update_user_balance(message.from_user.id, -amount)
    await state.clear()
    
    ticket_id = create_ticket(message.from_user.id, "WITHDRAW", data=f"Вывод {amount} USDT")
    
    await message.answer(
        f"✅ <b>Заявка на вывод #{ticket_id} на сумму {amount} USDT успешно создана!</b>\n\n"
        f"Переводы выполняются в автоматическом режиме с 20:00 до 23:00 (МСК).\n"
        f"⚠️ <i>Убедитесь, что ваш Crypto Bot активен и не заблокирован. Чеки выдаются строго на ваш аккаунт.</i>",
        reply_markup=back_to_main(),
        parse_mode="HTML"
    )
    
    # Сообщение админу
    await bot.send_message(
        ADMIN_ID,
        f"💰 <b>Заявка на вывод #{ticket_id}</b>\n"
        f"Пользователь: {message.from_user.id} (@{message.from_user.username})\n"
        f"Сумма к выплате: <code>{amount}</code> USDT",
        reply_markup=admin_ticket_keyboard(ticket_id, "WITHDRAW"),
        parse_mode="HTML"
    )

# ==================== ADMIN ACTIONS ====================

@dp.callback_query(F.data.startswith("take:"))
async def admin_take_ticket(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    assign_ticket(tid, ADMIN_ID)
    t = get_ticket(tid)
    
    await bot.send_message(t[1], f"🟡 Ваша заявка #{tid} ({t[2]}) взята администратором в работу.")
    await call.message.edit_text(f"🛠 Заявка #{tid} переведена в статус 'В работе'.")
    await call.answer("Взято в работу")

@dp.callback_query(F.data.startswith("ask_code:"))
async def admin_ask_code(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    
    # 1.1 Пишет пользователю, чтобы тот посмотрел код
    await bot.send_message(
        t[1], 
        f"⚠️ <b>Внимание!</b> Администратор проверяет заявку #{tid}.\n"
        f"Пожалуйста, <b>посмотрите код подтверждения</b> на вашем телефоне и будьте готовы передать его админу в случае необходимости!"
    )
    await call.answer("🔔 Уведомление о коде отправлено пользователю!")

@dp.callback_query(F.data.startswith("done:"))
async def admin_done_ticket(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    
    if t[3] == 'done':
        await call.answer("Эта заявка уже выполнена!", show_alert=True)
        return

    payout = 0.0
    if t[2] == "MAX":
        payout = MAX_PRICE
    elif t[2] == "CARD":
        payout = CARD_PRICE
    # Для вывода баланс уже был вычтен при создании, выплачиваем молча
    
    complete_ticket(tid, payout)
    
    if t[2] == "WITHDRAW":
        await bot.send_message(t[1], f"✅ Ваша заявка на вывод #{tid} успешно выполнена! Чек отправлен.")
    else:
        await bot.send_message(t[1], f"✅ Заявка #{tid} ({t[2]}) успешно одобрена! Баланс пополнен на {payout} USDT.")
        
    await call.message.edit_text(f"✅ Заявка #{tid} успешно завершена.")
    await call.answer("Выполнено!")

@dp.callback_query(F.data.startswith("admin_cancel:"))
async def admin_reject_ticket(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    
    if t[3] == 'done':
        await call.answer("Нельзя отменить уже выполненную заявку!", show_alert=True)
        return
        
    # Если это был вывод, возвращаем деньги на баланс обратно пользователю
    if t[2] == "WITHDRAW":
        try:
            amount_str = t[4].replace("Вывод ", "").replace(" USDT", "").strip()
            amount = float(amount_str)
            update_user_balance(t[1], amount)
        except Exception:
            pass

    reject_ticket_db(tid)
    await bot.send_message(t[1], f"❌ Ваша заявка #{tid} ({t[2]}) была отклонена администратором.")
    await call.message.edit_text(f"❌ Заявка #{tid} успешно отклонена.")
    await call.answer("Отклонено")

# ==================== ЗАПУСК БОТА ====================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())