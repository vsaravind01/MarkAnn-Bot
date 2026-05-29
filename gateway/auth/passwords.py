from passlib.context import CryptContext

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    return _ctx.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _ctx.verify(password, hashed)
