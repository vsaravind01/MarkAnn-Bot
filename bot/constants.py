import os

BOT_USERNAME = os.getenv("BOT_USERNAME")
TOKEN = os.getenv("TELEGRAM_API_KEY")


# Command Messages
LIVE_STARTED_MESSAGE = "You have subscribed to live announcements!📢"

START_MESSAGE = """Hi {first_name} {last_name}, I'm MarkAnn Bot.
I provide live stock market press release announcements. Click the button below to go live!"""

STOP_MESSAGE = "Your live will end in few minutes. You will be notified when it ends.\n\nHave a great day!✨"

HELP_MESSAGE = """
You can control me by sending these commands:

/start - Subscribe to live announcements
/stop - Stop the live announcements
"""

ALREADY_SUBSCRIBED_MESSAGE = (
    "Dear {first_name} {last_name}, You are already subscribed to live announcements."
)

NOT_SUBSCRIBED_MESSAGE = """You are not subscribed to any live announcements.

/start - Subscribe to live announcements
"""

LIVE_END_MESSAGE = "Live Ended!"

ERROR_MESSAGE = "An error occurred. Please try again later."

GO_LIVE_MESSAGE = "Go Live"


# Service Messages
PRESS_RELEASE_MESSAGE_TEMPLATE = """
*{ann_type}* from {company} at {time}
*Date:* {date}

*company:* {company}
*value:* {value}

{description}

*Attachment*: [Report PDF](https://www.bseindia.com/xml-data/corpfiling/AttachLive/{pdf_link})\n
*BSE Link*: [BSE]({bse_link})\n"""
