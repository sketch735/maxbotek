import aiohttp
import os

CRYPTOBOT_TOKEN = os.getenv("532005:AA78QRhZPpW82lSyFOggX4PQD8uhkV8zxU1")

LIMITS = {
    "free": 5,
    "pro": 50,
    "premium": 200
}


def check_limit(user):
    if not user:
        return False
    tariff = user[1]
    requests = user[2]
    return requests < LIMITS.get(tariff, 5)


async def create_invoice(amount):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN},
            json={"asset": "USDT", "amount": amount}
        ) as r:
            return await r.json()