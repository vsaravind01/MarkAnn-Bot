from typing import Callable, Optional

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
