import jwt
import pytest

from gateway.auth.tokens import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_token,
)
from gateway.config import Settings


@pytest.fixture
def cfg():
    return Settings(
        jwt_secret="test-secret-exactly-32-bytes-here!",
        jwt_ttl_minutes=15,
        database_url="sqlite+aiosqlite:///:memory:",
    )


def test_create_and_decode_access_token(cfg):
    token = create_access_token(user_id=1, role="trader", email="a@b.com", settings=cfg)
    payload = decode_access_token(token, cfg)
    assert payload["user_id"] == 1
    assert payload["role"] == "trader"
    assert payload["email"] == "a@b.com"


def test_expired_token_raises(cfg):
    expired_cfg = Settings(
        jwt_secret="test-secret-exactly-32-bytes-here!",
        jwt_ttl_minutes=-1,
        database_url="sqlite+aiosqlite:///:memory:",
    )
    token = create_access_token(user_id=1, role="trader", email="a@b.com", settings=expired_cfg)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, cfg)


def test_wrong_secret_raises(cfg):
    token = create_access_token(user_id=1, role="trader", email="a@b.com", settings=cfg)
    bad_cfg = Settings(
        jwt_secret="completely-different-secret-32-b!",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, bad_cfg)


def test_generate_refresh_token_unique():
    token1 = generate_refresh_token()
    token2 = generate_refresh_token()
    assert token1 != token2
    assert len(token1) > 20


def test_hash_token_deterministic():
    token = generate_refresh_token()
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token
