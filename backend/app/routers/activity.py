from fastapi import APIRouter, Depends, Query

from ..db import get_conn
from ..security import require_manager

router = APIRouter(tags=["Activity log"])


@router.get("/activity")
def activity(limit: int = Query(50, ge=1, le=500), staff=Depends(require_manager), conn=Depends(get_conn, scope="function")):
    """Who did what and when (station manager only)."""
    return conn.execute(
        """SELECT a.audit_id, a.created_at, a.action, a.entity_name, a.entity_id, a.details,
                  s.full_name AS staff_name
           FROM audit_log a LEFT JOIN staff s ON s.staff_id = a.staff_id
           ORDER BY a.created_at DESC, a.audit_id DESC LIMIT %s""",
        (limit,),
    ).fetchall()
