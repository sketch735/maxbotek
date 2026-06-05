# bot.py
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

from db import (
    create_user, get_user, update_user_balance, create_ticket,
    get_ticket, reject_ticket_db, get_pending_withdrawals,
    increment_max_submitted, increment_cards_submitted,
    set_subscribed, is_subscribed, complete_ticket
)
from keyboards import (
    user_menu, admin_ticket_keyboard, profile_keyboard,
    back_to_main, subscription_keyboard, admin_withdraw_keyboard,
    withdraw_amounts_keyboard, admin_code_received_keyboard
)
from services import create_invoice

logging.basicConfig(level=logging.INFO)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")

# Настройка списка администраторов с поддержкой строки через запятую и fallback-значений
ADMIN_IDS = []
admin_ids_env = os.getenv("ADMIN_IDS")
if admin_ids_env:
    try:
        ADMIN_IDS = [int(x.strip()) for x in admin_ids_env.split(",") if x.strip().isdigit()]
    except Exception as e:
        logging.error(f"Ошибка парсинга ADMIN_IDS: {e}")

if not ADMIN_IDS:
    # Если переменной ADMIN_IDS нет, берем ADMIN_ID и добавляем второго админа
    base_admin = os.getenv("ADMIN_ID")
    if base_admin and base_admin.isdigit():
        ADMIN_IDS.append(int(base_admin))
    # Добавляем второго администратора по умолчанию
    if 8754271991 not in ADMIN_IDS:
        ADMIN_IDS.append(8754271991)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class TicketStates(StatesGroup):
    waiting_phone = State()
    waiting_custom_withdraw = State()
    waiting_code = State()

# ==================== Middleware ====================
class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data: dict):
        user = event.from_user if hasattr(event, 'from_user') else getattr(event, 'message', None).from_user
        if not user or user.id in ADMIN_IDS:
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
            try:
                await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
            await event.answer()
        return

dp.message.outer_middleware(SubscriptionMiddleware())
dp.callback_query.outer_middleware(SubscriptionMiddleware())

# ==================== Старт ====================
@dp.message(CommandStart())
async def start_cmd(message: Message):
    create_user(message.from_user.id, message.from_user.username)
    try:
        member = await bot.get_chat_member("@adteoamdkmMAX", message.from_user.id)
        if member.status in ["member", "administrator", "creator"] or message.from_user.id in ADMIN_IDS:
            await message.answer(
                "🚀 <b>MaxRentik Приветствует!</b>\n\nВыберите действие:",
                reply_markup=user_menu(),
                parse_mode="HTML"
            )
            return
    except Exception:
        pass

    await message.answer(
        "🚀 <b>MaxRentik Приветствует!</b>\n\n"
        "Для работы с нашим ботом, подпишитесь на канал ниже.",
        reply_markup=subscription_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_subscription")
async def check_subscription(call: CallbackQuery):
    await call.answer()
    try:
        member = await bot.get_chat_member("@adteoamdkmMAX", call.from_user.id)
        if member.status in ["member", "administrator", "creator"] or call.from_user.id in ADMIN_IDS:
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
    await call.answer()
    await state.clear()
    create_user(call.from_user.id, call.from_user.username)
    await call.message.edit_text(
        "🚀 <b>MaxRentik Приветствует!</b>\n\nВыберите действие:",
        reply_markup=user_menu(),
        parse_mode="HTML"
    )

# ==================== Профиль ====================
@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    await call.answer()
    create_user(call.from_user.id, call.from_user.username)
    user = get_user(call.from_user.id) or (None, None, 0.0, 0.0, 0, 0, 0, None)
    await call.message.edit_text(
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"💰 Баланс: <b>{user[2]} USDT</b>\n"
        f"📈 Всего заработано: <b>{user[3]} USDT</b>\n"
        f"📦 Сдано MAX: <b>{user[4]}</b>",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )

# ==================== Сдача MAX ====================
@dp.callback_query(F.data == "max")
async def process_max(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.edit_text("📦 Введите номер телефона РФ:", reply_markup=back_to_main())
    await state.set_state(TicketStates.waiting_phone)

@dp.message(TicketStates.waiting_phone)
async def phone_input(message: Message, state: FSMContext):
    create_user(message.from_user.id, message.from_user.username)
    ticket_id = create_ticket(message.from_user.id, "MAX", f"Телефон: {message.text}")
    await message.answer(f"✅ Заявка #{ticket_id} создана!", reply_markup=user_menu())
    
    username_str = f"@{message.from_user.username}" if message.from_user.username else "Нет"
    
    # Отправка уведомления всем администраторам из списка
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, 
                f"🆕 Новая заявка #{ticket_id} (MAX)\n"
                f"Пользователь: <code>{message.from_user.id}</code> ({username_str})\n"
                f"Данные: {message.text}",
                reply_markup=admin_ticket_keyboard(ticket_id, "MAX"), 
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
            
    await state.clear()

# ==================== Сдача КАРТЫ ====================
@dp.callback_query(F.data == "card")
async def process_card(call: CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        "💳 <b>Продажа карт</b>\n\n"
        "Для продажи карты пишите:\n"
        "@maxbetto\n\n"
        "Отправьте сообщение с предложением продажи карты",
        reply_markup=back_to_main(),
        parse_mode="HTML"
    )

# ==================== Вывод средств ====================
@dp.callback_query(F.data == "withdraw")
async def withdraw_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    user = get_user(call.from_user.id) or (None, None, 0.0, 0.0, 0, 0, 0, None)
    balance = user[2]
    if balance <= 0:
        return await call.answer("❌ Недостаточно средств!", show_alert=True)
    
    await call.message.edit_text(
        f"💰 Баланс: {balance} USDT\nВыберите сумму для вывода:", 
        reply_markup=withdraw_amounts_keyboard()
    )

@dp.callback_query(F.data.startswith("wamt:"))
async def withdraw_amount_choice(call: CallbackQuery, state: FSMContext):
    await call.answer()
    choice = call.data.split(":")[1]
    user = get_user(call.from_user.id) or (None, None, 0.0, 0.0, 0, 0, 0, None)
    balance = user[2]

    if choice == "custom":
        await call.message.edit_text("Введите сумму для вывода:", reply_markup=back_to_main())
        await state.set_state(TicketStates.waiting_custom_withdraw)
        return

    try:
        amount = float(choice)
    except ValueError:
        return

    if amount > balance:
        return await call.answer("❌ Сумма превышает ваш баланс!", show_alert=True)

    await execute_withdrawal(call.message, call.from_user.id, amount, state)

@dp.message(TicketStates.waiting_custom_withdraw)
async def withdraw_custom_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(',', '.'))
    except:
        return await message.answer("❌ Введите корректную сумму.")

    user = get_user(message.from_user.id) or (None, None, 0.0, 0.0, 0, 0, 0, None)
    if amount > user[2]:
        return await message.answer("❌ Сумма превышает баланс.")
    if amount <= 0:
        return await message.answer("❌ Сумма должна быть больше 0.")

    await execute_withdrawal(message, message.from_user.id, amount, state)

async def execute_withdrawal(message: Message, user_id: int, amount: float, state: FSMContext):
    await state.clear()
    try:
        invoice = await create_invoice(amount, f"Вывод #{user_id}")
        if invoice and invoice.get("ok"):
            invoice_url = invoice["result"]["pay_url"]
            ticket_id = create_ticket(user_id, "WITHDRAW", f"Вывод {amount} USDT", invoice_url)
            
            update_user_balance(user_id, -amount)
            
            await message.answer("✅ Заявка отправлена, ожидайте пополнения.", reply_markup=user_menu())
            
            user_info = get_user(user_id) or (None, None, 0.0, 0.0, 0, 0, 0, None)
            username_str = f"@{user_info[7]}" if user_info[7] else "Нет"
            
            # Отправка уведомления всем администраторам из списка
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"💰 <b>Заявка на вывод #{ticket_id}</b>\n"
                        f"Пользователь: <code>{user_id}</code> ({username_str})\n"
                        f"Сумма: {amount} USDT\n"
                        f"Чек: {invoice_url}",
                        reply_markup=admin_withdraw_keyboard(ticket_id),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logging.error(f"Не удалось отправить уведомление о выводе админу {admin_id}: {e}")
        else:
            logging.error(f"CryptoBot API Error: {invoice}")
            await message.answer("❌ Ошибка создания чека.")
    except Exception as e:
        logging.error(f"Invoice error: {e}", exc_info=True)
        await message.answer("❌ Ошибка создания чека.")

# ==================== Админ: Действия ====================
@dp.callback_query(F.data.startswith("done:"))
async def done_callback(call: CallbackQuery):
    await call.answer()
    if call.from_user.id not in ADMIN_IDS: return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    if not t: return await call.message.edit_text("❌ Заявка не найдена.")

    if t[3] in ['done', 'rejected']:
        return await call.message.edit_text(f"⚠️ Заявка #{tid} уже была обработана ранее.")

    if t[2] == "MAX":
        amount = 4.4
        if complete_ticket(tid, amount):
            increment_max_submitted(t[1])
            await call.message.edit_text(f"✅ Заявка #{tid} (MAX) завершена. Начислено 4.4 USDT.")
            try:
                await bot.send_message(t[1], "✅ Сделка подтверждена.\nВам начислено 4.4 USDT.")
            except Exception:
                pass

@dp.callback_query(F.data.startswith("admin_cancel:"))
async def admin_cancel(call: CallbackQuery):
    await call.answer()
    if call.from_user.id not in ADMIN_IDS: return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    if not t: return await call.message.edit_text("❌ Заявка не найдена.")
    
    if t[3] in ['done', 'rejected']:
        return await call.message.edit_text(f"⚠️ Заявка #{tid} уже была обработана ранее.")
    
    if t[2] == "WITHDRAW":
        try:
            amount = float(t[4].split()[1])
            update_user_balance(t[1], amount)
        except Exception:
            pass

    reject_ticket_db(tid)
    await call.message.edit_text(f"❌ Заявка #{tid} отклонена.")
    try:
        await bot.send_message(t[1], f"❌ Заявка #{tid} отклонена.")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("ask_code:"))
async def ask_code(call: CallbackQuery, state: FSMContext):
    await call.answer()
    if call.from_user.id not in ADMIN_IDS: return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    if not t: return await call.message.edit_text("❌ Заявка не найдена.")
    
    if t[3] in ['done', 'rejected']:
        return await call.message.edit_text(f"⚠️ Заявка #{tid} уже завершена.")

    try:
        user_state = dp.fsm.get_context(bot, chat_id=t[1], user_id=t[1])
        await user_state.set_state(TicketStates.waiting_code)
        await user_state.update_data(ticket_id=tid)
        await bot.send_message(t[1], "📨 На ваш номер MAX отправлен SMS.\nВведите 6-значный код:", reply_markup=back_to_main())
        await call.message.reply(f"📨 Запрос кода отправлен пользователю по заявке #{tid}.")
    except Exception as e:
        await call.message.reply(f"❌ Не удалось отправить запрос пользователю: {e}")

@dp.message(TicketStates.waiting_code)
async def code_input(message: Message, state: FSMContext):
    data = await state.get_data()
    tid = data.get("ticket_id")
    if tid:
        await message.answer(
            "✅ Код получен.\n"
            "Ожидайте подтверждения сделки администратором.\n"
            "После проверки данные будут подтверждены и начисление будет выполнено.",
            reply_markup=user_menu()
        )
        
        username_str = f"@{message.from_user.username}" if message.from_user.username else "Нет"
        
        # Отправка кода всем администраторам из списка
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"🔑 <b>Код по заявке #{tid} (MAX)</b>\n"
                    f"Пользователь: <code>{message.from_user.id}</code> ({username_str})\n"
                    f"Отправленный код: <code>{message.text}</code>",
                    reply_markup=admin_code_received_keyboard(tid),
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"Не удалось отправить код админу {admin_id}: {e}")
    else:
        await message.answer("❌ Произошла ошибка или сессия устарела.", reply_markup=user_menu())
    await state.clear()

@dp.message(Command("tab"))
async def tab_command(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    withdrawals = get_pending_withdrawals()
    if not withdrawals:
        return await message.answer("📭 Нет заявок на вывод.")
    kb = []
    text = "📋 <b>Заявки на выплату:</b>\n\n"
    for w in withdrawals:
        tid, uid, data, url, username = w
        username_str = f"@{username}" if username else "Нет"
        text += f"#{tid} | User: <code>{uid}</code> ({username_str})\nСумма/Данные: {data}\nЧек: {url}\n\n"
        kb.append([InlineKeyboardButton(text=f"💰 Выплатить #{tid}", callback_data=f"paid:{tid}")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML", disable_web_page_preview=True)

@dp.callback_query(F.data.startswith("paid:"))
async def paid_withdraw(call: CallbackQuery):
    await call.answer()
    if call.from_user.id not in ADMIN_IDS: return
    tid = int(call.data.split(":")[1])
    t = get_ticket(tid)
    if not t: return await call.message.edit_text("❌ Заявка не найдена.")
    
    if t[3] in ['done', 'rejected']:
        return await call.message.edit_text(f"⚠️ Выплата #{tid} уже обработана.")

    if complete_ticket(tid, 0):
        await call.message.edit_text(f"✅ Выплата #{tid} подтверждена.")
        try:
            await bot.send_message(t[1], "Ваш счёт оплачен")
        except Exception:
            pass

# Добавлен обработчик для команды /admin, запрошенной в ТЗ
@dp.message(Command("admin"))
async def admin_menu_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    
    withdrawals = get_pending_withdrawals()
    count = len(withdrawals)
    await message.answer(
        f"🛠 <b>Панель администратора</b>\n\n"
        f"Всего активных заявок на вывод: <b>{count}</b>\n"
        f"Используйте команду /tab для детального списка выплат.",
        parse_mode="HTML"
    )

# ==================== Запуск ====================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())