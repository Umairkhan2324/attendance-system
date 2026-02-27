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
    db = request.app.state.db
    employees = db.get_all_employees()
    return {"total": len(employees), "employees": employees}


@router.post("/enroll", response_model=EmployeeEnrollResponse)
def enroll_employee(body: EmployeeEnrollRequest, request: Request):
    """
    Enroll a new employee by providing their employee code, name, and a
    base64-encoded face photo. The face encoding is saved to Oracle DB.
    """
    db = request.app.state.db
    mqtt_svc = request.app.state.mqtt
    face_svc = mqtt_svc.face_svc

    try:
        image = face_svc.decode_base64_image(body.image_base64)
        encoding = face_svc.extract_encoding(image)
        db.enroll_employee(body.employee_code, body.employee_name, encoding)

        return EmployeeEnrollResponse(
            success=True,
            message=f"Employee '{body.employee_name}' enrolled successfully.",
            employee_code=body.employee_code,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Enrollment error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enrollment failed: {str(e)}")


@router.delete("/{employee_code}")
def delete_employee(employee_code: str, request: Request):
    """Remove an employee from the system."""
    db = request.app.state.db

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
    db = request.app.state.db
    try:
        db.load_encodings()
        return {
            "success": True,
            "message": f"Reloaded {len(db.employees)} employee encodings.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
