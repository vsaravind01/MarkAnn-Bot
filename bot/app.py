import logging
import os
from datetime import datetime

from telegram.ext import CallbackQueryHandler, CommandHandler

from bot import bots, commands
from bot.decorators import service_logger
from bot.services import startup_service
from database.decorators import run_migration

if not os.path.exists(f"{os.path.dirname(__file__)}/logs"):
    os.makedirs(f"{os.path.dirname(__file__)}/logs")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s → %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=f"{os.path.dirname(__file__)}/logs/{datetime.now().strftime('%Y%m%d_%H%M%S')}_markann.log",
    filemode="w",
)


@run_migration
@service_logger(service_name="MarkAnnBot")
def main():
    """Main function to start the bot."""

    startup_service()

    bot = bots.MarkAnnBot()
    bot.attach_handler(CommandHandler("start", commands.start_cmd))
    bot.attach_handler(CommandHandler("stop", commands.stop_cmd))
    bot.attach_handler(CommandHandler("help", commands.help_cmd))
    bot.attach_handler(CallbackQueryHandler(commands.keyboard_callback))

    bot.attach_error_handler(CallbackQueryHandler(commands.error))

    bot.run()


if __name__ == "__main__":
    main()
