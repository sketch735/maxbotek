from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def user_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Сдать MAX", callback_data="max")],
        [InlineKeyboardButton(text="💳 Сдать карту", callback_data="card")],
        [InlineKeyboardButton(text="📊 Мои заявки", callback_data="my")]
    ])


def admin_ticket(ticket_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟡 Взять в работу", callback_data=f"take:{ticket_id}")],
        [InlineKeyboardButton(text="💬 Чат", callback_data=f"chat:{ticket_id}")],
        [InlineKeyboardButton(text="✅ Закрыть", callback_data=f"done:{ticket_id}")]
    ])