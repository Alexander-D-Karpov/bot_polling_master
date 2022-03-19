import asyncio
import logging
from typing import List

from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters.command import Command, CommandObject
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.utils.markdown import html_decoration as fmt
from aiogram.utils.token import TokenValidationError

from polling_manager import PollingManager

logger = logging.getLogger(__name__)

TOKENS = [
    "5126472216:AAEL1Dke53Shg5f6aBaHE56EEdaXAiopDV4"
]

MAIN_BOT = 5126472216

# TODO Move user data to DB
USER_LINKED_TO_BOT = {}
BOT_ADMIN = {}


async def set_commands(bot: Bot):
    if bot.id == MAIN_BOT:
        commands = [
            BotCommand(
                command="add_bot",
                description="add bot, usage '/add_bot 123456789:qwertyuiopasdfgh'",
            ),
            BotCommand(
                command="stop_bot",
                description="stop bot, usage '/stop_bot 123456789'",
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


async def on_bot_shutdown(bot: Bot):
    for user, user_id in USER_LINKED_TO_BOT[bot.id]:
        await bot.send_message(chat_id=user_id, text="bot shutdown!")


async def on_startup(bots: List[Bot]):
    for bot in bots:
        await on_bot_startup(bot)


async def on_shutdown(bots: List[Bot]):
    for bot in bots:
        await on_bot_shutdown(bot)


async def add_bot(
    message: types.Message,
    bot: Bot,
    command: CommandObject,
    dp_for_new_bot: Dispatcher,
    polling_manager: PollingManager,
):
    if bot.id == MAIN_BOT:
        if command.args:
            try:
                bot = Bot(command.args)

                if bot.id in polling_manager.polling_tasks:
                    await message.answer("Bot with this id already running")
                    return

                # also propagate dp and polling manager to new bot to allow new bot add bots
                await polling_manager.start_bot_polling(
                    dp=dp_for_new_bot,
                    bot=bot,
                    on_bot_startup=on_bot_startup(bot),
                    on_bot_shutdown=on_bot_shutdown(bot),
                    polling_manager=polling_manager,
                    dp_for_new_bot=dp_for_new_bot
                )
                bot_user = await bot.get_me()
                USER_LINKED_TO_BOT[bot_user.id] = []
                BOT_ADMIN[bot_user.id] = message.from_user.id
                await message.answer(f"New bot started: @{bot_user.username}")

            except (TokenValidationError, TelegramUnauthorizedError) as err:
                await message.answer(fmt.quote(f"{type(err).__name__}: {str(err)}"))
        else:
            await message.answer("Please provide token")


async def stop_bot(
    message: types.Message, bot: Bot, command: CommandObject, polling_manager: PollingManager
):
    if bot.id == MAIN_BOT:
        if command.args:
            try:
                polling_manager.stop_bot_polling(int(command.args))

                for user, user_id in USER_LINKED_TO_BOT[int(command.args)]:
                    await bot.send_message(chat_id=user_id, text="bot shutdown!")

                USER_LINKED_TO_BOT.pop(int(command.args))
                BOT_ADMIN.pop(int(command.args))
                await message.answer("Bot stopped")

            except (ValueError, KeyError) as err:
                await message.answer(fmt.quote(f"{type(err).__name__}: {str(err)}"))
        else:
            await message.answer("Please provide bot id")


async def echo(message: types.Message, bot: Bot):
    if bot.id != MAIN_BOT:
        if message.chat.id == BOT_ADMIN[bot.id]:
            if message.reply_to_message and "@" in message.reply_to_message.text:
                message_from = message.reply_to_message.text.split("@")[1].split(":")[0]
                for x in USER_LINKED_TO_BOT[bot.id]:
                    if x[0] == message_from:
                        message_id = x[1]
                        await bot.send_message(chat_id=message_id, text="private massage:\n" + message.text)
                        break
            else:
                for user, user_id in USER_LINKED_TO_BOT[bot.id]:
                    await bot.send_message(chat_id=user_id, text="new broadcast:\n" + message.text)
        else:
            await bot.send_message(chat_id=BOT_ADMIN[bot.id], text=f"message from @{message.chat.username}:\n " + message.text)


async def start(message: types.Message, bot: Bot):
    if bot.id != MAIN_BOT:
        if message.chat.id != BOT_ADMIN[bot.id] and message.chat.id not in [x[1] for x in USER_LINKED_TO_BOT[bot.id]]:
            USER_LINKED_TO_BOT[bot.id].append((message.chat.username, message.chat.id))


async def user_list(message: types.Message, bot: Bot):
    if bot.id != MAIN_BOT:
        if message.chat.id == BOT_ADMIN[bot.id]:
            if USER_LINKED_TO_BOT[bot.id]:
                await message.answer(", ".join(["@" + x[0] for x in USER_LINKED_TO_BOT[bot.id]]))
            else:
                await message.answer("nobody has joined your chat yet :(")


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    bots = [Bot(token) for token in TOKENS]
    dp = Dispatcher(isolate_events=True)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.message.register(add_bot, Command(commands="add_bot"))
    dp.message.register(stop_bot, Command(commands="stop_bot"))
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
