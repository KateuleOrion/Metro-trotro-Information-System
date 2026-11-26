import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends

from .. import config
from ..db import get_conn
from ..errors import ApiError
from ..schemas import LoginIn
from ..security import create_token, current_staff, hash_password, is_hashed, verify_password
from ..services import audit

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Failed sign-in attempts per email (kept in memory, so it resets when the server restarts).
_failures: dict[str, deque] = defaultdict(deque)


def _check_not_locked(email: str):
    now, attempts = time.monotonic(), _failures[email]
    while attempts and now - attempts[0] > config.LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= config.LOGIN_MAX_FAILURES:
        raise ApiError(429, "Too many wrong attempts. Please wait a few minutes and try again")


def _normalise_phone(raw: str) -> str:
    """'024 123 4567', '+233241234567' and '233241234567' all become '+233241234567'."""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits.startswith("0"):
        digits = "233" + digits[1:]
    return "+" + digits


@router.post("/login")
def login(body: LoginIn, conn=Depends(get_conn)):
    if body.phone:
        phone = _normalise_phone(body.phone)
        key = phone
        where, value = "phone_number = %s", phone
    else:
        key = body.email.strip().lower()
        where, value = "lower(email) = %s", key
    _check_not_locked(key)
    row = conn.execute(
        f"SELECT staff_id, full_name, role, password_hash, account_status FROM staff WHERE {where}",
        (value,),
    ).fetchone()

    if not row or not verify_password(body.password, row["password_hash"]):
        _failures[key].append(time.monotonic())
        audit(conn, row["staff_id"] if row else None, "LOGIN_FAILED", "staff",
              row["staff_id"] if row else None, {"identifier": key})
        conn.commit()  # keep the audit record even though we return an error
        raise ApiError(401, "Wrong phone number, email or password")
    if body.role and row["role"] != body.role:
        label = body.role.replace("_", " ")
        raise ApiError(403, f"This account is not registered as a {label}. Choose a different role")
    if row["account_status"] != "active":
        raise ApiError(403, "This account is not active. Please contact the station manager")

    _failures.pop(key, None)
    if not is_hashed(row["password_hash"]):
        # Upgrade plain-text sample passwords to a secure hash the first time they are used.
        conn.execute("UPDATE staff SET password_hash = %s WHERE staff_id = %s",
                     (hash_password(body.password), row["staff_id"]))
    conn.execute("UPDATE staff SET last_login = CURRENT_TIMESTAMP WHERE staff_id = %s", (row["staff_id"],))
    audit(conn, row["staff_id"], "LOGIN", "staff", row["staff_id"])
    return {
        "token": create_token(row["staff_id"], row["role"]),
        "name": row["full_name"],
        "role": row["role"],
        "staff_id": row["staff_id"],
    }


@router.get("/me")
def me(staff=Depends(current_staff)):
    return staff
