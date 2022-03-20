#!/usr/bin/env python
# encoding: utf-8
import asyncio
import json
from functools import wraps

from aiogram import Dispatcher, Bot
from aiogram.dispatcher.filters import Command
from flask import Flask, request, jsonify
from bot import add_bot, on_bot_startup, on_bot_shutdown, on_startup, on_shutdown, stop_bot, user_list, start, echo, \
    init_bot
from polling_manager import PollingManager

app = Flask(__name__)
polling_manager = PollingManager()
dp = Dispatcher(isolate_events=True)
dp_for_new_bot = dp

dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)

dp.message.register(add_bot, Command(commands="add_bot"))
dp.message.register(stop_bot, Command(commands="stop_bot"))
dp.message.register(user_list, Command(commands="list"))
dp.message.register(start, Command(commands=["start", "restart"]))
dp.message.register(echo)

def async_action(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapped


@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    record = json.loads(request.data)
    id = record["id"]
    print(id)
    return jsonify(record)


@app.route('/start_bot', methods=['POST'])
@async_action
async def start_bot():
    record = json.loads(request.data)
    token = record["token"]
    print(token)

    bot = Bot(token)

    await init_bot(token=token)

    return jsonify(record)


app.run(debug=True)