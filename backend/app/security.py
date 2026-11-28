"""Passwords, tokens and role checks."""
import hmac
import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Request
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


# Mates (conductors) and drivers have their own apps, so each may only call what their app needs.
# Station staff and station managers are not limited here (managers are checked by require_manager).
ROLE_LIMITS = {
    "mate": ("Mates can only book and cancel seats", [
        ("GET", re.compile(r"^/auth/me$")),
        ("GET", re.compile(r"^/vehicles$")),
        ("POST", re.compile(r"^/vehicles/\d+/(book|release)-seats$")),
    ]),
    "driver": ("Drivers can only see their own vehicles", [
        ("GET", re.compile(r"^/auth/me$")),
        ("GET", re.compile(r"^/driver/me$")),
        ("POST", re.compile(r"^/tracking/position$")),  # only for their own vehicle, checked there
    ]),
}


def current_staff(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                  conn=Depends(get_conn, scope="function")) -> dict:
    """Requires a valid token for an active account (station staff, station manager, mate or driver)."""
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
    if row["role"] in ROLE_LIMITS:
        message, allowed = ROLE_LIMITS[row["role"]]
        if not any(request.method == method and pattern.match(request.url.path) for method, pattern in allowed):
            raise ApiError(403, message)
    return {"staff_id": row["staff_id"], "name": row["full_name"], "role": row["role"]}


def require_manager(staff: dict = Depends(current_staff)) -> dict:
    if staff["role"] != "station_manager":
        raise ApiError(403, "Only a station manager can do this")
    return staff
