from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def user_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Сдать MAX", callback_data="max")],
        [InlineKeyboardButton(text="💳 Сдать карту", callback_data="card")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")]
    ])

def profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Вывод", callback_data="withdraw")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="profile")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main")]
    ])

def cancel_keyboard(ticket_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"cancel:{ticket_id}")]
    ])

def admin_ticket_keyboard(ticket_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟡 Взять в работу", callback_data=f"take:{ticket_id}")],
        [InlineKeyboardButton(text="✅ Завершить", callback_data=f"done:{ticket_id}")],
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"admin_cancel:{ticket_id}")]
    ])