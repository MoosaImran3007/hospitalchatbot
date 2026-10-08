# Tests for JWT token creation:
#
# 1. Access token is created successfully
# 2. Access token contains correct payload fields
# 3. Refresh token is created successfully with expiry
# 4. Refresh token contains correct payload fields
from jose import jwt

from auth.jwt import (
    SECRET_KEY,
    ALGORITHM,
    create_access_token,
    create_refresh_token,
)


def test_create_access_token():

    token = create_access_token(
        user_id="123",
        email="test@example.com",
        role="user"
    )

    assert token is not None
    assert isinstance(token, str)


def test_access_token_payload():

    token = create_access_token(
        user_id="123",
        email="test@example.com",
        role="user"
    )

    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM]
    )

    assert payload["sub"] == "123"
    assert payload["email"] == "test@example.com"
    assert payload["role"] == "user"
    assert payload["type"] == "access"


def test_create_refresh_token():

    token, expire = create_refresh_token(
        user_id="123",
        email="test@example.com"
    )

    assert token is not None
    assert isinstance(token, str)
    assert expire is not None


def test_refresh_token_payload():

    token, _ = create_refresh_token(
        user_id="123",
        email="test@example.com"
    )

    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM]
    )

    assert payload["sub"] == "123"
    assert payload["email"] == "test@example.com"
    assert payload["type"] == "refresh"