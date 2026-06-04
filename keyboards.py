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
    buttons = [
        [InlineKeyboardButton(text="🟡 Взять в работу", callback_data=f"take:{ticket_id}")]
    ]
    
    # Для заявок типа MAX выводим кнопку запроса кода подтверждения
    if ticket_type == "MAX":
        buttons.append([InlineKeyboardButton(text="💬 Запросить код", callback_data=f"ask_code:{ticket_id}")])
        
    buttons.append([InlineKeyboardButton(text="✅ Подтвердить и начислить", callback_data=f"done:{ticket_id}")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"admin_cancel:{ticket_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)