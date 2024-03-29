# Импортируем нужные библиотеки
import telebot
import logging
from telebot.types import ReplyKeyboardMarkup
from gpt import count_all_tokens, ask_gpt, create_system_prompt, upgrade_token
from database import create_table, create_db, execute_query, execute_selection_query
from config import BOT_TOKEN, MAX_LIMIT_TOKENS, MAX_LIMIT_SESSION, MAX_USERS, DB_NAME, text_help, genres, characters, settings 

# Создаем бота
bot = telebot.TeleBot(BOT_TOKEN)

# Словарь для хранения настроек пользователя
current_options = {}
# Словарь для хранения истории диалога пользователя и GPT
user_history = {}

# Создание базы данных и таблицы
create_db(DB_NAME)
create_table('users')

logging.basicConfig(filename='log.txt', level=logging.DEBUG,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", filemode="w")
 
# Функция создания клавиатуры с переданными кнопками
def make_keyboard(buttons):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(*buttons)
    return markup

# Обработчики команд:
@bot.message_handler(commands=['help'])
def say_help(message):
    bot.send_message(message.from_user.id, text_help)

@bot.message_handler(commands=['about'])
def about_command(message):
    bot.send_message(message.from_user.id, 'Давай я расскажу тебе немного о себе: Я - бот-сценарист, который пишет истории с помощью нейросети и, конечно, твоей фантазии. Я очень люблю интересные истории, поэтому уверен, что мы сможем написать крутой сценарий.',
                     reply_markup=make_keyboard(['/start', '/help']))

@bot.message_handler(commands=['start'])
def start(message):
    global current_options
    user_id = message.from_user.id
    if len(user_history) == MAX_USERS:
        bot.send_message(user_id, "Кажется, уже слишком много пользователей зарегестрировалось:(")
        return
    user_name = message.from_user.first_name
    bot.send_message(user_id,
                     text=f'Привет, {user_name}! Я бот, который создает истории с помощью нейросети. Напиши /new_story, чтобы начать новую историю. А когда закончишь, напиши /finish.',
                     reply_markup=make_keyboard(['/new_story', '/help', '/about']))
    current_options[user_id] = {'genre': '', 'character': '', 'setting': ''}
    if user_id not in user_history:
        user_history[user_id] = {'session': 0, 'collection': []}
    if user_history[user_id]['session'] == MAX_LIMIT_SESSION:
        bot.send_message(user_id, 'Ваши сессии закончились. К сожалению, новую историю начать не получится.')
        return
    logging.info('Отправка приветственного сообщения')

@bot.message_handler(commands=['new_story'])
def new_story(message):
    user_history[message.chat.id]['collection'] = []
    bot.send_message(message.chat.id, 'Отлично, приступим к сценарию. Выбери жанр будущей истории:', reply_markup=make_keyboard(genres))
    bot.register_next_step_handler(message, choose_genre)

def choose_genre(message):
    global current_options
    bot.send_message(message.chat.id, 'Выбери главного героя:', reply_markup=make_keyboard(characters))
    current_options[message.from_user.id]['genre'] = message.text
    bot.register_next_step_handler(message, choose_character)

def choose_character(message):
    global current_options
    setting = '\n'.join([' - '.join(i) for i in zip(settings.keys(), settings.values())])
    text =  'Выбери сеттинг:\n' + setting
    bot.send_message(message.chat.id, text, reply_markup=make_keyboard(settings.keys()))
    current_options[message.from_user.id]['character'] = message.text
    bot.register_next_step_handler(message, choose_setting)

def choose_setting(message):
    global current_options
    bot.send_message(message.chat.id, 'Если ты хочешь, чтобы мы учли еще какую-то информацию, напиши ее сейчас. Или ты можешь сразу переходить к истории, написав /begin.', reply_markup=make_keyboard(['/begin']))
    current_options[message.from_user.id]['setting'] = settings[message.text]
    bot.register_next_step_handler(message, begin)

def begin(message):
    user_id = message.from_user.id
    if message.content_type != 'text':
        logging.info('Error - Неверный формат данных')
        bot.send_message(user_id, 'Пока я умею работать только с текстовыми сообщениями. Пожалуйста, отправьте сообщение именно текстом.')
        bot.register_next_step_handler(message, begin)
        return
    user_history[user_id]['collection'].append({'role': 'system', 'text': create_system_prompt(current_options, user_id)})
    if message.text == '/begin':
        bot.send_message(user_id, 'Генерирую...')
        handle(message)
    else:
        user_history[user_id]['collection'].append({'role': 'user', 'text': message.text})
        bot.send_message(user_id, 'Спасибо. Все учтем. Напиши /begin, чтобы начать писать историю.')
        bot.register_next_step_handler(message, begin)
   
@bot.message_handler(commands=['finish'])
def end_task(message):
    user_id = message.from_user.id
    assistant_content = ask_gpt(user_history[user_id]['collection'], mode='end')
    user_history[user_id]['collection'].append({'role': 'assistant', 'text': assistant_content})
    user_history[user_id]['session'] += 1
    bot.send_message(user_id, assistant_content)
    bot.send_message(user_id, 'Спасибо, что писал со мной историю.', reply_markup=make_keyboard(['/new_story', '/whole_story', '/all_tokens', '/debug']))

@bot.message_handler(commands=['whole_story'])
def whole_story(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Вот история, которая у нас получилась:')
    all_history = execute_selection_query(f'SELECT content FROM users WHERE user_id = {user_id} AND session = {user_history[user_id]['session']-1} AND (role = "user" OR role = "assistant")')
    for res in all_history:
        bot.send_message(user_id, res)
    bot.send_message(user_id, 'Конец истории.')

@bot.message_handler(commands=['all_tokens'])
def all_tokens(message):
    user_id = message.from_user.id
    all_tokens = execute_selection_query(f'SELECT tokens FROM users WHERE user_id = {user_id} ORDER BY id DESC LIMIT 1')
    bot.send_message(user_id, f'Количество использованных токенов: {all_tokens[0][0]}')
    
@bot.message_handler(commands=['debug'])
def logs_debug(message):
    with open("log.txt", "rb") as f:
        bot.send_document(message.chat.id, f)

# Обработка текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle(message):
    user_id = message.from_user.id
    if message.content_type != 'text':
        logging.info('Error - Неверный формат данных')
        bot.send_message(user_id, 'Пока я умею работать только с текстовыми сообщениями. Пожалуйста, отправьте сообщение именно текстом.')
        bot.register_next_step_handler(message, handle)
        return
    if user_history[user_id]['session'] < MAX_LIMIT_SESSION:
        if count_all_tokens(user_history[user_id]['collection']) <= MAX_LIMIT_TOKENS:
            if user_id not in current_options or current_options[user_id] == {}:
                if user_id not in current_options or current_options[user_id]['genre'] not in genres or current_options[user_id]['character'] not in characters or current_options[user_id]['setting'] not in settings:
                    bot.send_message(user_id, 'Ты не зарегистрировался или не выбрал жанр, героя или сеттинг.')
                    start(message)
                    return
            if message.text != '/begin':
                user_history[user_id]['collection'].append({'role': 'user', 'text': message.text})
            execute_query(f"INSERT INTO users (user_id, session, tokens, role, content) "
                                    f"VALUES ({user_id}, '{user_history[user_id]['session']}', '{count_all_tokens(user_history[user_id]['collection'])}', '{user_history[user_id]['collection'][-1]['role']}', '{user_history[user_id]['collection'][-1]['text']}')")
            upgrade_token() # перед запросом к GPT, делаем проверку на действительность токена - обновляем, если время действия истекло
            assistant_content = ask_gpt(user_history[user_id]['collection'])
            if assistant_content != "Произошла непредвиденная ошибка. Подробности см. в журнале.": # ответ без ошибок
                user_history[user_id]['collection'].append({'role': 'assistant', 'text': assistant_content})
                execute_query(f"INSERT INTO users (user_id, session, tokens, role, content) "
                                    f"VALUES ({user_id}, '{user_history[user_id]['session']}', '{count_all_tokens(user_history[user_id]['collection'])}', '{user_history[user_id]['collection'][-1]['role']}', '{user_history[user_id]['collection'][-1]['text']}')")
                bot.send_message(user_id, assistant_content,
                                    reply_markup=make_keyboard(['/finish']))
        else:
            bot.send_message(user_id, 'У вас израсходованы все токены. К сожалению, историю нужно закончить. Но вы можете начать писать новый сценарий!', reply_markup=make_keyboard(['/new_story', '/whole_story', '/all_tokens', '/debug']))
            user_history[user_id]['session'] += 1
            logging.info(f'Output: Количество токенов в сессии израсходовано.')
    else:
        bot.send_message(user_id, 'Ваши сессии закончились. Вы можете посмотреть получившийся сценарий, количество потраченных токенов или файл с логами.', reply_markup=make_keyboard(['/whole_story', '/all_tokens', '/debug']))

bot.polling()
