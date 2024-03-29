import logging
import sqlite3
from config import DB_NAME

logging.basicConfig(filename='log.txt', level=logging.DEBUG,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", filemode="w")

def create_db(DB_NAME=DB_NAME):
    db_path = f'{DB_NAME}'
    connection = sqlite3.connect(db_path)
    connection.close()
    logging.info(f'Output: База данных успешно создана')

# Функция для выполнения любого sql-запроса для изменения данных
def execute_query(sql_query, data=None, db_path=f'{DB_NAME}'):
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        if data:
            cursor.execute(sql_query, data)
        else:
            cursor.execute(sql_query)
        connection.commit()
        return cursor
    except sqlite3.Error as e:
        logging.error(f'Output: Ошибка при выполнении запроса: {e}')
        print('Ошибка при выполнении запроса:', e)
    finally:
        connection.close()

# Функция для выполнения любого sql-запроса для получения данных (возвращает значение)
def execute_selection_query(sql_query, data=None, db_path=f'{DB_NAME}'):
    try:
        logging.info(f'Execute query: {sql_query}')
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        if data:
            cursor.execute(sql_query, data)
        else:
            cursor.execute(sql_query)
        rows = cursor.fetchall()
        connection.close()
        return rows
    except sqlite3.Error as e:
        logging.error(f'Output: Ошибка при sql-запросе: {e}')
        print('Ошибка при выполнении sql-запроса:', e)

# Функция для создания новой таблицы (если такой ещё нет)
# Создаёт запрос CREATE TABLE IF NOT EXISTS имя_таблицы (колонка1 ТИП, колонка2 ТИП)
def create_table(table_name):
    sql_query = f'CREATE TABLE IF NOT EXISTS {table_name} ' \
                f'(id INTEGER PRIMARY KEY, ' \
                f'user_id INTEGER, ' \
                f'session INTEGER, ' \
                f'tokens INTEGER, ' \
                f'role TEXT, ' \
                f'content TEXT)'
    execute_query(sql_query)

# Функция для вывода всей таблицы (для проверки)
def get_all_rows(table_name):
    rows = execute_selection_query(f'SELECT * FROM {table_name}')
    for row in rows:
        print(row)
