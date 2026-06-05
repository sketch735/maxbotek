import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey

from db import (
    create_user, get_user, update_user_balance, create_ticket,
    get_ticket, assign_ticket, update_ticket_data, complete_ticket,
    reject_ticket_db, get_pending_withdrawals, get_all_users_stat,
    increment_max_submitted, increment_cards_submitted
)
from keyboards import (
    user_menu, admin_ticket_keyboard, profile_keyboard,
    back_to_main, subscription_keyboard, admin_withdraw_keyboard,
    card_type_keyboard
)
from services import create_invoice

logging.basicConfig(level=logging.INFO)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== Состояния ====================
class TicketStates(StatesGroup):
    waiting_phone = State()
    waiting_card = State()
    waiting_withdraw_amount = State()
    waiting_for_code = State()
    waiting_card_price = State()
    waiting_card_details = State()  # Для реквизитов после выбора типа карты
    waiting_code = State()

# ==================== Middleware ====================
class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data: dict):
        user = event.from_user if hasattr(event, 'from_user') else getattr(event, 'message', None).from_user
        if not user or user.id == ADMIN_ID:
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "check_subscription":
            return await handler(event, data)

        try:
            member = await data['bot'].get_chat_member("@adteoamdkmMAX", user.id)
            if member.status in ["member", "administrator", "creator"]:
                return await handler(event, data)
        except Exception as e:
            logging.error(f"Subscription check error: {e}")

        text = "⚠️ <b>Для работы с ботом необходимо подписаться на канал!</b>"
        kb = subscription_keyboard()
        
        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
            await event.answer()
        return

dp.message.outer_middleware(SubscriptionMiddleware())
dp.callback_query.outer_middleware(SubscriptionMiddleware())

# ==================== Старт ====================
@dp.message(CommandStart())
async def start_cmd(message: Message):
    create_user(message.from_user.id)
    await message.answer(
        "🚀 <b>MaxRentik Приветствует!</b>\n\n"
        "Для работы с нашим ботом, подпишитесь на канал ниже, иначе доступ будет ограничен.",
        reply_markup=subscription_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_subscription")
async def check_subscription(call: CallbackQuery):
    try:
        member = await bot.get_chat_member("@adteoamdkmMAX", call.from_user.id)
        if member.status in ["member", "administrator", "creator"]:
            await call.message.edit_text(
                "✅ <b>Подписка подтверждена!</b>\nДобро пожаловать в главное меню:",
                reply_markup=user_menu(),
                parse_mode="HTML"
            )
        else:
            await call.answer("❌ Вы не подписаны!", show_alert=True)
    except:
        await call.answer("⚠️ Ошибка проверки.", show_alert=True)

@dp.callback_query(F.data == "main")
async def main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🚀 <b>MaxRentik Приветствует!</b>\n\nВыберите действие:",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )

# ==================== Профиль ====================
@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    user = get_user(call.from_user.id) or (None, None, 0.0, 0.0, 0, 0)
    await call.message.edit_text(
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"💰 Баланс: <b>{user[2]} USDT</b>\n"
        f"📈 Всего заработано: <b>{user[3]} USDT</b>\n"
        f"📦 Сдано MAX: <b>{user[4]}</b>\n"
        f"💳 Сдано карт: <b>{user[5]}</b>",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )

# ==================== Сдача MAX / CARD ====================
@dp.callback_query(F.data == "max")
async def process_max(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("📦 Введите номер телефона / счёт MAX:", reply_markup=back_to_main())
    await state.set_state(TicketStates.waiting_phone)

@dp.callback_query(F.data == "card")
async def process_card(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("💳 Выберите тип карты:", reply_markup=card_type_keyboard())
    await state.clear()

@dp.callback_query(F.data.startswith("card_type:"))
async def card_type_selected(call: CallbackQuery, state: FSMContext):
    card_type = call.data.split(":")[1]
    card_names = {
        "tbank": "Т-Банк",
        "alfa": "Альфа-Банк",
        "sber": "СберБанк",
        "other": "Другая карта"
    }
    name = card_names.get(card_type, "Карта")
    await call.message.edit_text(
        f"💳 Вы выбрали: <b>{name}</b>\n\nВведите реквизиты карты (номер, ФИО и т.д.):",
        reply_markup=back_to_main(),
        parse_mode="HTML"
    )
    await state.set_state(TicketStates.waiting_card_details)
    await state.update_data(card_type=name)

@dp.message(TicketStates.waiting_phone)
async def phone_input(message: Message, state: FSMContext):
    ticket_id = create_ticket(message.from_user.id, "MAX", f"Телефон: {message.text}")
    increment_max_submitted(message.from_user.id)
    await message.answer(f"✅ Заявка #{ticket_id} создана!", reply_markup=user_menu())
    await bot.send_message(ADMIN_ID, f"🆕 Новая заявка #{ticket_id} (MAX)", 
                           reply_markup=admin_ticket_keyboard(ticket_id, "MAX"), parse_mode="HTML")
    await state.clear()

@dp.message(TicketStates.waiting_card_details)
async def card_details_input(message: Message, state: FSMContext):
    data = await state.get_data()
    card_type = data.get("card_type", "CARD")
    full_data = f"Тип: {card_type}\nРеквизиты: {message.text}"
    
    ticket_id = create_ticket(message.from_user.id, "CARD", full_data)
    increment_cards_submitted(message.from_user.id)
    
    await message.answer(f"✅ Заявка #{ticket_id} создана!", reply_markup=user_menu())
    await bot.send_message(
        ADMIN_ID, 
        f"🆕 Новая заявка #{ticket_id} (CARD - {card_type})", 
        reply_markup=admin_ticket_keyboard(ticket_id, "CARD"), 
        parse_mode="HTML"
    )
    await state.clear()

# ==================== Вывод средств ====================
@dp.callback_query(F.data == "withdraw")
async def withdraw_start(call: CallbackQuery, state: FSMContext):
    user = get_user(call.from_user.id)
    balance = user[2] if user else 0
    if balance <= 0:
        return await call.answer("❌ Недостаточно средств!", show_alert=True)
    
    await call.message.edit_text(f"💰 Баланс: {balance} USDT\nВведите сумму для вывода:", reply_markup=back_to_main())
    await state.set_state(TicketStates.waiting_withdraw_amount)

@dp.message(TicketStates.waiting_withdraw_amount)
async def withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
    except:
        return await message.answer("❌ Введите корректную сумму.")

    user = get_user(message.from_user.id)
    if amount > user[2]:
        return await message.answer("❌ Сумма превышает баланс.")

    invoice = await create_invoice(amount, f"Вывод #{message.from_user.id}")
    if invoice.get("ok"):
        invoice_url = invoice["result"]["pay_url"]
        ticket_id = create_ticket(message.from_user.id, "WITHDRAW", f"Вывод {amount} USDT", invoice_url)
        
        await message.answer(f"✅ Заявка на вывод #{ticket_id} создана!\nОжидайте оплаты.", reply_markup=user_menu())
        
        await bot.send_message(
            ADMIN_ID,
            f"💰 <b>Заявка на вывод #{ticket_id}</b>\n"
            f"Пользователь: <code>{message.from_user.id}</code>\n"
            f"Сумма: {amount} USDT\n"
            f"Чек: {invoice_url}",
            reply_markup=admin_withdraw_keyboard(ticket_id),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка создания чека.")
    await state.clear()

# ==================== Админ: Оплата вывода ====================
@dp.callback_query(F.data.startswith("paid:"))
async def paid_withdraw(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    if not t:
        return await call.answer("Заявка не найдена")
    
    complete_ticket(tid, 0)
    await bot.send_message(t[1], f"✅ Вывод по заявке #{tid} успешно выполнен!")
    await call.message.edit_text(f"✅ Выплата #{tid} подтверждена.")
    await call.answer("Оплачено!")

# ==================== Админ: CARD — ручной ценник ====================
@dp.callback_query(F.data.startswith("done:"))
async def done_callback(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    if not t:
        return await call.answer("Заявка не найдена")

    if t[2] == "CARD":
        await call.message.edit_text("💰 Введите сумму, которую начислить пользователю за карту:")
        await state.set_state(TicketStates.waiting_card_price)
        await state.update_data(ticket_id=tid)
        return

    # Для MAX
    complete_ticket(tid, 4.4 if t[2] == "MAX" else 0)
    await call.message.edit_text(f"✅ Заявка #{tid} завершена.")
    await call.answer("Готово!")

@dp.message(TicketStates.waiting_card_price)
async def card_price_input(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        data = await state.get_data()
        tid = data.get("ticket_id")
        complete_ticket(tid, amount)
        await message.answer(f"✅ Карта по заявке #{tid} оплачена на {amount} USDT.")
        await bot.send_message(ADMIN_ID, f"✅ Карта #{tid} завершена на {amount} USDT.")
    except:
        await message.answer("❌ Неверная сумма.")
    await state.clear()

# ==================== Админ: Взять в работу, Отклонить, Запрос кода ====================

@dp.callback_query(F.data.startswith("take:"))
async def take_ticket(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    assign_ticket(tid, ADMIN_ID)
    await call.message.edit_text(f"🟡 Заявка #{tid} взята в работу.")
    await call.answer("Взято в работу!")

@dp.callback_query(F.data.startswith("admin_cancel:"))
async def admin_cancel(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    reject_ticket_db(tid)
    t = get_ticket(tid)
    if t:
        await bot.send_message(t[1], f"❌ Заявка #{tid} отклонена администратором.")
    await call.message.edit_text(f"❌ Заявка #{tid} отклонена.")
    await call.answer("Отклонено!")

@dp.callback_query(F.data.startswith("ask_code:"))
async def ask_code(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    if not t or t[1] is None:
        return await call.answer("Заявка не найдена")
    
    await bot.send_message(
        t[1], 
        "📨 На ваш номер MAX был отправлен SMS-код.\nПожалуйста, введите 6-значный код:",
        reply_markup=back_to_main()
    )
    await call.answer("Запрос кода отправлен пользователю!")
    
    await state.set_state(TicketStates.waiting_code)
    await state.update_data(ticket_id=tid)

@dp.message(TicketStates.waiting_code)
async def code_input(message: Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    tid = data.get("ticket_id")
    
    if tid:
        t = get_ticket(tid)
        if t:
            await bot.send_message(
                ADMIN_ID,
                f"🔑 Код от пользователя {message.from_user.id} по заявке #{tid}:\n<code>{code}</code>",
                parse_mode="HTML"
            )
            await message.answer("✅ Код отправлен администратору!")
    
    await state.clear()

@dp.message(F.from_user.id == ADMIN_ID, Command("tab"))
async def tab_command(message: Message):
    withdrawals = get_pending_withdrawals()
    if not withdrawals:
        return await message.answer("📭 Нет активных заявок на вывод.")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = "📋 <b>Заявки на выплату:</b>\n\n"
    
    for w in withdrawals:
        tid, uid, data, url = w
        text += f"#{tid} | User: <code>{uid}</code> | {data}\n\n"
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"💰 Выплатить #{tid} ({uid})", 
            callback_data=f"pay_withdraw:{tid}"
        )])
    
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("pay_withdraw:"))
async def pay_withdraw_inline(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    if not t:
        return await call.answer("Заявка не найдена")
    
    try:
        # Пытаемся извлечь сумму
        amount_str = [word for word in t[3].split() if word.replace('.', '', 1).isdigit()]
        amount = float(amount_str[0]) if amount_str else 0
        invoice = await create_invoice(amount, f"Выплата #{tid} пользователю {t[1]}")
        if invoice.get("ok"):
            invoice_url = invoice["result"]["pay_url"]
            await call.message.edit_text(f"✅ Чек создан для заявки #{tid}\nСсылка: {invoice_url}")
            await bot.send_message(ADMIN_ID, f"Чек для #{tid}: {invoice_url}")
        else:
            await call.answer("Ошибка создания чека")
    except:
        await call.answer("Не удалось извлечь сумму")

@dp.message(F.from_user.id == ADMIN_ID, Command("admin"))
async def toggle_admin(message: Message):
    await message.answer("🔧 Админ-панель активна (вы уже администратор).")

# ==================== Запуск ====================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())