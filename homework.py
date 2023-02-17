import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from telegram.error import TelegramError

from exceptions import (CheckResponseException, EndpointException,
                        NoTokensException, ParseStatusException)

load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    filename="main.log",
    format="%(funcName)s, %(lineno)s, %(levelname)s, %(message)s",
    filemode="w",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    "my_logger.log",
    maxBytes=50000000,
    backupCount=5,
)
logger.addHandler(handler)
formatter = logging.Formatter(
    "%(asctime)s, %(levelname)s, %(message)s, %(funcName)s, %(lineno)s"
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def send_message(bot, message):
    """Бот отправляет сообщение о статусе домашней работы."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f"Сообщение в чат {TELEGRAM_CHAT_ID}: {message}")
    except TelegramError:
        logger.error("Ошибка отправки сообщения в телеграм")


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {"from_date": timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException:
        logging.error("Ошибка при запросе к API")
        raise EndpointException("Ошибка при запросе к API")

    if response.status_code != HTTPStatus.OK:
        status_code = response.status_code
        logging.error(f"Ошибка {status_code}.")
        raise EndpointException(f"Ошибка {status_code}")
    try:
        return response.json()
    except requests.RequestException:
        logger.error("Ошибка парсинга ответа из формата json")
        raise ParseStatusException("Ошибка парсинга ответа из формата json")


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error("Ответ API не словарь")
        raise TypeError("Ответ API не словарь")
    try:
        list_homeworks = response["homeworks"]
    except KeyError:
        logger.error("Данные приходят не в виде словаря")
        raise KeyError("Данные приходят не в виде словаря")
    if not isinstance(list_homeworks, list):
        logger.error("Данные приходят не в виде списка")
        raise TypeError("Данные приходят не в виде списка")
    try:
        homework = list_homeworks[0]
    except CheckResponseException:
        logger.error("Список домашних работ пуст")
        raise CheckResponseException("Список домашних работ пуст")
    return homework


def parse_status(homework):
    """Извлекает из информации c статус домашней работы."""
    homework_name = homework.get("homework_name")
    if homework_name is None:
        raise KeyError(
            "Отсутствие ожидаемых ключей в ответе API (homework_name)"
        )
    homework_status = homework.get("status")
    if homework_status is None:
        raise KeyError("Отсутствие ожидаемых ключей в ответе API (status)")
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if verdict is None:
        raise ParseStatusException(
            "Недокументированный статус домашней работы в ответе от API"
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - 2629743
    cache_message = ""
    error_message = ""
    if not check_tokens():
        logger.critical("Отсутствуют одна или несколько переменных окружения")
        raise NoTokensException(
            "Отсутствуют одна или несколько переменных окружения"
        )
    while True:
        try:
            response = get_api_answer(timestamp)
            message = parse_status(check_response(response))
            if message != cache_message:
                send_message(bot, message)
                cache_message = message
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            logger.error(error)
            message_t = str(error)
            if message_t != error_message:
                send_message(bot, message_t)
                error_message = message_t
        time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
