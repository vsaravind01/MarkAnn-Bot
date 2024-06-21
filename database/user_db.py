from datetime import datetime
from typing import Optional, Type

import pytz
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class UserSchema(Base):
    __tablename__ = "users"

    id = sqlalchemy.Column(sqlalchemy.String, primary_key=True)
    username = sqlalchemy.Column(sqlalchemy.String)
    last_updated = sqlalchemy.Column(sqlalchemy.DateTime, default=sqlalchemy.func.now())

    def __repr__(self):
        return f"User(id={self.id}, username={self.username}, last_updated={self.last_updated})"

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "last_updated": self.last_updated,
        }

    @staticmethod
    def from_dict(data: dict) -> "UserSchema":
        return UserSchema(
            id=data["id"],
            username=data["username"],
            last_updated=data["last_updated"],
        )

    def update(self, data: dict):
        self.username = data.get("username", self.username)
        self.last_updated = data.get("last_updated", self.last_updated)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "last_updated": self.last_updated.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @staticmethod
    def from_json(data) -> "UserSchema":
        return UserSchema(
            id=data["id"],
            username=data["username"],
            last_updated=datetime.strptime(data["last_updated"], "%Y-%m-%d %H:%M:%S"),
        )


class UserMessageSchema(Base):
    __tablename__ = "user_messages"

    id = sqlalchemy.Column(sqlalchemy.String, primary_key=True)
    user_id = sqlalchemy.Column(
        sqlalchemy.String, sqlalchemy.ForeignKey("users.id"), primary_key=True
    )
    timestamp = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.now)
    user = relationship("UserSchema", backref="messages")

    def __repr__(self):
        return f"UserMessage(id={self.id}, user_id={self.user_id}, timestamp={self.timestamp})"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(data) -> "UserMessageSchema":
        return UserMessageSchema(
            id=data["id"],
            user_id=data["user_id"],
            timestamp=data["timestamp"],
        )

    def update(self, data):
        self.user_id = data.get("user_id", self.user_id)
        self.timestamp = data.get("timestamp", self.timestamp)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @staticmethod
    def from_json(data) -> "UserMessageSchema":
        return UserMessageSchema(
            id=data["id"],
            user_id=data["user_id"],
            timestamp=datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S"),
        )


class UserDB:
    def __init__(self, db_url: str):
        self.engine = sqlalchemy.create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sqlalchemy.orm.sessionmaker(bind=self.engine)

    def __del__(self):
        self.close()

    def create_user(self, user_id: str, username: str) -> UserSchema:
        session = self.Session()
        user = UserSchema(id=user_id, username=username)
        session.add(user)
        session.commit()
        session.close()
        return user

    def get_user(self, user_id: str) -> Type[UserSchema]:
        session = self.Session()
        user = session.query(UserSchema).filter_by(id=user_id).first()
        session.close()
        return user

    def get_users(self) -> list[Type[UserSchema]]:
        session = self.Session()
        users = session.query(UserSchema).all()
        session.close()
        return users

    def update_user(self, user_id: str, data: dict) -> UserSchema:
        session = self.Session()
        user: Optional[UserSchema] = (
            session.query(UserSchema).filter_by(id=user_id).first()
        )
        assert user is not None, f"User with id {user_id} not found"
        user.update(data=data)
        session.commit()
        session.close()
        return user

    def delete_user(self, user_id: str) -> None:
        session = self.Session()
        user = session.query(UserSchema).filter_by(id=user_id).first()
        session.delete(user)
        session.commit()
        session.close()

    def create_message(self, message_id: str, user_id: str) -> UserMessageSchema:
        session = self.Session()
        user_message = UserMessageSchema(
            id=message_id,
            user_id=user_id,
            timestamp=datetime.now(tz=pytz.timezone("Asia/Kolkata")).replace(
                tzinfo=None
            ),
        )
        session.add(user_message)
        session.commit()
        session.close()
        return user_message

    def get_messages(
        self, user_id: str, date: datetime = None
    ) -> list[Type[UserMessageSchema]]:
        session = self.Session()
        filter_ = UserMessageSchema.user_id == user_id
        if date is not None:
            # check only for date, not time
            filter_ = sqlalchemy.and_(
                filter_,
                sqlalchemy.func.date(UserMessageSchema.timestamp)
                == date.astimezone(tz=pytz.timezone("Asia/Kolkata")).date(),
            )
        messages = session.query(UserMessageSchema).filter(filter_).all()
        session.close()
        return messages

    def delete_messages(self, user_id) -> None:
        session = self.Session()
        messages = session.query(UserMessageSchema).filter_by(user_id=user_id).all()
        for message in messages:
            session.delete(message)
        session.commit()
        session.close()

    def check_message_sent_to_user(self, user_id: str, message_id: str) -> bool:
        session = self.Session()
        message = (
            session.query(UserMessageSchema)
            .filter_by(user_id=user_id, id=message_id)
            .first()
        )
        session.close()
        return message is not None

    def exclude_messages_sent_to_user(
        self, user_id: str, message_ids: list[str]
    ) -> list[str]:
        session = self.Session()
        messages = session.query(UserMessageSchema).filter_by(user_id=user_id).all()
        message_ids = set(message_ids)
        filtered_messages = [
            str(message.id) for message in messages if message.id not in message_ids
        ]
        session.close()
        return filtered_messages

    def close(self):
        self.engine.dispose()
