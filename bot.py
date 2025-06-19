import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


TOKEN = '7907057772:AAGAZd0BcYeRT6jvsCpOKsjVvalu3SS-Uco'
bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.WARNING)


inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='Надіслати повідомлення', callback_data='send_message')],
        [InlineKeyboardButton(text='Показати водіїв', callback_data='show_drivers')],
        [InlineKeyboardButton(text='Показати пасажирів', callback_data='show_passengers')]
    ],
)


@dp.message(lambda message: message.text == '/start')
async def cmd_start(message: Message):
    logging.info(f"User {message.from_user.id} started the bot.")
    await message.answer("Це безкоштовний бот Одеса - Південне та Південне - Одеса:", reply_markup=inline_keyboard)

 
@dp.message()
async def handle_message(message: Message):
    if len(message.text.split('\n')) == 7:
        lines = message.text.split("\n")
        role = lines[0]
        route = lines[1]
        time = lines[2]
        price = lines[3]
        phone = lines[4]
        seats = lines[5]
        conditions = lines[6]
    else:
        f"Для того щоб система могла відсортувати й відобразити повідомлення, воно має бути в такому форматі й складатися з 7 рядків:"

    logging.info(f"{message.from_user.username}, {message.from_user.id}: {message.text}")

    response = message.text
    '''response = (
        f"📌 **{role}**\n"
        f"📍 Звідки - Куди: {route}\n"
        f"🕒 Час: {time}\n"
        f"💰 Ціна: {price}\n"
        f"📞 Телефон: {phone}"
        f"🪑 Кількість вільних місць: {seats}\n"
        f"⚠ Максимальна кількість пасажирів позаду (2 або 3): {conditions}\n"
    )'''

    await message.answer(response)


@dp.message(lambda message: message.text == 'Показати актуальних водіїв')
async def show_drivers(message: Message):
    logging.info(f"User {message.from_user.id} requested drivers list.")
    await message.answer("Тут будуть актуальні водії.")


@dp.message(lambda message: message.text == 'Показати актуальних пасажирів')
async def show_passengers(message: Message):
    logging.info(f"User {message.from_user.id} requested passengers list.")
    await message.answer("Тут будуть актуальні пасажири.")


async def main():
    logging.info("Bot is starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    print('The bot is running!')
    asyncio.run(main())
