import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from telegram.error import TelegramError

from exceptions import (
    EndpointException,
    ParseStatusException,
)

load_dotenv()
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


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Бот отправляет сообщение о статусе домашней работы."""
    try:
        logger.debug("Начало отправки статуса в telegram")
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TelegramError as error:
        raise TelegramError(f"Ошибка отправки статуса в telegram: {error}")
    else:
        logger.debug("Статус отправлен в telegram")


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {"from_date": timestamp}
    try:
        logger.debug(f"Начало запроса к API:{ENDPOINT}, {params}")
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException:
        raise EndpointException("Ошибка при запросе к API")

    if response.status_code != HTTPStatus.OK:
        status_code = response.status_code
        raise EndpointException(f"Ошибка {status_code}")
    try:
        return response.json()
    except requests.RequestException:
        raise ParseStatusException("Ошибка парсинга ответа из формата json")


def check_response(response) -> list:
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError("Ответ API не словарь")
    try:
        homeworks = response["homeworks"]
    except KeyError:
        raise KeyError("Данные приходят не в виде словаря")
    if not isinstance(homeworks, list):
        raise TypeError("Данные приходят не в виде списка")
    return homeworks


def parse_status(homework) -> str:
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
    timestamp = int(time.time())
    cache_message = ""
    error_message = ""
    if not check_tokens():
        logger.critical("Отсутствуют одна или несколько переменных окружения")
        sys.exit(["Отсутствуют одна или несколько переменных окружения"])
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                timestamp = response.get("current_date")
                if message != cache_message:
                    send_message(bot, message)
                    cache_message = message
                    timestamp = int(time.time())
            else:
                logger.debug("Отсутствует новая информация")

        except Exception as error:
            logger.error(error)
            message_t = str(error)
            if message_t != error_message:
                send_message(bot, message_t)
                error_message = message_t
            time.sleep(RETRY_PERIOD)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        filename="main.log",
        format="%(funcName)s, %(lineno)s, %(levelname)s, %(message)s",
        filemode="w",
    )
    main()
