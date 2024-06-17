from telegram.ext import (
    Application,
    BaseHandler,
)

from bot.constants import TOKEN


class MarkAnnBot:
    """MarkAnn Bot class.
    MarkAnn bot is a Telegram bot that provides live stock market press release announcements.

    Attributes:
    -----------
    app: Application
        Telegram bot application instance

    Methods:
    --------
    attach_handler(handler: Callable)
        Attach custom handlers to the bot application.
    run()
        Run the bot application.
    """

    def __init__(self):
        self.app = Application.builder().token(TOKEN).concurrent_updates(True).build()

    def attach_handler(self, handler: BaseHandler):
        """Attach custom handlers to the bot application.

        Args:
        -----
        handler: BaseHandler
            The handler to attach to the command.
        """
        self.app.add_handler(handler)

    def attach_error_handler(self, handler: BaseHandler):
        """Attach custom error handlers to the bot application.

        Args:
        -----
        handler: BaseHandler
            The handler to attach to the command.
        """
        self.app.add_error_handler(handler)

    def run(self):
        """Run the bot application."""
        self.app.run_polling()
