"""app/api/employees.py — Employee management endpoints (enroll, list, delete)."""

import logging
from fastapi import APIRouter, Request, HTTPException

from app.models.schemas import (
    EmployeeEnrollRequest,
    EmployeeEnrollResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
def list_employees(request: Request):
    """List all enrolled employees."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Oracle DB is not configured.")

    employees = db.get_all_employees()
    return {"total": len(employees), "employees": employees}


@router.post("/enroll", response_model=EmployeeEnrollResponse)
def enroll_employee(body: EmployeeEnrollRequest, request: Request):
    """
    Disabled in this build: facial enrollment is handled externally by the AI camera.
    This API no longer stores face encodings.
    """
    raise HTTPException(
        status_code=501,
        detail="Employee facial enrollment is disabled; manage identities on the camera side.",
    )


@router.delete("/{employee_code}")
def delete_employee(employee_code: str, request: Request):
    """Remove an employee from the system."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Oracle DB is not configured.")

    if employee_code not in db.employees:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_code}' not found.")

    try:
        db.delete_employee(employee_code)
        return {"success": True, "message": f"Employee '{employee_code}' removed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload-encodings")
def reload_encodings(request: Request):
    """Manually trigger a reload of all employee encodings from Oracle DB."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Oracle DB is not configured.")

    try:
        db.load_encodings()
        return {
            "success": True,
            "message": f"Reloaded {len(db.employees)} employee encodings.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
