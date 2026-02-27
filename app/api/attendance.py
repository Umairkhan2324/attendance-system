"""app/api/attendance.py — Attendance log endpoints."""

import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse

from app.models.schemas import AttendanceListResponse, AttendanceRecord

router = APIRouter()


@router.get("/", response_model=AttendanceListResponse)
def get_all_attendance(request: Request):
    """Return all attendance records logged to Excel (reads from Excel file)."""
    mqtt = request.app.state.mqtt
    records_raw = mqtt.excel_svc.get_all_records()

    records = [
        AttendanceRecord(
            employee_code=r["employee_code"],
            employee_name=r["employee_name"],
            date=str(r["date"]),
            time=str(r["time"]),
            confidence=0.0,   # Excel doesn't store confidence
            status=r["status"] or "Present",
        )
        for r in records_raw
    ]
    return AttendanceListResponse(total=len(records), records=records)


@router.get("/recent")
def get_recent_attendance(request: Request):
    """Return the last 100 verified attendance events (from in-memory cache)."""
    mqtt = request.app.state.mqtt
    logs = mqtt.get_recent_logs()
    return {"total": len(logs), "records": logs}


@router.get("/download")
def download_excel(request: Request):
    """Download the Excel attendance log file."""
    mqtt = request.app.state.mqtt
    file_path = mqtt.excel_svc.file_path

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Excel file not found.")

    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/verify-frame")
async def verify_frame_via_api() -> None:
    """
    Disabled in this build: face-based verification is handled upstream by the AI camera.
    Use MQTT JSON events (employee_code / employee_name / present flag) instead.
    """
    raise HTTPException(
        status_code=501,
        detail="Frame-based verification is disabled. Send attendance events via MQTT.",
    )
