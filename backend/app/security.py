"""Passwords, tokens and role checks."""
import hmac
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config
from .db import get_conn
from .errors import ApiError

bearer = HTTPBearer(auto_error=False)
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def is_hashed(stored: str) -> bool:
    return stored.startswith(_BCRYPT_PREFIXES)


def verify_password(plain: str, stored: str) -> bool:
    if is_hashed(stored):
        try:
            return bcrypt.checkpw(plain.encode(), stored.encode())
        except ValueError:
            return False
    # The team's sample data stores demo passwords in plain text. They are accepted once and then
    # re-hashed automatically at login (see routers/auth.py), so no plain text stays in the database.
    return hmac.compare_digest(plain.encode(), stored.encode())


def create_token(staff_id: int, role: str) -> str:
    payload = {
        "staff_id": staff_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")

def create_passenger_token(passenger_id: int) -> str:
    payload = {
        "passenger_id": passenger_id,
        "account_type": "passenger",
        "exp": datetime.now(timezone.utc)
        + timedelta(hours=config.JWT_EXPIRE_HOURS),
    }

    return jwt.encode(
        payload,
        config.JWT_SECRET,
        algorithm="HS256"
    )

def current_staff(creds: HTTPAuthorizationCredentials | None = Depends(bearer), conn=Depends(get_conn)) -> dict:
    """Requires a valid token for an active staff account."""
    if creds is None:
        raise ApiError(401, "Please sign in")
    try:
        payload = jwt.decode(creds.credentials, config.JWT_SECRET, algorithms=["HS256"])
        staff_id = int(payload["staff_id"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise ApiError(401, "Your session has expired. Please sign in again")
    row = conn.execute(
        "SELECT staff_id, full_name, role, account_status FROM staff WHERE staff_id = %s", (staff_id,)
    ).fetchone()
    if not row or row["account_status"] != "active":
        raise ApiError(401, "Your session has expired. Please sign in again")
    return {"staff_id": row["staff_id"], "name": row["full_name"], "role": row["role"]}

def current_commuter(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    conn=Depends(get_conn)
) -> dict:
    """Requires a valid token for an active commuter account."""

    if creds is None:
        raise ApiError(401, "Please sign in")

    try:
        payload = jwt.decode(
            creds.credentials,
            config.JWT_SECRET,
            algorithms=["HS256"]
        )

        staff_id = int(payload["staff_id"])
        token_role = payload["role"]

    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise ApiError(
            401,
            "Your session has expired. Please sign in again"
        )

    if token_role != "commuter":
        raise ApiError(403, "Only a commuter can access this feature")

    row = conn.execute(
        """
        SELECT staff_id, full_name, role, account_status
        FROM staff
        WHERE staff_id = %s
        """,
        (staff_id,)
    ).fetchone()

    if (
        not row
        or row["account_status"] != "active"
        or row["role"] != "commuter"
    ):
        raise ApiError(
            401,
            "Your commuter account is not active. Please sign in again"
        )

    return {
        "staff_id": row["staff_id"],
        "passenger_subject": str(row["staff_id"]),
        "name": row["full_name"],
        "role": row["role"]
    }

def current_passenger(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    conn=Depends(get_conn)
) -> dict:
    """Requires a valid token for an active passenger account."""

    if creds is None:
        raise ApiError(401, "Please sign in")

    try:
        payload = jwt.decode(
            creds.credentials,
            config.JWT_SECRET,
            algorithms=["HS256"]
        )

        passenger_id = int(payload["passenger_id"])
        account_type = payload["account_type"]

    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise ApiError(
            401,
            "Your session has expired. Please sign in again"
        )

    if account_type != "passenger":
        raise ApiError(403, "Only passengers can access this feature")

    row = conn.execute(
        """
        SELECT passenger_id, full_name, account_status
        FROM passengers
        WHERE passenger_id = %s
        """,
        (passenger_id,)
    ).fetchone()

    if not row or row["account_status"] != "active":
        raise ApiError(
            401,
            "Your passenger account is not active. Please sign in again"
        )

    return {
        "passenger_id": row["passenger_id"],
        "passenger_subject": str(row["passenger_id"]),
        "name": row["full_name"],
        "role": "passenger"
    }

def require_manager(staff: dict = Depends(current_staff)) -> dict:
    if staff["role"] != "station_manager":
        raise ApiError(403, "Only a station manager can do this")
    return staff
