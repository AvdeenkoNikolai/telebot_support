import os
import asyncio
import sqlite3 as sq
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher,dispatcher
from dotenv import load_dotenv
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage import memory

load_dotenv()

starage = memory.MemoryStorage()


class States(StatesGroup):
    letter = State()



#импорт токена 
API_TOKEN: str = os.getenv("TOKEN")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=starage)

#создание бд
connection = sq.connect("db.sqlite3")
cursor = connection.cursor()
cursor.execute(
    """CREATE TABLE IF NOT EXISTS user(
        telegram_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        letter TEXT
    );""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS task(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT,
        date TEXT
    )""")
connection.commit()

#регистрация useer  и добавление его данных в бд
@dp.message_handler(commands=["start"])
async def start_bot(message: types.Message):
    cursor.execute(
        """
        INSERT OR IGNORE INTO user (telegram_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
        """, (
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
)
    connection.commit()
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        types.KeyboardButton("Профиль"),
        types.KeyboardButton("Расписание"),
        types.KeyboardButton("Отправить письмо")
    )
    await bot.send_message(
        message.chat.id,
        '''Привет!
Я бот который поможет тебе узнать расписание и поможет задать вопрос. ''',
        reply_markup=keyboard,
    )
    await bot.delete_message(
        message.chat.id,
        message.message_id,
    )

#logic button
@dp.message_handler(content_types=["text"])
async def message_handlers(message: types.Message):
    profile = cursor.execute(
        """
        SELECT * FROM user
        WHERE telegram_id = ?;
        """, (message.from_user.id,)
    ).fetchall()

    if message.text == "Профиль":
        await message.bot.send_message(
            message.chat.id,
            f"ID: {profile[0][0]}\nUsernume: {profile[0][1]}\nfirst_name: {profile[0][2]}\nlast_name: {profile[0][3]}\nletter: {profile[0][4]}"
        )

    if message.text == "Расписание":
        dates = cursor.execute(
            """
            SELECT date FROM task;
            """
        ).fetchall()
        keyboard = types.InlineKeyboardMarkup()
        for date in dates:
            keyboard.insert(
                types.InlineKeyboardButton(
                    text=f"{date[0]}",
                    callback_data=f"date:{date[0]}",
                )
            )
        await message.bot.send_message(
            message.chat.id,
            "Выберите дату",
            reply_markup=keyboard,
        )
    
    if message.text == "Отправить письмо":
        await message.reply("Введите текст письма:")
        await States.letter.set()


@dp.message_handler(state=States.letter)
async def save_message(message: types.Message, state: dispatcher.FSMContext):
    text = message.text
    user_id = message.from_user.id
    # Сохраняем сообщение в базе данных
    cursor.execute('UPDATE user SET letter = ? WHERE telegram_id = ?', (text, user_id,))
    connection.commit()

    await state.finish()
    await message.reply("Сообщение сохранено!")


@dp.callback_query_handler(lambda callback: callback.data.startswith("date"))
async def check_task(callback: types.CallbackQuery):
    task = cursor.execute(
        """
        SELECT task FROM task
        WHERE date = ?
        """, (callback.data.split(':')[1],)
    ).fetchall()[0]

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            "Назад",
            callback_data="back",
        ),
    )
    await callback.bot.send_message(
        callback.message.chat.id,
        f"{task[0]}",
        reply_markup=keyboard,
    )
    await callback.bot.delete_message(
        callback.message.chat.id,
        callback.message.message_id,
    )


@dp.callback_query_handler(lambda callback: "back" in callback.data)
async def back_to_menu(callback: types.CallbackQuery):

    dates = cursor.execute(
        """
        SELECT date FROM task;
        """
    ).fetchall()
    keyboard = types.InlineKeyboardMarkup()
    for date in dates:
        keyboard.insert(
            types.InlineKeyboardButton(
                text=f"{date[0]}",
                callback_data=f"date:{date[0]}",
            )
        )
    await callback.bot.send_message(
        callback.message.chat.id,
        "Выберите дату",
        reply_markup=keyboard,
    )
    await callback.bot.delete_message(
        callback.message.chat.id,
        callback.message.message_id,
    )


async def default_command():
    await dp.bot.set_my_commands(
        [
            types.BotCommand("start", "Старт"),
        ]
    )


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(default_command())
    loop.create_task(dp.start_polling())
    loop.run_forever()
