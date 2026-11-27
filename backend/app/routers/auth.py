
import re
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends

from .. import config
from ..db import get_conn
from ..errors import ApiError
from ..schemas import LoginIn, PassengerRegisterIn, PassengerLoginIn
from ..security import (
    create_token,
    create_passenger_token,
    current_staff,
    current_passenger,
    hash_password,
    is_hashed,
    verify_password,
)
from ..services import audit

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Failed sign-in attempts per email address or phone number.
_failures: dict[str, deque] = defaultdict(deque)


def _check_not_locked(identifier: str):
    now, attempts = time.monotonic(), _failures[identifier]

    while attempts and now - attempts[0] > config.LOGIN_WINDOW_SECONDS:
        attempts.popleft()

    if len(attempts) >= config.LOGIN_MAX_FAILURES:
        raise ApiError(
            429,
            "Too many wrong attempts. Please wait a few minutes and try again",
        )


def _normalise_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)

    if digits.startswith("0"):
        digits = "233" + digits[1:]
    elif not digits.startswith("233"):
        digits = "233" + digits

    return digits


@router.post("/login")
def login(body: LoginIn, conn=Depends(get_conn)):
    if body.phone:
        identifier = _normalise_phone(body.phone)
        method = "phone"

        row = conn.execute(
            """
            SELECT staff_id, full_name, role, password_hash, account_status
            FROM staff
            WHERE regexp_replace(
                COALESCE(phone_number, ''), '[^0-9]', '', 'g'
            ) = %s
            """,
            (identifier,),
        ).fetchone()

    elif body.email:
        identifier = body.email.strip().lower()
        method = "email"

        row = conn.execute(
            """
            SELECT staff_id, full_name, role, password_hash, account_status
            FROM staff
            WHERE lower(email) = %s
            """,
            (identifier,),
        ).fetchone()

    else:
        raise ApiError(422, "Provide a phone number or email address")

    _check_not_locked(identifier)

    if not row or not verify_password(body.password, row["password_hash"]):
        _failures[identifier].append(time.monotonic())

        audit(
            conn,
            row["staff_id"] if row else None,
            "LOGIN_FAILED",
            "staff",
            row["staff_id"] if row else None,
            {"login_method": method},
        )

        conn.commit()
        raise ApiError(401, "Wrong phone number/email or password")

    if row["role"] != body.role:
        raise ApiError(403, "This account does not have the selected role")

    if row["account_status"] != "active":
        raise ApiError(
            403,
            "This account is not active. Please contact the station manager",
        )

    _failures.pop(identifier, None)

    if not is_hashed(row["password_hash"]):
        conn.execute(
            "UPDATE staff SET password_hash = %s WHERE staff_id = %s",
            (hash_password(body.password), row["staff_id"]),
        )

    conn.execute(
        "UPDATE staff SET last_login = CURRENT_TIMESTAMP WHERE staff_id = %s",
        (row["staff_id"],),
    )

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

@router.post("/passenger/register", status_code=201)
def register_passenger(
    body: PassengerRegisterIn,
    conn=Depends(get_conn)
):
    phone = _normalise_phone(body.phone_number)

    existing = conn.execute(
        """
        SELECT passenger_id
        FROM passengers
        WHERE phone_number = %s
        """,
        (phone,)
    ).fetchone()

    if existing:
        raise ApiError(409, "This phone number is already registered")

    row = conn.execute(
        """
        INSERT INTO passengers
            (full_name, phone_number, password_hash)
        VALUES (%s, %s, %s)
        RETURNING passenger_id, full_name, phone_number, account_status
        """,
        (
            body.full_name,
            phone,
            hash_password(body.password)
        )
    ).fetchone()

    conn.commit()

    return {
        "message": "Passenger account created successfully",
        "passenger": row
    }

@router.post("/passenger/login")
def passenger_login(
    body: PassengerLoginIn,
    conn=Depends(get_conn)
):
    identifier = _normalise_phone(body.phone_number)

    _check_not_locked(identifier)

    row = conn.execute(
        """
        SELECT passenger_id, full_name, phone_number,
               password_hash, account_status
        FROM passengers
        WHERE phone_number = %s
        """,
        (identifier,)
    ).fetchone()

    if not row or not verify_password(body.password, row["password_hash"]):
        _failures[identifier].append(time.monotonic())
        raise ApiError(401, "Wrong phone number or password")

    if row["account_status"] != "active":
        raise ApiError(403, "Your passenger account is not active")

    _failures.pop(identifier, None)

    conn.execute(
        """
        UPDATE passengers
        SET last_login = CURRENT_TIMESTAMP
        WHERE passenger_id = %s
        """,
        (row["passenger_id"],)
    )

    conn.commit()

    return {
        "token": create_passenger_token(row["passenger_id"]),
        "name": row["full_name"],
        "role": "passenger",
        "passenger_id": row["passenger_id"]
    }