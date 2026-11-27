"""New staff accounts waiting for approval.

Station staff and station managers register on the dashboard. (Mates are not staff;
they use the separate mate app.) Their account stays
'pending' until a station manager approves it ('active') or rejects it ('rejected').
"""
from typing import Literal

from fastapi import APIRouter, Depends

from ..db import get_conn
from ..errors import ApiError
from ..schemas import RejectIn
from ..security import require_manager
from ..services import audit

router = APIRouter(prefix="/staff/accounts", tags=["Staff accounts"])

ACCOUNT_SQL = """
SELECT s.staff_id, s.full_name, s.phone_number, s.email, s.role, s.account_status, s.reject_reason,
       s.created_at, s.reviewed_at, r.full_name AS reviewed_by_name
FROM staff s
LEFT JOIN staff r ON r.staff_id = s.reviewed_by
"""


@router.get("")
def list_accounts(
    status: Literal["pending", "active", "rejected"] = "pending",
    staff=Depends(require_manager),
    conn=Depends(get_conn, scope="function"),
):
    order = "ASC" if status == "pending" else "DESC"  # oldest waiting account first
    return conn.execute(
        ACCOUNT_SQL + f" WHERE s.account_status = %s ORDER BY s.created_at {order}, s.staff_id {order}", (status,)
    ).fetchall()


def _pending(conn, staff_id: int) -> dict:
    row = conn.execute("SELECT * FROM staff WHERE staff_id = %s FOR UPDATE", (staff_id,)).fetchone()
    if not row:
        raise ApiError(404, "Account not found")
    if row["account_status"] != "pending":
        raise ApiError(409, "This account is not waiting for approval")
    return row


@router.post("/{staff_id}/approve")
def approve_account(staff_id: int, staff=Depends(require_manager), conn=Depends(get_conn, scope="function")):
    _pending(conn, staff_id)
    conn.execute(
        "UPDATE staff SET account_status = 'active', reject_reason = NULL, reviewed_by = %s, "
        "reviewed_at = CURRENT_TIMESTAMP WHERE staff_id = %s",
        (staff["staff_id"], staff_id),
    )
    audit(conn, staff["staff_id"], "STAFF_APPROVED", "staff", staff_id)
    return conn.execute(ACCOUNT_SQL + " WHERE s.staff_id = %s", (staff_id,)).fetchone()


@router.post("/{staff_id}/reject")
def reject_account(staff_id: int, body: RejectIn, staff=Depends(require_manager),
                   conn=Depends(get_conn, scope="function")):
    _pending(conn, staff_id)
    conn.execute(
        "UPDATE staff SET account_status = 'rejected', reject_reason = %s, reviewed_by = %s, "
        "reviewed_at = CURRENT_TIMESTAMP WHERE staff_id = %s",
        (body.reason or None, staff["staff_id"], staff_id),
    )
    audit(conn, staff["staff_id"], "STAFF_REJECTED", "staff", staff_id,
          {"reason": body.reason} if body.reason else None)
    return conn.execute(ACCOUNT_SQL + " WHERE s.staff_id = %s", (staff_id,)).fetchone()
