# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/adteoamdkmMAX")],
        [InlineKeyboardButton(text="🔄 Проверить подписку", callback_data="check_subscription")]
    ])

def user_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Сдать MAX", callback_data="max")],
        [InlineKeyboardButton(text="💳 Сдать карту", callback_data="card")],
        [InlineKeyboardButton(text="👤 Профиль & Статистика", callback_data="profile")]
    ])

def profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Вывод средств", callback_data="withdraw")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="profile")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="main")]
    ])

def back_to_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="main")]
    ])

def admin_ticket_keyboard(ticket_id: int, ticket_type: str):
    buttons = []
    if ticket_type == "MAX":
        buttons.append([InlineKeyboardButton(text="💬 Запросить код", callback_data=f"ask_code:{ticket_id}")])
    buttons.append([InlineKeyboardButton(text="✅ Подтвердить и начислить", callback_data=f"done:{ticket_id}")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"admin_cancel:{ticket_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_withdraw_keyboard(ticket_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid:{ticket_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_cancel:{ticket_id}")]
    ])

def withdraw_amounts_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5 USDT", callback_data="wamt:5"),
         InlineKeyboardButton(text="10 USDT", callback_data="wamt:10")],
        [InlineKeyboardButton(text="25 USDT", callback_data="wamt:25"),
         InlineKeyboardButton(text="50 USDT", callback_data="wamt:50")],
        [InlineKeyboardButton(text="Другая сумма", callback_data="wamt:custom")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="main")]
    ])