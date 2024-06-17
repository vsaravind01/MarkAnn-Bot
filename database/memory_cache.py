from datetime import datetime

from telegram import User

from database.user_db import UserDB


class MemoryCache:
    def __init__(self, user: User, db: UserDB):
        self.cache: set[str] = set()
        self.user = user
        self.db = db

        self.init_cache()

    def __contains__(self, item_id: str):
        return item_id in self.cache

    def init_cache(self):
        if self.db.get_user(user_id=str(self.user.id)) is None:
            self.db.create_user(user_id=str(self.user.id), username=self.user.username)
        for item in self.db.get_messages(
            user_id=str(self.user.id), date=datetime.today()
        ):
            self.cache.add(str(item.id))

    def add(self, item_id: str):
        self.cache.add(item_id)
        self.db.create_message(message_id=item_id, user_id=str(self.user.id))

    def remove(self, item_id: str):
        self.cache.remove(item_id)
