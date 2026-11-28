import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends
from psycopg import errors as pg

from .. import config
from ..db import get_conn
from ..errors import ApiError
from ..schemas import LoginIn, RegisterIn
from ..security import create_token, current_staff, hash_password, is_hashed, verify_password
from ..services import audit, normalize_phone
from .driver_requests import create_driver_account

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Failed sign-in attempts per phone number / email (kept in memory, so it resets when the server restarts).
_failures: dict[str, deque] = defaultdict(deque)

NOT_ACTIVE = {
    "pending": "Your account is waiting for the station manager's approval",
    "rejected": "Your registration was not approved. Please contact the station manager",
}


def _check_not_locked(key: str):
    now, attempts = time.monotonic(), _failures[key]
    while attempts and now - attempts[0] > config.LOGIN_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= config.LOGIN_MAX_FAILURES:
        raise ApiError(429, "Too many wrong attempts. Please wait a few minutes and try again")


def _session(row: dict) -> dict:
    return {
        "token": create_token(row["staff_id"], row["role"]),
        "name": row["full_name"],
        "role": row["role"],
        "staff_id": row["staff_id"],
    }


@router.post("/login")
def login(body: LoginIn, conn=Depends(get_conn, scope="function")):
    """Sign in with the phone number the account was registered with, or with its email."""
    entered = (body.login or body.email).strip()
    if "@" in entered:
        key = entered.lower()
        where, value = "lower(email) = %s", key
    else:
        key = normalize_phone(entered)
        where, value = "phone_number = %s", key
    _check_not_locked(key)
    row = conn.execute(
        f"SELECT staff_id, full_name, role, password_hash, account_status FROM staff WHERE {where}", (value,)
    ).fetchone()

    # An account of another role (e.g. station manager details on the Mate page) is treated exactly
    # like wrong details, so the message never tells anyone what role an account has.
    wrong_role = bool(row and body.role and row["role"] != body.role)
    if not row or wrong_role or not verify_password(body.password, row["password_hash"]):
        _failures[key].append(time.monotonic())
        audit(conn, row["staff_id"] if row else None, "LOGIN_FAILED", "staff",
              row["staff_id"] if row else None, {"login": key, **({"chose_role": body.role} if wrong_role else {})})
        conn.commit()  # keep the audit record even though we return an error
        raise ApiError(401, "Wrong phone number, email or password")
    if row["account_status"] != "active":
        raise ApiError(403, NOT_ACTIVE.get(row["account_status"],
                                           "This account is not active. Please contact the station manager"))

    _failures.pop(key, None)
    if not is_hashed(row["password_hash"]):
        # Upgrade plain-text sample passwords to a secure hash the first time they are used.
        conn.execute("UPDATE staff SET password_hash = %s WHERE staff_id = %s",
                     (hash_password(body.password), row["staff_id"]))
    conn.execute("UPDATE staff SET last_login = CURRENT_TIMESTAMP WHERE staff_id = %s", (row["staff_id"],))
    audit(conn, row["staff_id"], "LOGIN", "staff", row["staff_id"])
    return _session(row)


@router.post("/register", status_code=201)
def register(body: RegisterIn, conn=Depends(get_conn, scope="function")):
    """A station staff member or station manager creates an account with a phone number (or email)
    and a password. By default the account waits for a station manager's approval."""
    phone = normalize_phone(body.phone_number) if body.phone_number else None
    email = body.email.lower() if body.email else None
    if body.role == "driver":
        # Drivers always wait for the station manager, who approves them on the Drivers tab.
        return create_driver_account(conn, body, phone, hash_password(body.password))
    if phone and conn.execute("SELECT 1 FROM staff WHERE phone_number = %s", (phone,)).fetchone():
        raise ApiError(409, "An account with this phone number already exists. Please log in instead")
    if email and conn.execute("SELECT 1 FROM staff WHERE lower(email) = %s", (email,)).fetchone():
        raise ApiError(409, "An account with this email already exists. Please log in instead")

    status = "pending" if config.STAFF_SIGNUP_NEEDS_APPROVAL else "active"
    try:
        row = conn.execute(
            "INSERT INTO staff (full_name, email, phone_number, password_hash, role, account_status) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING staff_id, full_name, role, account_status",
            (body.full_name, email, phone, hash_password(body.password), body.role, status),
        ).fetchone()
    except pg.UniqueViolation:  # two registrations at the same moment
        raise ApiError(409, "An account with this phone number or email already exists. Please log in instead")
    audit(conn, row["staff_id"], "STAFF_REGISTERED", "staff", row["staff_id"], {"role": body.role})

    if status == "pending":
        return {"account_status": "pending", "staff_id": row["staff_id"],
                "message": "Account created. The station manager must approve it before you can log in"}
    return {"account_status": "active", "message": "Account created", **_session(row)}


@router.get("/me")
def me(staff=Depends(current_staff)):
    return staff
