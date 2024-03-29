# Импортируем нужные библиотеки
import time
import logging
import requests
from config import FOLDER_ID, GPT_MODEL, MODEL_TEMPERATURE, MAX_MODEL_TOKENS, SYSTEM_PROMPT, CONTINUE_STORY, END_STORY

logging.basicConfig(filename='log.txt', level=logging.DEBUG,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", filemode="w")

# Обновление токена
def upgrade_token():
    global TOKEN, expires_at
    if expires_at < time.time():
        token_data = create_new_token()
        TOKEN = token_data['access_token']
        expires_at = time.time() + token_data['expires_in']

# Создание нового токена
def create_new_token():
    metadata_url = "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
    headers = {"Metadata-Flavor": "Google"}
    try:
        response = requests.get(metadata_url, headers=headers)
        return response.json()
    except Exception as e:
        logging.error(f'An error occurred while retrieving token: {e}')

token_data = create_new_token()
TOKEN = token_data['access_token']
expires_at = time.time() + token_data['expires_in']

# Запрос к Yandex GPT
def ask_gpt(collection, mode='continue'):
    url = f"https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json'
    }
    data = {
        "modelUri": f"gpt://{FOLDER_ID}/{GPT_MODEL}/latest",
        "completionOptions": {
            "stream": False,
            "temperature": MODEL_TEMPERATURE,
            "maxTokens": MAX_MODEL_TOKENS
        },
        "messages": []
    }
    for row in collection:
        content = row['text']
        if mode == 'continue' and row['role'] == 'user':
            content += f'\n{CONTINUE_STORY}'
        elif mode == 'end' and row['role'] == 'user':
            content += f'\n{END_STORY}'
        data["messages"].append(
                {
                    "role": row["role"],
                    "text": content
                }
            )
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            logging.debug(f"Response {response.json()} Status code:{response.status_code} Message {response.text}")
            result = f"Status code {response.status_code}. Подробности см. в журнале."
            return result
        result = response.json()['result']['alternatives'][0]['message']['text']
        logging.info(f"Request: {response.request.url}\n"
                     f"Response: {response.status_code}\n"
                     f"Response Body: {response.text}\n"
                     f"Processed Result: {result}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        result = "Произошла непредвиденная ошибка. Подробности см. в журнале."
    return result

# Новый метод получения кол-ва токенов YaGPT
def count_tokens(text):
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json'
    }
    len_tokens = requests.post(
        "https://llm.api.cloud.yandex.net/foundationModels/v1/tokenize",
        json={"modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest", "text": text},
        headers=headers
    )
    return len(len_tokens.json()['tokens'])

# Получения количества токенов из всего диалога
def count_all_tokens(messages):
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json'
    }
    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
        'maxTokens': MAX_MODEL_TOKENS,
        'messages': []
    }
    for ell in messages:
        data['messages'].append(ell)
    response = requests.post(
            url="https://llm.api.cloud.yandex.net/foundationModels/v1/tokenizeCompletion",
            json=data,
            headers=headers
        )
    if response.status_code == 200:
        tokens = response.json()["tokens"]
        return len(tokens)
    else:
        raise RuntimeError(
            'Invalid response received: code: {}, message: {}'.format(
                {response.status_code}, {response.text}
            )
        )

def create_system_prompt(data, user_id):
    prompt = SYSTEM_PROMPT
    prompt += (f'\nНапиши историю в жанре {data[user_id]["genre"]}'
               f' с главным героем: {data[user_id]["character"]}. '
               f'{data[user_id]["setting"]} Начало должно быть коротким, не более трех предложений. Не пиши никакой пояснительный текст от себя.')
    return prompt
