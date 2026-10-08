# Tests for authentication dependencies:
#
# 1. Valid access token is accepted
# 2. Refresh token is rejected as an access token
# 3. Invalid token is rejected
# 4. Tampered token is rejected
# 5. Token without user ID is rejected
# 6. Token without email is rejected
# 7. Admin role is correctly recognized
# 8. Normal user role is correctly recognized
# 9. Admin is allowed by require_admin
# 10. Super admin is allowed by require_admin
# 11. Normal user is rejected by require_admin
# 12. Super admin is allowed by require_super_admin
# 13. Admin is rejected by require_super_admin
# 14. Normal user is rejected by require_super_admin
# 15. Expired access token is rejected
import pytest
from jose import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from auth.dependencies import get_current_user
from auth.jwt import (
    SECRET_KEY,
    ALGORITHM,
    create_access_token,
    create_refresh_token,
)


def make_credentials(token: str):
    return HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token
    )


# ============================================================
# VALID ACCESS TOKEN
# ============================================================

def test_get_current_user_with_valid_access_token():

    token = create_access_token(
        user_id="123",
        email="test@example.com",
        role="user"
    )

    credentials = make_credentials(token)

    current_user = get_current_user(credentials)

    assert current_user["id"] == "123"
    assert current_user["email"] == "test@example.com"
    assert current_user["role"] == "user"


# ============================================================
# REFRESH TOKEN SHOULD BE REJECTED
# ============================================================

def test_refresh_token_cannot_authenticate_user():

    refresh_token, _ = create_refresh_token(
        user_id="123",
        email="test@example.com"
    )

    credentials = make_credentials(refresh_token)

    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token type"


# ============================================================
# INVALID TOKEN
# ============================================================

def test_invalid_token():

    credentials = make_credentials(
        "this-is-not-a-valid-jwt"
    )

    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid or expired token"


# ============================================================
# TAMPERED TOKEN
# ============================================================

def test_tampered_access_token():

    token = create_access_token(
        user_id="123",
        email="test@example.com",
        role="user"
    )

    # Change the last character of the signature
    tampered_token = token[:-1] + (
        "x" if token[-1] != "x" else "y"
    )

    credentials = make_credentials(tampered_token)

    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid or expired token"


# ============================================================
# MISSING USER ID
# ============================================================

def test_token_without_user_id():

    payload = {
        "email": "test@example.com",
        "role": "user",
        "type": "access"
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    credentials = make_credentials(token)

    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid authentication token"


# ============================================================
# MISSING EMAIL
# ============================================================

def test_token_without_email():

    payload = {
        "sub": "123",
        "role": "user",
        "type": "access"
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    credentials = make_credentials(token)

    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid authentication token"


# ============================================================
# ADMIN ACCESS
# ============================================================

def test_require_admin_with_admin_user():

    token = create_access_token(
        user_id="123",
        email="admin@example.com",
        role="admin"
    )

    credentials = make_credentials(token)

    current_user = get_current_user(credentials)

    assert current_user["role"] == "admin"


# ============================================================
# NORMAL USER IS NOT ADMIN
# ============================================================

def test_normal_user_role():

    token = create_access_token(
        user_id="123",
        email="user@example.com",
        role="user"
    )

    credentials = make_credentials(token)

    current_user = get_current_user(credentials)

    assert current_user["role"] == "user"
from auth.dependencies import require_admin, require_super_admin


def test_require_admin_allows_admin():
    current_user = {
        "id": "123",
        "email": "admin@example.com",
        "role": "admin"
    }

    result = require_admin(current_user)

    assert result == current_user


def test_require_admin_allows_super_admin():
    current_user = {
        "id": "123",
        "email": "superadmin@example.com",
        "role": "super_admin"
    }

    result = require_admin(current_user)

    assert result == current_user


def test_require_admin_rejects_normal_user():
    current_user = {
        "id": "123",
        "email": "user@example.com",
        "role": "user"
    }

    with pytest.raises(HTTPException) as exc:
        require_admin(current_user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Admin access required"


def test_require_super_admin_allows_super_admin():
    current_user = {
        "id": "123",
        "email": "superadmin@example.com",
        "role": "super_admin"
    }

    result = require_super_admin(current_user)

    assert result == current_user


def test_require_super_admin_rejects_admin():
    current_user = {
        "id": "123",
        "email": "admin@example.com",
        "role": "admin"
    }

    with pytest.raises(HTTPException) as exc:
        require_super_admin(current_user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Super admin access required"


def test_require_super_admin_rejects_normal_user():
    current_user = {
        "id": "123",
        "email": "user@example.com",
        "role": "user"
    }

    with pytest.raises(HTTPException) as exc:
        require_super_admin(current_user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Super admin access required"
from datetime import datetime, timedelta, timezone
# ============================================================
# EXPIRED ACCESS TOKEN
# ============================================================

def test_expired_access_token():

    expired_time = (
        datetime.now(timezone.utc)
        - timedelta(minutes=5)
    )

    payload = {
        "sub": "123",
        "email": "test@example.com",
        "role": "user",
        "type": "access",
        "exp": expired_time
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    credentials = make_credentials(token)

    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid or expired token"