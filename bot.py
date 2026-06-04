import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey

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
    get_all_users_stat
)

from keyboards import (
    user_menu, 
    admin_ticket_keyboard, 
    profile_keyboard, 
    back_to_main,
    subscription_keyboard
)

logging.basicConfig(level=logging.INFO)

# Загрузка конфигурации
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

# Фиксированные цены
MAX_PRICE = 4.4   
CARD_PRICE = 100.0 

# Состояния FSM
class TicketStates(StatesGroup):
    waiting_phone = State()
    waiting_card = State()
    waiting_withdraw_amount = State()
    waiting_for_code = State()

# ==================== ИСПРАВЛЕННЫЙ MIDDLEWARE ====================
class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update | Message | CallbackQuery, data: dict):
        user = None
        
        if hasattr(event, 'message') and event.message:           # Update
            user = event.message.from_user
        elif hasattr(event, 'from_user'):                         # Message или CallbackQuery
            user = event.from_user

        if not user:
            return await handler(event, data)

        # Администратора пропускаем всегда
        if user.id == ADMIN_ID:
            return await handler(event, data)

        # Пропускаем проверку подписки
        if isinstance(event, CallbackQuery) and event.data == "check_subscription":
            return await handler(event, data)

        try:
            member = await data['bot'].get_chat_member(chat_id="@adteoamdkmMAX", user_id=user.id)
            if member.status in ["member", "administrator", "creator"]:
                return await handler(event, data)
        except Exception as e:
            logging.error(f"Ошибка при проверке подписки: {e}")

        # Пользователь не подписан
        text_msg = "⚠️ <b>Доступ заблокирован!</b>\nДля использования бота необходимо подписаться на наш Telegram-канал."
        
        if isinstance(event, Message):
            await event.answer(text_msg, reply_markup=subscription_keyboard(), parse_mode="HTML")
        elif isinstance(event, CallbackQuery):
            await event.message.answer(text_msg, reply_markup=subscription_keyboard(), parse_mode="HTML")
            await event.answer()

        return  # Блокируем дальнейшую обработку


# Регистрируем middleware
dp.message.outer_middleware(SubscriptionMiddleware())
dp.callback_query.outer_middleware(SubscriptionMiddleware())

# ==================== ОБРАБОТКА ПОДПИСКИ ====================
@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(call: CallbackQuery):
    try:
        member = await bot.get_chat_member(chat_id="@adteoamdkmMAX", user_id=call.from_user.id)
        if member.status in ["member", "administrator", "creator"]:
            await call.message.edit_text(
                "✅ Подписка успешно подтверждена! Добро пожаловать в главное меню:",
                reply_markup=user_menu()
            )
            await call.answer("Спасибо за подписку!")
        else:
            await call.answer("❌ Вы всё еще не подписались на канал!", show_alert=True)
    except Exception:
        await call.answer("⚠️ Ошибка проверки. Убедитесь, что бот добавлен администратором в канал.", show_alert=True)

# ==================== СТАРТ И ОСНОВНОЕ МЕНЮ ====================
@dp.message(CommandStart())
async def start_cmd(message: Message):
    create_user(message.from_user.id)
    await message.answer(
        "🚀 <b>MaxRentik Приветствует!</b> активирован\n\nВыберите действие в меню ниже:",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "main")
async def process_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "🚀 <b>MaxRentik Приветствует!</b> активирован\n\nВыберите действие в меню ниже:",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )
    await call.answer()

# ==================== ПРОФИЛЬ ====================
@dp.callback_query(F.data == "profile")
async def process_profile(call: CallbackQuery):
    user = get_user(call.from_user.id)
    if not user:
        create_user(call.from_user.id)
        user = get_user(call.from_user.id)
        
    balance = user[2]
    total_earned = user[3]
    
    await call.message.edit_text(
        f"👤 <b>Ваш профиль & Статистика</b>\n\n"
        f"🆔 Ваш Telegram ID: <code>{call.from_user.id}</code>\n"
        f"💰 Доступно к выводу: <b>{balance} USDT</b>\n"
        f"📈 Заработано за всё время: <b>{total_earned} USDT</b>\n\n"
        f"<i>Статистика обновляется автоматически и хранится вечно.</i>",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )
    await call.answer()

# ==================== СОЗДАНИЕ ЗАЯВОК ====================
@dp.callback_query(F.data == "max")
async def process_max(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "📦 Вы выбрали сдачу MAX.\nПожалуйста, введите ваш номер телефона/счета MAX:",
        reply_markup=back_to_main()
    )
    await state.set_state(TicketStates.waiting_phone)

@dp.callback_query(F.data == "card")
async def process_card(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "💳 Вы выбрали сдачу карты.\nПожалуйста, введите реквизиты вашей карты:",
        reply_markup=back_to_main()
    )
    await state.set_state(TicketStates.waiting_card)

@dp.message(TicketStates.waiting_phone, F.text)
async def process_phone_input(message: Message, state: FSMContext):
    phone = message.text.strip()
    ticket_id = create_ticket(message.from_user.id, "MAX", data=f"Телефон/Счет: {phone}")
    await state.clear()
    
    await message.answer(
        f"✅ Заявка #{ticket_id} на сдачу MAX успешно создана!\nОжидайте проверки администратором.",
        reply_markup=user_menu()
    )
    
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>Новая заявка #{ticket_id} (MAX)</b>\nПользователь: <code>{message.from_user.id}</code>\nДанные: {phone}",
        reply_markup=admin_ticket_keyboard(ticket_id, "MAX"),
        parse_mode="HTML"
    )

@dp.message(TicketStates.waiting_card, F.text)
async def process_card_input(message: Message, state: FSMContext):
    card_details = message.text.strip()
    ticket_id = create_ticket(message.from_user.id, "CARD", data=f"Реквизиты: {card_details}")
    await state.clear()
    
    await message.answer(
        f"✅ Заявка #{ticket_id} на сдачу карты успешно создана!\nОжидайте проверки администратором.",
        reply_markup=user_menu()
    )
    
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>Новая заявка #{ticket_id} (CARD)</b>\nПользователь: <code>{message.from_user.id}</code>\nДанные: {card_details}",
        reply_markup=admin_ticket_keyboard(ticket_id, "CARD"),
        parse_mode="HTML"
    )

# ==================== ВЫВОД СРЕДСТВ ====================
@dp.callback_query(F.data == "withdraw")
async def process_withdraw(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(call.from_user.id)
    balance = user[2] if user else 0.0
    
    if balance <= 0:
        await call.answer("❌ У вас нет доступных средств для вывода!", show_alert=True)
        return
        
    await call.message.edit_text(
        f"💰 Ваш текущий баланс: {balance} USDT.\n"
        f"Введите сумму, которую вы хотите вывести:",
        reply_markup=back_to_main()
    )
    await state.set_state(TicketStates.waiting_withdraw_amount)

@dp.message(TicketStates.waiting_withdraw_amount, F.text)
async def process_withdraw_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректное число.")
        return
        
    user = get_user(message.from_user.id)
    balance = user[2] if user else 0.0
    
    if amount <= 0:
        await message.answer("⚠️ Сумма должна быть больше нуля.")
        return
        
    if amount > balance:
        await message.answer(f"⚠️ Недостаточно средств. Ваш баланс: {balance} USDT.")
        return
        
    update_user_balance(message.from_user.id, -amount)
    ticket_id = create_ticket(message.from_user.id, "WITHDRAW", data=f"Вывод {amount} USDT")
    await state.clear()
    
    await message.answer(
        f"✅ Заявка на вывод #{ticket_id} на сумму {amount} USDT успешно создана!\nОжидайте проведения выплаты.",
        reply_markup=user_menu()
    )
    
    await bot.send_message(
        ADMIN_ID,
        f"💰 <b>Заявка на вывод #{ticket_id}</b>\nПользователь: <code>{message.from_user.id}</code>\nСумма: {amount} USDT",
        reply_markup=admin_ticket_keyboard(ticket_id, "WITHDRAW"),
        parse_mode="HTML"
    )

# ==================== АДМИН ФУНКЦИИ ====================
@dp.callback_query(F.data.startswith("take:"))
async def take_callback(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    assign_ticket(tid, call.from_user.id)
    t = get_ticket(tid)
    if t:
        await bot.send_message(t[1], f"🟡 Ваша заявка #{tid} взята в работу администратором. Ожидайте.")
        await call.answer("✅ Взято в работу")

@dp.callback_query(F.data.startswith("ask_code:"))
async def ask_code_callback(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    
    if not t:
        await call.answer("Заявка не найдена.", show_alert=True)
        return
        
    user_id = t[1]
    
    try:
        user_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
        await dp.fsm.storage.set_state(bot=bot, context=user_key, state=TicketStates.waiting_for_code)
        await dp.fsm.storage.set_data(bot=bot, context=user_key, data={"ask_code_ticket_id": tid})
        
        await bot.send_message(
            user_id,
            f"💬 <b>Внимание!</b> Администратор запросил шестизначный код подтверждения для вашей заявки #{tid}.\n"
            f"Пожалуйста, отправьте шестизначный код ответным сообщением сюда.",
            parse_mode="HTML"
        )
        await call.answer("Запрос кода успешно отправлен пользователю!", show_alert=True)
    except Exception as e:
        await call.answer(f"Не удалось отправить запрос: {e}", show_alert=True)

@dp.message(TicketStates.waiting_for_code, F.text)
async def user_code_input_handler(message: Message, state: FSMContext):
    code = message.text.strip()
    
    if not (code.isdigit() and len(code) == 6):
        await message.answer("⚠️ Пожалуйста, введите корректный шестизначный цифровой код.")
        return
        
    state_data = await state.get_data()
    tid = state_data.get("ask_code_ticket_id")
    
    if tid:
        t = get_ticket(tid)
        current_info = t[4] if t and t[4] else ""
        updated_info = f"{current_info} | Код подтверждения: {code}".strip(" | ")
        update_ticket_data(tid, updated_info)
        
        await bot.send_message(
            ADMIN_ID,
            f"📥 <b>Получен код подтверждения!</b>\n"
            f"Заявка: #{tid} ({t[2]})\n"
            f"Пользователь: <code>{message.from_user.id}</code>\n"
            f"Код: <code>{code}</code>",
            parse_mode="HTML"
        )
        
        await message.answer("✅ Код успешно отправлен администратору. Ожидайте подтверждения заявки.")
        await state.clear()
    else:
        await message.answer("❌ Заявка устарела или не найдена.")
        await state.clear()

@dp.callback_query(F.data.startswith("done:"))
async def done_callback(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    
    if not t or t[3] in ['done', 'rejected']:
        await call.answer("Заявка уже обработана или не найдена.", show_alert=True)
        return
        
    payout = 0.0
    if t[2] == "MAX":
        payout = MAX_PRICE
    elif t[2] == "CARD":
        payout = CARD_PRICE
        
    complete_ticket(tid, payout)
    
    if t[2] == "WITHDRAW":
        await bot.send_message(t[1], f"✅ Ваша заявка на вывод #{tid} успешно выполнена! Чек отправлен.")
    else:
        await bot.send_message(t[1], f"✅ Заявка #{tid} ({t[2]}) успешно одобрена! Баланс пополнен на {payout} USDT.")
        
    await call.message.edit_text(f"✅ Заявка #{tid} успешно завершена.")
    await call.answer("Выполнено!")

@dp.callback_query(F.data.startswith("admin_cancel:"))
async def admin_reject_ticket_callback(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    
    if not t or t[3] in ['done', 'rejected']:
        await call.answer("Нельзя изменить статус этой заявки!", show_alert=True)
        return
        
    if t[2] == "WITHDRAW":
        try:
            amount_str = t[4].replace("Вывод ", "").replace(" USDT", "").strip()
            amount = float(amount_str)
            update_user_balance(t[1], amount)
        except Exception:
            pass

    reject_ticket_db(tid)
    await bot.send_message(t[1], f"❌ Ваша заявка #{tid} ({t[2]}) была отклонена администратором.")
    await call.message.edit_text(f"❌ Заявка #{tid} успешно отклонена администратором.")
    await call.answer("❌ Заявка отклонена")

@dp.message(F.from_user.id == ADMIN_ID, Command("payouts", "admin"))
async def admin_payouts_stats(message: Message):
    stats = get_all_users_stat()
    if not stats:
        await message.answer("📭 База данных пользователей пуста.")
        return
        
    report = "📊 <b>Вечная статистика выплат и балансов:</b>\n\n"
    report += f"Всего пользователей в системе: {len(stats)}\n"
    report += "-----------------------------------------\n"
    
    for row in stats:
        tg_id, balance, total_earned = row
        report += f"👤 Юзер ID: <code>{tg_id}</code>\n"
        report += f"💰 Доступно к выплате (Баланс): <b>{balance} USDT</b>\n"
        report += f"📈 Заработано за всё время: <b>{total_earned} USDT</b>\n"
        report += "-----------------------------------------\n"
        
    if len(report) > 4096:
        for x in range(0, len(report), 4096):
            await message.answer(report[x:x+4096], parse_mode="HTML")
    else:
        await message.answer(report, parse_mode="HTML")

# ==================== ЗАПУСК БОТА ====================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())