from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import BoundFilter
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import aiogram.utils.markdown as md
from aiogram.types import ParseMode

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

import prettytable as pt
import sqlite3
from datetime import datetime


from config import *

storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=storage)
admins_ids = [OWNER_MEMBER_ID]


class Form(StatesGroup):
    fullname = State()
    gender = State()
    age = State()
    location = State()
    citizenship = State()
    education = State()
    experience = State()
    salary = State()
    foreign_languages = State()
    marital_status = State()
    skills = State()
    additional_information = State()


class MyFilter(BoundFilter):
    key = 'is_admin'

    def __init__(self, is_admin):
        self.is_admin = is_admin

    async def check(self, message: types.Message):
        return message.chat.id in admins_ids


dp.filters_factory.bind(MyFilter)


@dp.message_handler(commands='help')
async def process_help_command(message: types.Message):
    await message.reply("Бот для записи анкет")


@dp.message_handler(is_admin=True, commands='upload')
async def google_drive_upload_file(message: types.Message = None, filepath=DB_FILENAME, google_dir=GOOGLE_DRIVE_DIR_ID):
    file_list = google_drive.ListFile({'q': f"'{google_dir}' in parents and trashed=false"}).GetList()
    for file in file_list:
        file.Delete()
    gfile = google_drive.CreateFile({'parents': [{'id': google_dir}]})
    gfile.SetContentFile(filepath)
    gfile.Upload()
    await message.reply('База данных успешно загружена')


@dp.message_handler(is_admin=True, commands='admin_add')
async def admin_add(message: types.Message):
    user_id = message.text[11:]
    global admins_ids
    if not (user_id and user_id.isdigit()):
        return await message.reply("ID должен состоять только из цифр")
    if user_id in admins_ids:
        return await message.reply("ID уже записан в список админов")
    admins_ids.append(user_id)
    await message.reply(f"{user_id} добавлен в список админов")


@dp.message_handler(is_admin=True, commands='admin_remove')
async def admin_remove(message: types.Message):
    user_id = message.text[14:]
    global admins_ids
    if not (user_id and user_id.isdigit()):
        return await message.reply("ID должен состоять только из цифр")
    if user_id not in admins_ids:
        return await message.reply("ID не записан в список админов")
    admins_ids.remove(user_id)
    await message.reply(f"{user_id} удален из списка админов")


@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='Завершить заполнение анкеты', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await process_start_command(message)
        return

    await state.finish()

    start_button = 'Начать заполнение анкеты'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(start_button)
    await message.reply('Заполнение анкеты отменено. Данные не сохранены.', reply_markup=keyboard)


@dp.message_handler(commands=['start', 'Начать', 'new form'])
@dp.message_handler(Text(equals='Начать заполнение анкеты'))
async def process_start_command(message: types.Message):
    await Form.fullname.set()

    start_button = 'Начать заполнение анкеты'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(start_button)
    await message.answer("Привет! Предлагаем тебе пройти анкетирование в нашу компанию.\n"
                         "Используй кнопки на клавиатуре снизу, ответы отправляйте одним сообщением")
    await message.answer("Введите ФИО (Иванов Иван Иванович), отчество указывать при наличии", reply_markup=keyboard)


@dp.message_handler(lambda message: len(message.text.split()) not in (2, 3), state=Form.fullname)
async def process_fullname_invalid(message: types.Message):
    return await message.reply('Некорректно введены ФИО.\n'
                               'Пример заполнения: "Иванов Иван Иванович" или "Иванов Иван" (при отсутствии отчества)')


@dp.message_handler(lambda message: len(message.text.split()) in (2, 3), state=Form.fullname)
async def process_fullname(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        fullname = ' '.join(message.text.split())
        data['fullname'] = fullname
    await Form.next()

    buttons = ('Мужчина', 'Женщина')
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*buttons)
    keyboard.add('Другой')
    keyboard.add('Завершить заполнение анкеты')

    await message.answer("Введите свой гендер", reply_markup=keyboard)


@dp.message_handler(lambda message: message.text not in ["Мужчина", "Женщина", "Другой"], state=Form.gender)
async def process_gender_invalid(message: types.Message):
    return await message.reply("Пожалуйста, введите гендер из представленных вариантов на клавиатуре")


@dp.message_handler(state=Form.gender)
async def process_gender(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['gender'] = message.text
    await Form.next()

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add('Завершить заполнение анкеты')

    await message.answer("Введите свой возраст", reply_markup=keyboard)


@dp.message_handler(lambda message: not message.text.isdigit(), state=Form.age)
async def process_age_invalid(message: types.Message):
    return await message.reply("Возраст должен быть натуральным числом. Сколько Вам лет?")


@dp.message_handler(state=Form.age)
async def process_age(message: types.Message, state: FSMContext):
    age = int(message.text)
    if age > 150:
        return await message.reply('К сожалению, Ваш возраст слишком велик для нашей компании.'
                                   ' Возможно, Вы опечатались. Введите свой возраст еще раз')

    async with state.proxy() as data:
        data['age'] = age
    await Form.next()

    button = 'Москва'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(button)
    keyboard.add('Завершить заполнение анкеты')

    await message.answer("Введите город, в котором вы сейчас проживаете", reply_markup=keyboard)


@dp.message_handler(state=Form.location)
async def process_location(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['location'] = message.text
    await Form.next()

    button = 'РФ'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(button)
    keyboard.add('Завершить заполнение анкеты')

    await message.answer("Введите своё гражданство", reply_markup=keyboard)


@dp.message_handler(state=Form.citizenship)
async def process_citizenship(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['citizenship'] = message.text
    await Form.next()

    button = 'Отсутствует'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(button)
    keyboard.add('Завершить заполнение анкеты')

    await message.answer("Введите своё образование", reply_markup=keyboard)


@dp.message_handler(state=Form.education)
async def process_education(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['education'] = message.text
    await Form.next()

    button = 'Отсутствует'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(button)
    keyboard.add('Завершить заполнение анкеты')

    await message.answer('Укажите опыт работы в других компаниях (если есть)', reply_markup=keyboard)


@dp.message_handler(state=Form.experience)
async def process_experience(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['experience'] = message.text
    await Form.next()

    button = '0'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(button)
    keyboard.add('Завершить заполнение анкеты')

    await message.answer('Какую зарплату вы ожидаете на новом месте работы?\n'
                         'Укажите целое значение в рублях или "0" — если не имеет значения', reply_markup=keyboard)


@dp.message_handler(lambda message: not message.text.isdigit(), state=Form.salary)
async def process_salary_invalid(message: types.Message):
    return await message.reply("Зарплата должна быть натуральным числом."
                               " Пожалуйста, укажите ожидаемую зарплату в рублях")


@dp.message_handler(state=Form.salary)
async def process_salary(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['salary'] = int(message.text)
    await Form.next()

    button = 'Английский язык'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(button)
    keyboard.add('Завершить заполнение анкеты')

    await message.answer("Какие иностранные языки вы знаете?", reply_markup=keyboard)


@dp.message_handler(state=Form.foreign_languages)
async def process_foreign_languages(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['foreign_languages'] = message.text
    await Form.next()

    buttons = ('В браке', 'Не в браке', 'В разводе', 'Есть отношения', 'Нет отношений')
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*buttons)
    keyboard.add('Завершить заполнение анкеты')

    await message.answer('Укажите Ваш семейный статус', reply_markup=keyboard)


@dp.message_handler(
    lambda message: message.text not in ['В браке', 'Не в браке', 'В разводе', 'Есть отношения', 'Нет отношений'],
    state=Form.marital_status)
async def process_marital_status(message: types.Message):
    return await message.reply("Пожалуйста, введите своё семейное положение из представленных вариантов на клавиатуре")


@dp.message_handler(state=Form.marital_status)
async def process_marital_status(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['marital_status'] = message.text
    await Form.next()

    button = 'Отсутствуют'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(button)
    keyboard.add('Завершить заполнение анкеты')

    await message.answer("Укажите Ваши навыки", reply_markup=keyboard)


@dp.message_handler(state=Form.skills)
async def process_skills(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['skills'] = message.text
    await Form.next()

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add('Завершить заполнение анкеты')

    await message.answer("Отправьте дополнительную информацию о Вас", reply_markup=keyboard)


@dp.message_handler(state=Form.additional_information)
async def process_additional_information(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['additional_information'] = message.text
    await Form.next()

    data = (
        ['ФИО', data['fullname']],
        ['Гендер', data['gender']],
        ['Возраст', f"{data['age']}"],
        ['Место проживания', data['location']],
        ['Гражданство', data['citizenship']],
        ['Образование', data['education']],
        ['Опыт работы', data['experience']],
        ['Ожидаемая зарплата', f"{data['salary']}"],
        ['Иностранные языки', data['foreign_languages']],
        ['Семейное положение', data['marital_status']],
        ['Навыки', data['skills']],
        ['Доп. информация', data['additional_information']],
    )

    table = pt.PrettyTable(['Характеристика', 'Ваш ответ'])
    table.add_rows(data)

    await message.answer('Спасибо за ответы! Данные, которые Вы ввели:')
    await bot.send_message(
        message.chat.id,
        md.text(
            f'```{table}```'
        ),
        parse_mode=ParseMode.MARKDOWN_V2
    )

    application_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    async with state.proxy() as data:
        data['date'] = application_time
        data['user_id'] = message.from_user.id

    await db_add_questionnaire_questionnaire(data)

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add('Начать заполнение анкеты')

    await state.finish()

    await message.answer("Удачи!", reply_markup=keyboard)


async def db_add_questionnaire_questionnaire(data):
    """Запись в базу данных"""
    await db_create_table(DB_FILENAME)

    db = sqlite3.connect(DB_FILENAME)
    cursor = db.cursor()
    cursor.execute(
        f"INSERT INTO questionnaire (user_id, application_time, fullname, gender, age, location, citizenship, "
        f"education, experience, salary, foreign_languages, marital_status, skills, additional_information) VALUES "
        f"({data['user_id']}, '{data['date']}', '{data['fullname']}', '{data['gender']}', {data['age']}, "
        f"'{data['location']}', '{data['citizenship']}', '{data['education']}', '{data['experience']}', "
        f"{data['salary']}, '{data['foreign_languages']}', '{data['marital_status']}', '{data['skills']}', "
        f"'{data['additional_information']}')"
    )
    db.commit()
    cursor.close()
    db.close()


def google_authorization():
    gauth_ = GoogleAuth()
    auth_url = gauth_.GetAuthUrl()
    print(auth_url)
    code = input()
    if r'%2F' in code:
        code = code.replace(r"%2F", r'/')
    gauth_.Auth(code)
    drive_ = GoogleDrive(gauth_)
    return drive_


async def db_create_table(filename):
    """Создание таблицы в бд"""
    db = sqlite3.connect(filename)
    cursor = db.cursor()

    cursor.execute(
        """CREATE TABLE IF NOT EXISTS "questionnaire" (
        "id"	INTEGER NOT NULL UNIQUE,
        "user_id"	INTEGER NOT NULL,
        "application_time"	TEXT,
        "fullname"	TEXT,
        "gender"	TEXT,
        "age"	INTEGER,
        "location"	TEXT,
        "citizenship"	TEXT,
        "education"	TEXT,
        "experience"	TEXT,
        "salary"	INTEGER,
        "foreign_languages"	TEXT,
        "marital_status"	TEXT,
        "skills"	TEXT,
        "additional_information"	TEXT,
        PRIMARY KEY("id" AUTOINCREMENT))"""
    )

    db.commit()
    cursor.close()
    db.close()


def main():
    global google_drive
    google_drive = google_authorization()
    executor.start_polling(dp)


if __name__ == '__main__':
    main()
