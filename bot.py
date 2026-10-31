import asyncio
import html
import json
import logging
import os
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from aiohttp import web

logging.basicConfig(level=logging.INFO)

raw_token = os.environ.get("BOT_TOKEN", "")
BOT_TOKEN = raw_token.strip().strip('"').strip("'")

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    logging.error("ОШИБКА: BOT_TOKEN не задан в Environment на Render!")
    sys.exit(1)

ADMIN_ID = 6189216877
ADMIN_USERNAME = "uj_92"
WEB_APP_URL = "https://uj-92-shop.github.io/uj92-shop/"
PROMOS_FILE = "promos.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def load_promos():
    if os.path.exists(PROMOS_FILE):
        try:
            with open(PROMOS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [p for p in data if p.get("code") != "START15"]
        except Exception as e:
            logging.warning(f"Ошибка чтения promos.json: {e}")
    return []


def save_promos(promos_list):
    try:
        with open(PROMOS_FILE, "w", encoding="utf-8") as f:
            json.dump(promos_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"Ошибка записи promos.json: {e}")


PROMOS_DB = load_promos()


@dp.message(CommandStart())
async def start_handler(message: types.Message):
    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚡ Запустить приложение",
                    web_app=WebAppInfo(url=WEB_APP_URL),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐ Отзывы", url="https://t.me/uj_92_rew"
                ),
                InlineKeyboardButton(
                    text="💬 Поддержка @uj_92",
                    url=f"https://t.me/{ADMIN_USERNAME}",
                ),
            ],
        ]
    )

    first_name = html.escape(message.from_user.first_name or "клиент")
    text = (
        f"👋 Привет, <b>{first_name}</b>!\n\n"
        f"Добро пожаловать в <b>UJ92_shop</b> — магазин номеров и кейсов с подарками Telegram.\n"
        f"• Пополняйте баланс в GRAM или USDT (TON)\n"
        f"• Открывайте кейсы и собирайте подарки в инвентарь\n"
        f"• Покупайте номера с мгновенным отслеживанием статуса\n\n"
        f"Поддержка: @{ADMIN_USERNAME}"
    )

    await message.answer(
        text, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML"
    )
    await message.answer(
        "Нажмите кнопку ниже для входа:", reply_markup=inline_kb
    )


async def handle_api_promos(request):
    global PROMOS_DB
    if request.method == "OPTIONS":
        return web.Response(status=200, headers=CORS_HEADERS)

    if request.method == "GET":
        return web.json_response(
            {"ok": True, "promos": PROMOS_DB}, headers=CORS_HEADERS
        )

    try:
        body = await request.json()
        action = body.get("action")

        if action == "upsert":
            code = str(body.get("code", "")).strip().upper()
            discount = int(body.get("discount", 0))
            limit_per_user = int(body.get("limitPerUser", 1))
            status = str(body.get("status", "active"))

            if code and code != "START15" and discount > 0:
                existing = next(
                    (p for p in PROMOS_DB if p["code"] == code), None
                )
                if existing:
                    existing["discount"] = discount
                    existing["limitPerUser"] = limit_per_user
                    existing["status"] = status
                else:
                    PROMOS_DB.append(
                        {
                            "code": code,
                            "discount": discount,
                            "limitPerUser": limit_per_user,
                            "status": status,
                            "usedUsers": body.get("usedUsers", {}),
                        }
                    )
                save_promos(PROMOS_DB)

        elif action == "delete":
            code = str(body.get("code", "")).strip().upper()
            PROMOS_DB = [p for p in PROMOS_DB if p["code"] != code]
            save_promos(PROMOS_DB)

        elif action == "use":
            code = str(body.get("code", "")).strip().upper()
            user_key = str(body.get("userKey", "")).strip().lower()
            existing = next((p for p in PROMOS_DB if p["code"] == code), None)
            if existing and user_key:
                used_map = existing.setdefault("usedUsers", {})
                used_map[user_key] = used_map.get(user_key, 0) + 1
                save_promos(PROMOS_DB)

        return web.json_response(
            {"ok": True, "promos": PROMOS_DB}, headers=CORS_HEADERS
        )
    except Exception as e:
        logging.error(f"Ошибка в /promos: {e}")
        return web.json_response(
            {"ok": False, "error": str(e)}, status=500, headers=CORS_HEADERS
        )


async def handle_api_notify(request):
    if request.method == "OPTIONS":
        return web.Response(status=200, headers=CORS_HEADERS)

    try:
        body = await request.json()
        order = body.get("order", {})
        user = body.get("user", {})
        event_type = body.get("eventType", "created")

        order_id = html.escape(str(order.get("id", "UJ92")))
        order_type = order.get("orderType", "phone")
        currency = html.escape(str(order.get("currency", "GRAM")))
        crypto_amt = html.escape(str(order.get("cryptoAmount", "0")))
        usd_amt = html.escape(str(order.get("usdAmount", "0")))
        promo = html.escape(str(order.get("promo", "Нет")))
        items = order.get("items", [])

        user_id = user.get("id", 0)
        user_name = html.escape(str(user.get("name", "Клиент")))
        user_tag = html.escape(str(user.get("username", "@guest")))

        items_str = "\n".join(
            [
                f"• {i.get('flag', '')} {i.get('country', '')} ({i.get('code', '')}) × {i.get('qty', 1)} шт."
                for i in items
            ]
        )

        if order_type == "gift_withdraw":
            admin_text = (
                f"🎁 <b>ЗАЯВКА НА ВЫВОД ИЗ ИНВЕНТАРЯ!</b>\n\n"
                f"• Код: <code>{order_id}</code>\n"
                f"• Покупатель: {user_name} ({user_tag}, ID: <code>{user_id}</code>)\n"
                f"• Предмет:\n{items_str}\n\n"
                f"<b>Выдайте предмет пользователю!</b>"
            )
            buyer_text = (
                f"🎁 <b>Заявка № {order_id} на вывод создана!</b>\n\n"
                f"{items_str}\n\n"
                f"Администратор @{ADMIN_USERNAME} свяжется с вами для выдачи."
            )
        elif order_type == "deposit":
            if event_type == "paid":
                admin_text = (
                    f"💰 <b>ПОПОЛНЕНИЕ ПОДТВЕРЖДЕНО!</b>\n\n"
                    f"• Счёт: <code>{order_id}</code>\n"
                    f"• Клиент: {user_name} ({user_tag}, ID: <code>{user_id}</code>)\n"
                    f"• Сумма: <b>${usd_amt} ({crypto_amt} {currency})</b>"
                )
                buyer_text = (
                    f"✅ <b>Баланс успешно пополнен на ${usd_amt}!</b>\n"
                    f"Счёт № <code>{order_id}</code> подтверждён в блокчейне TON."
                )
            else:
                admin_text = (
                    f"💳 <b>СЧЁТ НА ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n"
                    f"• Счёт: <code>{order_id}</code>\n"
                    f"• Клиент: {user_name} ({user_tag}, ID: <code>{user_id}</code>)\n"
                    f"• Сумма: <b>{crypto_amt} {currency} (${usd_amt})</b>"
                )
                buyer_text = (
                    f"🧾 <b>Счёт № {order_id} на пополнение (${usd_amt}) создан!</b>\n\n"
                    f"• К оплате: <b>{crypto_amt} {currency}</b>\n"
                    f"• Комментарий: <code>{order_id}</code>\n\n"
                    f"Подтвердите оплату в Tonkeeper. Поддержка: @{ADMIN_USERNAME}"
                )
        else:
            if event_type == "paid":
                admin_text = (
                    f"💰 <b>ЗАКАЗ ОПЛАЧЕН!</b>\n\n"
                    f"• Заказ: <code>{order_id}</code>\n"
                    f"• Покупатель: {user_name} ({user_tag}, ID: <code>{user_id}</code>)\n"
                    f"• Сумма: <b>{crypto_amt} {currency} (${usd_amt})</b>\n"
                    f"• Промокод: {promo}\n"
                    f"• Товары:\n{items_str}\n\n"
                    f"✅ <b>Выдайте покупателю номер!</b>"
                )
                buyer_text = (
                    f"✅ <b>Оплата по заказу № {order_id} подтверждена!</b>\n\n"
                    f"• Сумма: <b>{crypto_amt} {currency} (${usd_amt})</b>\n"
                    f"• Товары:\n{items_str}\n\n"
                    f"Администратор @{ADMIN_USERNAME} сейчас выдаст вам номер."
                )
            else:
                admin_text = (
                    f"🚨 <b>НОВЫЙ ЗАКАЗ В UJ92_SHOP!</b>\n\n"
                    f"• Заказ: <code>{order_id}</code>\n"
                    f"• Покупатель: {user_name} ({user_tag}, ID: <code>{user_id}</code>)\n"
                    f"• Счёт: <b>{crypto_amt} {currency} (${usd_amt})</b>\n"
                    f"• Промокод: {promo}\n"
                    f"• Товары:\n{items_str}\n"
                    f"• Комментарий: <code>{order_id}</code>"
                )
                buyer_text = (
                    f"🧾 <b>Заказ № {order_id} создан!</b>\n\n"
                    f"<b>Состав заказа:</b>\n{items_str}\n\n"
                    f"• <b>Сумма счёта:</b> {crypto_amt} {currency} (${usd_amt})\n"
                    f"• <b>Комментарий:</b> <code>{order_id}</code>\n\n"
                    f"Подтвердите счёт в кошельке. Поддержка: @{ADMIN_USERNAME}"
                )

        buyer_url = (
            f"https://t.me/{user_tag[1:]}"
            if user_tag.startswith("@")
            else f"tg://user?id={user_id}"
        )
        admin_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Написать покупателю", url=buyer_url
                    )
                ]
            ]
        )
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            parse_mode="HTML",
            reply_markup=admin_kb,
        )

        if user_id and int(user_id) != 0:
            buyer_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💬 Поддержка @uj_92",
                            url=f"https://t.me/{ADMIN_USERNAME}",
                        )
                    ]
                ]
            )
            await bot.send_message(
                chat_id=int(user_id),
                text=buyer_text,
                parse_mode="HTML",
                reply_markup=buyer_kb,
            )

        return web.json_response({"ok": True}, headers=CORS_HEADERS)
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления: {e}")
        return web.json_response(
            {"ok": False, "error": str(e)}, status=500, headers=CORS_HEADERS
        )


async def handle_ping(request):
    return web.Response(text="UJ92 Shop Bot is alive!", headers=CORS_HEADERS)


async def main():
    port = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_route("OPTIONS", "/notify", handle_api_notify)
    app.router.add_post("/notify", handle_api_notify)
    app.router.add_route("OPTIONS", "/promos", handle_api_promos)
    app.router.add_get("/promos", handle_api_promos)
    app.router.add_post("/promos", handle_api_promos)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Веб-порт {port} успешно открыт.")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
