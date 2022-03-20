import asyncio
import json
import logging
import requests
from typing import List

from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters.callback_data import CallbackData
from aiogram.dispatcher.filters.command import Command
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.types import BotCommand, BotCommandScopeDefault, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.token import TokenValidationError
from pydantic import Field

from polling_manager import PollingManager

logger = logging.getLogger(__name__)

TOKENS = ["5126472216:AAEL1Dke53Shg5f6aBaHE56EEdaXAiopDV4"]
main_bot = Bot(TOKENS[0])
MAIN_BOT = 5126472216


class BotCallback(CallbackData, prefix="callback_bot"):
    token: str = Field(None, alias="BotCallback")


def _get_inline_tags(id: int, polling_list) -> types.InlineKeyboardMarkup:
    print(polling_list)
    url = f"https://true.loca.lt/api/from-tg-id-to-admin-chats/{id}/"
    cb_data = json.loads(requests.get(url).text)["chats"]
    keyboard_markup = InlineKeyboardBuilder()

    for x in cb_data:
        bot_id = int(x['api_key'].split(":")[0])
        keyboard_markup.row(
            InlineKeyboardButton(text="✅ " +x["name"] if bot_id in polling_list else x["name"], callback_data=f"token:{x['api_key']}")
        )

    return keyboard_markup.as_markup()


async def set_commands(bot: Bot):
    if bot.id == MAIN_BOT:
        commands = [
            BotCommand(
                command="edit",
                description="edit your bots'",
            ),
        ]
    else:
        commands = [
            BotCommand(
                command="restart",
                description="restart bot",
            ),
            BotCommand(
                command="list",
                description="get list of users(for admins only)",
            ),
        ]

    await bot.set_my_commands(commands=commands, scope=BotCommandScopeDefault())


async def on_bot_startup(bot: Bot):
    await set_commands(bot)
    bot_data = json.loads(requests.get(f"https://true.loca.lt/api/chat/{bot.id}").text)
    if bot_data:
        for user in bot_data["viewers"]:
            await bot.send_message(chat_id=user["tg_id"], text="bot started")


async def on_bot_shutdown(bot: Bot):
    bot_data = json.loads(requests.get(f"https://true.loca.lt/api/chat/{bot.id}").text)
    if bot_data:
        for user in bot_data["viewers"]:
            await bot.send_message(chat_id=user["tg_id"], text="bot shutdown")


async def on_startup(bots: List[Bot]):
    for bot in bots:
        await on_bot_startup(bot)


async def on_shutdown(bots: List[Bot]):
    for bot in bots:
        await on_bot_shutdown(bot)


async def init_bot(message: types.Message, bot: Bot, polling_manager: PollingManager):
    await bot.send_message(
        message.chat.id,
        "Select bots to edit:",
        reply_markup=_get_inline_tags(message.chat.id, polling_manager.polling_tasks),
    )


async def callback_action(
    query: types.CallbackQuery,
    bot: Bot,
    dp_for_new_bot: Dispatcher,
    polling_manager: PollingManager,
):
    await query.answer()
    data = query.data.split(":")
    bot_id = int(data[1])
    user_id = query.from_user.id
    if bot_id in polling_manager.polling_tasks:
        await stop_bot(
            bot=bot,
            bot_id=bot_id,
            user_id=user_id,
            polling_manager=polling_manager,
            token=data[1]+":"+data[2]
        )
    else:
        await add_bot(
            bot=bot,
            user_id=user_id,
            dp_for_new_bot=dp_for_new_bot,
            polling_manager=polling_manager,
            token=data[1]+":"+data[2]
        )
    await main_bot.edit_message_text(
        "Select bots to start:",
        query.from_user.id,
        query.message.message_id,
        reply_markup=_get_inline_tags(query.message.chat.id, polling_manager.polling_tasks),
    )


async def add_bot(
    bot: Bot,
    user_id: int,
    dp_for_new_bot: Dispatcher,
    polling_manager: PollingManager,
    token: str,
):
    if bot.id == MAIN_BOT:
        try:
            bot = Bot(token)

            if bot.id in polling_manager.polling_tasks:
                await bot.send_message(chat_id=user_id, text="bot is already running")
                return

            await polling_manager.start_bot_polling(
                dp=dp_for_new_bot,
                bot=bot,
                on_bot_startup=on_bot_startup(bot),
                on_bot_shutdown=on_bot_shutdown(bot),
                polling_manager=polling_manager,
                dp_for_new_bot=dp_for_new_bot,
            )
            bot_user = await bot.get_me()
            await main_bot.send_message(chat_id=user_id, text=f"New bot started: @{bot_user.username}")

            url = "https://true.loca.lt/api/chat-from-username/"

            dat = {
                "name": bot_user.first_name,
                "startMessage": f"bot @{bot_user.username}",
                "api_key": token,
                "tg_id": bot_user.id,
                "admin_tg_id": user_id,
            }
            r = requests.post(
                url,
                data=json.dumps(dat),
                headers={"content-type": "application/json"},
            )
            print(r.status_code)

        except (TokenValidationError, TelegramUnauthorizedError) as err:
            return


async def stop_bot(
    bot: Bot,
    user_id: int,
    polling_manager: PollingManager,
    bot_id: int,
    token: str
):
    if bot.id == MAIN_BOT:
        try:
            polling_manager.stop_bot_polling(bot_id)

            s_bot = Bot(token)
            bot_inf = await s_bot.get_me()

            await bot.send_message(chat_id=user_id, text=f"Bot stopped: @{bot_inf.username}")

        except (ValueError, KeyError) as err:
            return


async def echo(message: types.Message, bot: Bot):
    if bot.id != MAIN_BOT:
        bot_data = json.loads(
            requests.get(f"https://true.loca.lt/api/chat/{bot.id}").text
        )
        if message.chat.id == int(bot_data["admin"]["tg_id"]):
            if message.reply_to_message and "@" in message.reply_to_message.text:
                usr = message.reply_to_message.text.split("@")[1].split(":")[0]
                usr_dat = json.loads(
                    requests.get(
                        f"https://true.loca.lt/api/from-username-to-user/{usr}"
                    ).text
                )
                await bot.send_message(
                    chat_id=int(usr_dat["tg_id"]),
                    text="private massage:\n" + message.text,
                )
            else:
                for user in bot_data["viewers"]:
                    await bot.send_message(
                        chat_id=int(user["tg_id"]),
                        text="new broadcast:\n" + message.text,
                    )
        else:
            await bot.send_message(
                chat_id=int(bot_data["admin"]["tg_id"]),
                text=f"message from @{message.chat.username}:\n " + message.text,
            )

            url = "https://true.loca.lt/api/message-from-username/"

            dat = {
                "author_tg_nickname": message.chat.id,
                "message": message.text,
                "chat_id": bot.id,
                "message_id": message.message_id
            }
            r = requests.post(
                url, data=json.dumps(dat), headers={"content-type": "application/json"}
            )
            print(r.status_code)


async def start(message: types.Message, bot: Bot):
    url = "https://true.loca.lt/api/user/"
    dat = {"username": message.from_user.username, "tg_id": message.from_user.id}
    requests.post(
        url, data=json.dumps(dat), headers={"content-type": "application/json"}
    )

    if bot.id != MAIN_BOT:
        bot_data = json.loads(
            requests.get(f"https://true.loca.lt/api/chat/{bot.id}").text
        )
        if message.chat.id != int(bot_data["admin"]["tg_id"]):
            await bot.send_message(
                chat_id=int(bot_data["admin"]["tg_id"]),
                text=f"user @{message.from_user.username} joined chat",
            )
            await bot.send_message(
                chat_id=message.chat.id,
                text=f"Welcome to the chat, @{message.from_user.username}",
            )
            url = "https://true.loca.lt/api/add-viewer-to-chat/"
            dat = {"chat_tg_id": bot.id, "user_tg_id": message.from_user.id}
            requests.post(
                url, data=json.dumps(dat), headers={"content-type": "application/json"}
            )


async def user_list(message: types.Message, bot: Bot):
    if bot.id != MAIN_BOT:
        bot_data = json.loads(
            requests.get(f"https://true.loca.lt/api/chat/{bot.id}").text
        )
        if message.chat.id == int(bot_data["admin"]["tg_id"]):
            if bot_data["viewers"]:
                await message.answer(
                    ", ".join(["@" + x["username"] for x in bot_data["viewers"]])
                )
            else:
                await message.answer("nobody has joined your chat yet :(")


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    # TODO different Dispatchers for main bot and sub bots
    bots = [Bot(token) for token in TOKENS]
    dp = Dispatcher(isolate_events=True)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.message.register(init_bot, Command(commands="edit"))
    dp.callback_query.register(callback_action)
    dp.message.register(user_list, Command(commands="list"))
    dp.message.register(start, Command(commands=["start", "restart"]))
    dp.message.register(echo)

    polling_manager = PollingManager()

    for bot in bots:
        await bot.get_updates(offset=-1)
    await dp.start_polling(*bots, dp_for_new_bot=dp, polling_manager=polling_manager)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("Exit")
