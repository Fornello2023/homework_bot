import logging
import os
import sys
import time

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
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.critical(
            'Отсутствует обязательная переменная окружения.')
        raise ValueError('Отсутствует обязательная переменная окружения.')


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
        response = requests.get(ENDPOINT, headers=HEADERS, params={
                                'from_date': timestamp})

        if response.status_code != 200:
            raise HomeworkAPIResponseError(
                f'Ошибка при запросе к API.Статус код: {response.status_code}')

        return response.json()

    except requests.exceptions.HTTPError as http_err:
        logger.error(
            f'Ошибка HTTP при запросе к API: {http_err}.'
            f' Эндпоинт {ENDPOINT} недоступен.'
            )
        raise HomeworkAPIResponseError(
            f'Ошибка при запросе к API: {http_err}') from http_err

    except requests.exceptions.RequestException as err:
        logger.error(
            f'Ошибка при запросе к API: {err}. '
            f'Эндпоинт {ENDPOINT} недоступен.'
        )

        raise HomeworkAPIError(f'Ошибка при запросе к API: {err}') from err


def check_response(response):
    """Проверка формата ответа от API."""
    if not isinstance(response, dict):
        logger.error('Ответ API не является словарем.')
        raise TypeError('Ответ API не является словарем.')

    if 'homeworks' not in response:
        logger.error("Отсутствует ключ 'homeworks' в ответе API.")
        raise KeyError("Отсутствует ключ 'homeworks' в ответе API.")

    if not isinstance(response['homeworks'], list):
        logger.error("Значение ключа 'homeworks' должно быть списком.")
        raise TypeError("Значение ключа 'homeworks' должно быть списком.")

    return response['homeworks']


def parse_status(homework):
    """Извлечение статуса работы и подготовка сообщения для Telegram."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')

    if homework_name is None or status is None:
        logger.error(
            'В данных о домашней работе отсутствуют обязательные поля.')
        raise HomeworkNotFoundError(
            'В данных о домашней работе отсутствуют обязательные поля.')

    verdict = HOMEWORK_VERDICTS.get(status)

    if verdict is None:
        logger.error(f'Неизвестный статус работы: {status}')
        raise HomeworkAPIResponseError(f'Неизвестный статус работы: {status}')

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
            time.sleep(RETRY_PERIOD)

        except HomeworkAPIError as error:
            message = f'Ошибка API: {error.message}'
            send_message(bot, message)
            logger.error(f'Ошибка API: {error}')
            time.sleep(RETRY_PERIOD)

        except HomeworkNotFoundError as error:
            message = f'Не найдены данные: {error.message}'
            send_message(bot, message)
            logger.error(f'Не найдены данные: {error}')
            time.sleep(RETRY_PERIOD)

        except HomeworkAPIResponseError as error:
            message = f'Ошибка обработки ответа: {error.message}'
            send_message(bot, message)
            logger.error(f'Ошибка обработки ответа: {error}')
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            message = f'Неизвестная ошибка: {error}'
            send_message(bot, message)
            logger.error(f'Неизвестная ошибка: {error}')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
