# FILE: services.py

def ticket_type_text(t):
    if t == "MAX":
        return "📦 MAX"
    if t == "CARD":
        return "💳 CARD"
    return "❓ UNKNOWN"