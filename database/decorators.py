import os
from typing import Callable, Optional

from alembic import command, config

from database.vector_db import VectorDB


def document_existence_check(func: Callable[[object, str], Optional[dict]]):
    """Decorator to check if the document is already present in the database."""

    def wrapper(*args):
        db: VectorDB = args[0].db
        text: str = args[1]

        result = db.search(text)
        score = result[0].score
        if score > 0.95:
            return None
        else:
            return func(*args)

    return wrapper


def run_migration(func: Callable):
    """Decorator to run the migration before running the function."""

    def wrapper(*args, **kwargs):
        alembic_config = config.Config(os.path.dirname(__file__) + "/alembic.ini")
        command.upgrade(alembic_config, "head")
        return func(*args, **kwargs)

    return wrapper
