#!/usr/bin/env python3
import logging
import os
import secrets
import sqlite3

import aiohttp.web
from coolname import generate_slug
from aiogram import Bot, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.webhook import SendMessage
from aiogram.utils.executor import set_webhook

API_TOKEN = os.environ['TELEGRAM_TOKEN']
EXTERNAL_BASE_URL = os.environ['WEBHOOK_HOST']
WEBHOOK_PATH = os.environ.get('WEBHOOK_PATH', '/webhook')
WEBHOOK_URL = f'{EXTERNAL_BASE_URL}{WEBHOOK_PATH}'
DATABASE_PATH = os.environ.get('DATABASE_PATH', '/mnt/data/http_to_tg.db')

LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 3001

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)

dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

routes = aiohttp.web.RouteTableDef()

db = sqlite3.connect(DATABASE_PATH)


@routes.post('/{token}')
async def send(request: aiohttp.web.Request):
    cursor = db.cursor()
    cursor.execute('SELECT chat, alias FROM tokens WHERE token = ?', (request.match_info['token'],))
    result = cursor.fetchone()
    if result:
        chat_id, alias = result
        message = (await request.read()).decode('utf-8')
        await bot.send_message(chat_id, f'{alias}\n{message}')
        return aiohttp.web.HTTPAccepted()
    else:
        return aiohttp.web.HTTPNotFound()


@dp.message_handler(commands=['token'])
async def handler(message: types.Message):
    cursor = db.cursor()
    token = secrets.token_urlsafe()
    alias = message.get_args() or generate_slug(2)
    cursor.execute('INSERT INTO tokens VALUES (?, ?, ?)', (alias, token, message.chat.id))
    db.commit()
    return SendMessage(message.chat.id, f'Added: {alias}:{token}')


@dp.message_handler(commands=['alias'])
async def handler(message: types.Message):
    cursor = db.cursor()
    try:
        token, alias = message.get_args().split(maxsplit=1)
    except ValueError:
        return SendMessage(message.chat.id, 'Usage: /alias <token> <alias>')
    else:
        cursor.execute('UPDATE tokens SET alias = ? WHERE token = ? AND chat = ?', (alias, token, message.chat.id))
        db.commit()
        return SendMessage(message.chat.id, f'Changed: {alias}:{token}')


@dp.message_handler(commands=['tokens'])
async def handler(message: types.Message):
    cursor = db.cursor()
    cursor.execute('SELECT alias, token FROM tokens WHERE chat = ?', (message.chat.id,))
    return SendMessage(message.chat.id, 'Tokens:\n{}'.format('\n'.join(
        ':'.join(row) for row in cursor.fetchall()
    )))


@dp.message_handler(commands=['delete'])
async def handler(message: types.Message):
    cursor = db.cursor()
    tokens = message.get_args().split()
    for token in tokens:
        cursor.execute('DELETE from tokens WHERE token = ? and chat = ?', (token, message.chat.id,))
    db.commit()
    return SendMessage(message.chat.id, 'Deleted:\n{}'.format('\n'.join(tokens)))


async def on_startup(dp_):
    await bot.set_webhook(WEBHOOK_URL)
    cursor = db.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS tokens (alias, token, chat)')


async def on_shutdown(dp_):
    logging.warning('Shutting down...')
    await bot.delete_webhook()
    db.close()
    logging.warning('Bye!')


if __name__ == '__main__':
    app = aiohttp.web.Application()
    app.add_routes(routes)

    executor = set_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
    )
    executor.web_app.add_routes(routes)
    executor.run_app(host=LISTEN_HOST, port=LISTEN_PORT)
