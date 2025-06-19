import asyncio
import logging
import json
import sys
from datetime import datetime, timedelta
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
ALERT_API = "https://alerts.com.ua/api/states"
CITY_NAME = "м. Київ"
LOG_FILE = "log.txt"
REPORT_FILE = "log_report.txt"
SHIFT_FILE = "shift_data.json"
DEBUG_OVERRIDE_ALERT = 0  # 1 означає що для бота тривога є завжди, це для тесту. 0 - тривога визначається через апі.

logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
logger.propagate = False

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Зберігає user_id і час запиту на завершення зміни
CONFIRMATION_WAITING = {}


# Генерує клавіатуру з кнопками
def get_main_keyboard():
    buttons = [
        [
            KeyboardButton(text='Початок зміни'),
            KeyboardButton(text='Я в бомбосховищі'),
            KeyboardButton(text='Вже працюю'),
        ],
        [
            KeyboardButton(text='Кінець зміни'),
            KeyboardButton(text='Перевірити чи є тривога в Києві???'),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


SHIFT_DATA = {}


# Завантажує shift_data.json у оперативну памʼять
def load_shift_data():
    global SHIFT_DATA
    try:
        with open(SHIFT_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            for uid, data in raw.items():
                data["shift_start"] = datetime.fromisoformat(data["shift_start"])
                for rec in data["records"]:
                    rec["in"] = datetime.fromisoformat(rec["in"])
                    if "out" in rec:
                        rec["out"] = datetime.fromisoformat(rec["out"])
            SHIFT_DATA = {int(k): v for k, v in raw.items()}
    except FileNotFoundError:
        SHIFT_DATA = {}


# Зберігає SHIFT_DATA назад у файл
def save_shift_data():
    to_dump = {}
    for uid, data in SHIFT_DATA.items():
        records = []
        for rec in data["records"]:
            r = {"in": rec["in"].isoformat()}
            if "out" in rec:
                r["out"] = rec["out"].isoformat()
            records.append(r)
        to_dump[uid] = {
            "username": data["username"],
            "shift_start": data["shift_start"].isoformat(),
            "records": records,
        }
    with open(SHIFT_FILE, "w", encoding="utf-8") as f:
        json.dump(to_dump, f, ensure_ascii=False, indent=2)


# Повертає True якщо тривога активна або DEBUG увімкнено
async def is_alert_active_in_kyiv():
    if DEBUG_OVERRIDE_ALERT:
        return True
    try:
        data = requests.get(ALERT_API, timeout=5).json()
        for region in data.get("states", []):
            if region.get("name") == CITY_NAME:
                return region.get("alert", False)
    except Exception:
        return False
    return False


# Реальна перевірка тривоги (без DEBUG)
async def get_real_alert_status():
    try:
        data = requests.get(ALERT_API, timeout=5).json()
        for region in data.get("states", []):
            if region.get("name") == CITY_NAME:
                return region.get("alert", False)
    except Exception:
        return False
    return False


# Записує дію користувача в лог
def log_action(username, action, timestamp, delta=None):
    line = f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} — {username} — {action}"
    if delta:
        line += f" — stop-time: {delta}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# Запис повідомлення юзера в лог
def log_message(username, message):
    now = datetime.now().replace(microsecond=0)
    entry = f"{now.strftime('%Y-%m-%d %H:%M:%S')} — @{username}: {message}"
    logger.info(entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


# Запис відповіді бота в лог
def log_bot_response(username, response):
    now = datetime.now().replace(microsecond=0)
    line = f"{now.strftime('%Y-%m-%d %H:%M:%S')} — BOT to @{username}: {response}"
    logger.info(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# Відправляє повідомлення з клавіатурою і логом
async def send_with_keyboard(message, text):
    await message.answer(text, reply_markup=get_main_keyboard())
    log_bot_response(message.from_user.username or f"id_{message.from_user.id}", text)


# Якщо не введено "123" — скасовує завершення
async def confirmation_timeout(user_id, message):
    await asyncio.sleep(7)
    if user_id in CONFIRMATION_WAITING:
        del CONFIRMATION_WAITING[user_id]
        await send_with_keyboard(message, "⌛ Завершення зміни скасовано через неактивність (не введено 123).")


@dp.message(lambda message: message.text == '/start')
async def cmd_start(message):
    await send_with_keyboard(message, "👋 Вітаю! Оберіть дію:")


@dp.message()
async def handle_main(message):
    user = message.from_user
    now = datetime.now().replace(microsecond=0)
    username = user.username or f"id_{user.id}"
    log_message(username, message.text)

    user_data = SHIFT_DATA.get(user.id)
    shift_info = f"\nЗміна активна з {user_data['shift_start'].strftime('%Y-%m-%d %H:%M:%S')}" if user_data else "\nЗміна не активна"

    if user.id in CONFIRMATION_WAITING:
        if message.text == "123":
            shift_start = user_data['shift_start']
            summary = f"📊 Звіт зміни {username}  |  З {shift_start.strftime('%Y-%m-%d %H:%M:%S')}  |  до {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            total_minutes = 0
            for rec in user_data["records"]:
                if "in" in rec and "out" in rec:
                    delta = rec["out"] - rec["in"]
                    minutes = round(delta.total_seconds() / 60)
                    total_minutes += minutes
                    summary += f"• {rec['in'].strftime('%H:%M:%S')} → {rec['out'].strftime('%H:%M:%S')} = {minutes} хв\n"
            summary += f"⏱️ Загальний stop-time: {total_minutes} хв"
            with open(REPORT_FILE, "a", encoding="utf-8") as f:
                f.write(summary + "\n\n")
            await send_with_keyboard(message, summary)
            log_action(username, "кінець зміни", now, f"{total_minutes} хв")
            del SHIFT_DATA[user.id]
            save_shift_data()
            del CONFIRMATION_WAITING[user.id]
            return
        else:
            del CONFIRMATION_WAITING[user.id]
            await send_with_keyboard(message, "❌ Завершення зміни скасовано через іншу дію.")

    if message.text == "Початок зміни":
        if user.id in SHIFT_DATA:
            await send_with_keyboard(message, f"⚠️ Зміна вже активна з {user_data['shift_start'].strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            SHIFT_DATA[user.id] = {"username": username, "shift_start": now, "records": []}
            log_action(username, "початок зміни", now)
            save_shift_data()
            await send_with_keyboard(message, f"✅ Початок зміни зафіксовано: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    elif message.text == "Я в бомбосховищі":
        if not user_data:
            await send_with_keyboard(message, "⚠️ Спочатку почніть зміну.")
            return
        if await is_alert_active_in_kyiv():
            records = user_data["records"]
            if records and "out" not in records[-1]:
                await send_with_keyboard(message, "🛑 Ви вже зареєстровані як присутні в бомбосховищі." + shift_info)
            else:
                records.append({"in": now})
                log_action(username, "в бомбосховищі", now)
                save_shift_data()
                await send_with_keyboard(message, f"📍 {now.strftime('%Y-%m-%d %H:%M:%S')} — Зараховано: ви в бомбосховищі" + shift_info)
        else:
            await send_with_keyboard(message, f"❌ {now.strftime('%Y-%m-%d %H:%M:%S')} — Тривоги немає, не зараховано." + shift_info)

    elif message.text == "Вже працюю":
        if not user_data:
            await send_with_keyboard(message, "⚠️ Спочатку почніть зміну.")
            return
        records = user_data["records"]
        if records and "in" in records[-1] and "out" not in records[-1]:
            records[-1]["out"] = now
            delta = now - records[-1]["in"]
            minutes = round(delta.total_seconds() / 60)
            log_action(username, "вже працюю", now, f"{minutes} хв")
            save_shift_data()
            await send_with_keyboard(message, f"🛠️ {now.strftime('%Y-%m-%d %H:%M:%S')} — Зараховано: ви працюєте. ⏱️ Stop-time: {minutes} хв" + shift_info)
        else:
            await send_with_keyboard(message, f"❌ {now.strftime('%Y-%m-%d %H:%M:%S')} — Ви не зареєстровані як присутні в бомбосховищі. Не зараховано." + shift_info)

    elif message.text == "Кінець зміни":
        if not user_data:
            await send_with_keyboard(message, "⚠️ Зміна не була активна.")
            return
        CONFIRMATION_WAITING[user.id] = now
        await send_with_keyboard(message, "⚠️ Для завершення зміни введіть 123 протягом 7 секунд. Це захист від випадкового завершення.")
        asyncio.create_task(confirmation_timeout(user.id, message))

    elif message.text == "Перевірити чи є тривога в Києві???":
        real_alert = await get_real_alert_status()
        if real_alert:
            await send_with_keyboard(message, "🚨🚨🚨 Увага! В м.Київ оголошено тривогу.")
        else:
            await send_with_keyboard(message, "✅ В м.Київ тривоги немає.")


async def main():
    load_shift_data()
    logger.info("Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())