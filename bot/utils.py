import logging
import re
from datetime import datetime
from typing import Optional

from bot.constants import PRESS_RELEASE_MESSAGE_TEMPLATE

logger = logging.getLogger(__name__)


def auto_strptime(date_str: str):
    """Automatically parse the date string to datetime object."""
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",  # With microseconds
        "%Y-%m-%dT%H:%M:%S",  # Without microseconds
        "%Y-%m-%dT%H:%M",  # Without seconds
        "%Y-%m-%d",  # Only date
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError("Date format not recognized")


def format_message(item: dict):
    """Format the message to be sent to the user in MarkdownV2 format.

    Args:
    -----
    item: dict
        Announcement data

    Returns:
    --------
    str
        Formatted message to be sent to the user
    """
    logger.info(f"Formatting message for {str(item)}")
    if "company" in item["summary"]:
        company_info = f"[{item['summary']['company']}](https://google.com/search?q={item['summary']['company']})"
    else:
        company_info = "NA"
    return escape_markdown(
        PRESS_RELEASE_MESSAGE_TEMPLATE.format(
            ann_type=item["summary"]["type"].upper(),
            time=auto_strptime(item["date"]).strftime("%I:%M %p"),
            date=auto_strptime(item["date"]).strftime("%B %d, %Y"),
            company=escape_markdown(company_info),
            value=item["summary"]["value"],
            description=escape_markdown(item["summary"]["description"]),
            pdf_link=item["attachment"],
            bse_link=item["url"],
        ),
        version=3,
    )


def escape_markdown(
    text: str, version: int = 2, entity_type: str = None
) -> Optional[str]:
    """
    Helper function to escape telegram markup symbols.

    Args:
    -----
        text (:obj:`str`): The text.
        version (:obj:`int` | :obj:`str`): Use to specify the version of telegrams Markdown.
            Either ``1`` or ``2``. Defaults to ``2``.
        entity_type (:obj:`str`, optional): For the entity types ``PRE``, ``CODE`` and the link
            part of ``TEXT_LINKS``, only certain characters need to be escaped in ``MarkdownV2``.
            See the official API documentation for details. Only valid in combination with
            ``version=2``, will be ignored else.
    """
    if text is None:
        return None
    if int(version) == 1:
        escape_chars = r"_*`["
    elif int(version) == 2:
        if entity_type in ["pre", "code"]:
            escape_chars = r"\`"
        elif entity_type == "text_link":
            escape_chars = r"\)"
        else:
            escape_chars = r"_*[]()~`>#+=|{}!"
    elif int(version) == 3:
        escape_chars = r"-."
    else:
        raise ValueError("Markdown version must be either 1 or 2 or 3!")
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)
