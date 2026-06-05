# services.py
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")

async def create_invoice(amount: float, description: str = ""):
    if not CRYPTOBOT_TOKEN:
        raise ValueError("CRYPTOBOT_TOKEN не найден в .env")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN},
            json={
                "asset": "USDT",
                "amount": str(amount),
                "description": description,
                "paid_btn_name": "openBot",
                "paid_btn_url": "https://t.me/yourbot"
            }
        ) as resp:
            return await resp.json()