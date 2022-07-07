import os
import time
import logging
from dotenv import load_dotenv
import telegram
import requests

from exceptions import URLNotResponding, EmptyData


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Send messages"""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Сообщение успешно отправлено')
    except telegram.TelegramError as err:
        raise telegram.TelegramError(
            f'Сообщение не отправлено по причине {err}')


def get_api_answer(current_timestamp):
    """Query to endpoint Yandex Practicum"""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as err:
        raise ConnectionError(f'Ошибка подключения - {err}')

    if response.status_code != 200:
        raise ConnectionError('Подкючение не удалось')
    hw_statuses = response.json()
    return hw_statuses


def check_response(response):
    """Check response from endpoint"""
    if not isinstance(response, dict):
        raise TypeError('API ответ не корректен')
    if 'homeworks' not in response:
        raise KeyError('Ключ "homework" отсутствует')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            'API ответ возвращает домашние работы отличные от типа list')
    return homeworks


def parse_status(homework):
    """Get status homework"""
    if 'homework_name' not in homework:
        raise KeyError('Ключ "homework_name" отсутствует')
    if 'status' not in homework:
        raise KeyError('Ключ "status" отсутствует')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise ValueError('Не найден статус')
    homework_name = homework['homework_name']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Check env variables"""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    logging.critical('Отсутствуют переменные окружения')
    return False

# flake8: noqa: C901
def main():
    """Основная логика работы бота."""
    check_constants_flag = check_tokens()
    if not check_constants_flag:
        return

    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except Exception as error:
        logging.critical(f'Переменная TELEGRAM_TOKEN с ошибкой - {error}')
        return

    current_timestamp = int(time.time())
    continue_flag: bool = True

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)
            else:
                logging.debug('Отсутствие в ответе новых статусов')
            continue_flag = True

            current_timestamp = int(time.time())

        except URLNotResponding as error:
            logging.error(error.message)
            if continue_flag:
                send_message(bot, error.message)

        except EmptyData as error:
            logging.error(error.message)
            if continue_flag:
                send_message(bot, error.message)

        except SystemExit as e:
            error = f'URL недоступно - {e.message}'
            logging.error(error)
            if continue_flag:
                send_message(bot, error)

            current_timestamp = ...
            time.sleep(RETRY_TIME)

        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
            if continue_flag:
                send_message(bot, f'Сбой в работе программы: {error}')

        finally:
            time.sleep(RETRY_TIME)
            continue_flag = False


if __name__ == '__main__':
    main()
