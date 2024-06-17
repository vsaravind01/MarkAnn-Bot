import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext

from bot import decorators, services
from bot.constants import (
    ERROR_MESSAGE,
    GO_LIVE_MESSAGE,
    HELP_MESSAGE,
    LIVE_END_MESSAGE,
    START_MESSAGE,
    STOP_MESSAGE,
)
from common_managers import job_manager

logger = logging.getLogger(__name__)
j_manager = job_manager.JobManager()


@decorators.command_logger
@decorators.subscription_gateway(j_manager, cmd_type="start_service")
async def start_cmd(update: Update, context: CallbackContext):
    """Start command handler."""
    keyboard = [
        [InlineKeyboardButton(GO_LIVE_MESSAGE, callback_data="go_live")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        START_MESSAGE.format(
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name,
        ),
        reply_markup=reply_markup,
    )


@decorators.command_logger
@decorators.subscription_gateway(j_manager, cmd_type="stop_service")
async def stop_cmd(update: Update, context: CallbackContext):
    """Stop the live announcements service."""
    j_manager.remove_job(str(update.effective_user.id))
    logger.info(f"Live Stopped - Client ID: {update.effective_user.id}")
    await update.effective_chat.send_message(STOP_MESSAGE)


@decorators.command_logger
async def help_cmd(update: Update, context: CallbackContext):
    """Help command handler."""
    await update.message.reply_text(HELP_MESSAGE)


@decorators.command_logger
@decorators.subscription_gateway(j_manager, cmd_type="start_service")
async def keyboard_callback(update: Update, context: CallbackContext):
    """Keyboard callback handler."""
    query = update.callback_query

    logger.info(f"Keyboard Callback - Query: {query.data}")
    if query.data == "go_live":
        await run_cmd(update, context)
    await update.effective_chat.send_message(text=LIVE_END_MESSAGE)


@decorators.command_logger
async def error(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}")
    await update.effective_chat.send_message(ERROR_MESSAGE)


@decorators.command_logger
@decorators.subscription_gateway(j_manager, cmd_type="start_service")
async def run_cmd(update: Update, context: CallbackContext):
    """Start the live announcements service.
    The service fetches and sends announcements to the user. The service runs until the user stops it.
    """
    client_id = str(update.effective_user.id)
    try:
        logger.info(f"Starting Live - Client ID: {client_id}")
        job = j_manager.add_job(
            str(update.effective_user.id),
            services.ann_service,
            update=update,
            client_id=client_id,
        )
        logger.info(f"Live Started - Client ID: {client_id}")
        await job
    except Exception as e:
        logger.error(f"Error: {e}")
        j_manager.remove_job(str(update.effective_user.id))
