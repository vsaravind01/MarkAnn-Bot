import logging
from typing import Literal

from bot import constants
from common_managers.job_manager import JobManager


def command_logger(func):
    """Decorator to log the command execution.

    Args:
    -----
    func: Callable
        Function to be decorated

    Returns:
    --------
    wrapper:
        Decorated function
    """
    logger = logging.getLogger(func.__module__)

    def wrapper(*args, **kwargs):
        logger.debug(f"Command - {func.__name__} - started - {args} | {kwargs}")
        result = func(*args, **kwargs)
        logger.debug(f"Command - {func.__name__} - completed")
        return result

    return wrapper


def service_logger(service_name: str):
    """Decorator to log the start and completion of a service.

    Args:
    -----
    service_name: str
        Name of the service

    Returns:
    --------
    decorator:
        Decorator function
    """

    def decorator(func):
        logger = logging.getLogger(func.__module__)

        def wrapper(*args, **kwargs):
            logger.debug(f"Service - {service_name} - started - {args} | {kwargs}")
            result = func(*args, **kwargs)
            logger.debug(f"Service - {service_name} - completed")
            return result

        return wrapper

    return decorator


def subscription_gateway(
    j_manager: JobManager, cmd_type: Literal["start_service", "stop_service"]
):
    """Decorator to check if the user is already subscribed to the service.
    If the user is already subscribed, a message is sent to the user.

    Args:
    -----
    j_manager: JobManager
        The job manager object
    """

    if cmd_type not in ["start_service", "stop_service"]:
        raise ValueError(
            "Invalid command type. Must be either 'start_service' or 'stop_service'"
        )

    def decorator(func):
        if cmd_type == "start_service":

            async def wrapper(*args, **kwargs):
                update = args[0]
                if str(update.effective_user.id) in j_manager:
                    await update.effective_chat.send_message(
                        constants.ALREADY_SUBSCRIBED_MESSAGE.format(
                            first_name=update.effective_user.first_name,
                            last_name=update.effective_user.last_name,
                        )
                    )
                    return
                return await func(*args, **kwargs)

            return wrapper

        else:

            async def wrapper(*args, **kwargs):
                update = args[0]
                if str(update.effective_user.id) not in j_manager:
                    await update.effective_chat.send_message(
                        constants.NOT_SUBSCRIBED_MESSAGE
                    )
                    return
                return await func(*args, **kwargs)

            return wrapper

    return decorator
