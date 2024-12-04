import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv

from exceptions import (
    HomeworkAPIError,
    HomeworkAPIResponseError,
    HomeworkNotFoundError
)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('TOKEN_PRACTICUM')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = 7230833414

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def check_tokens():
    """Проверка доступности всех необходимых переменных окружения."""
    missing_tokens = []

    if not PRACTICUM_TOKEN:
        missing_tokens.append('PRACTICUM_TOKEN')
    if not TELEGRAM_TOKEN:
        missing_tokens.append('TELEGRAM_TOKEN')
    if not TELEGRAM_CHAT_ID:
        missing_tokens.append('TELEGRAM_CHAT_ID')

    if missing_tokens:
        for token in missing_tokens:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: {token}')
        raise ValueError(
            'Отсутствуют обязательные переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )

    logger.info('Все обязательные переменные окружения присутствуют.')


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение "{message}"')
    except Exception as e:
        logger.error(f'Не удалось отправить сообщение в Telegram: {e}')


def get_api_answer(timestamp):
    """Отправка запроса к API и обработка ответа."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )

        if response.status_code != HTTPStatus.OK:
            raise HomeworkAPIResponseError(
                f'Ошибка при запросе к API. Статус код: {response.status_code}'
            )

        return response.json()

    except requests.exceptions.HTTPError as http_err:
        raise HomeworkAPIResponseError(
            f'Ошибка при запросе к API: {http_err}'
        ) from http_err

    except requests.exceptions.RequestException as err:
        raise HomeworkAPIError(f'Ошибка при запросе к API: {err}') from err


def check_response(response):
    """Проверка формата ответа от API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем.')

    if 'homeworks' not in response:
        raise KeyError("Отсутствует ключ 'homeworks' в ответе API.")

    if not isinstance(response['homeworks'], list):
        raise TypeError("Значение ключа 'homeworks' должно быть списком.")

    return response['homeworks']


def parse_status(homework):
    """Извлечение статуса работы и подготовка сообщения для Telegram."""
    if 'homework_name' not in homework:
        raise HomeworkNotFoundError(
            'Отсутствует ключ "homework_name" в данных о домашней работе.')

    if 'status' not in homework:
        raise HomeworkNotFoundError(
            'Отсутствует ключ "status" в данных о домашней работе.')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise HomeworkAPIResponseError(f'Неизвестный статус работы: {status}')

    verdict = HOMEWORK_VERDICTS[status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telebot.TeleBot(TELEGRAM_TOKEN)

    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
            else:
                logger.debug('В ответе API нет новых статусов.')

            timestamp = int(time.time())

        except Exception as error:
            message = f'Ошибка: {error}'
            send_message(bot, message)
            logger.error(f'Ошибка: {error}')

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
