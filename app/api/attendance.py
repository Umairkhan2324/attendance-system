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
async def verify_frame_via_api(request: Request):
    """
    Manually submit a camera frame (JPEG bytes) for face verification.
    Useful for testing without a live MQTT stream.
    Send raw JPEG bytes in the request body.
    """
    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty request body. Send JPEG bytes.")

    mqtt_svc = request.app.state.mqtt
    face_svc = mqtt_svc.face_svc
    excel_svc = mqtt_svc.excel_svc

    try:
        image = face_svc.decode_image(payload)
        matches = face_svc.verify(image)

        if not matches:
            return {"status": "no_match", "message": "No recognized face in the image."}

        results = []
        for match in matches:
            emp_code = match["employee_code"]

            if face_svc.is_on_cooldown(emp_code):
                results.append({
                    "employee_code": emp_code,
                    "status": "cooldown",
                    "message": "Already logged recently.",
                })
                continue

            emp_name = match["employee_name"]
            date_str, time_str = excel_svc.log(emp_code, emp_name)
            face_svc.set_cooldown(emp_code)

            results.append({
                "status": "verified",
                "employee_code": emp_code,
                "employee_name": emp_name,
                "date": date_str,
                "time": time_str,
                "confidence": match["confidence"],
            })

        return {"total_faces_detected": len(matches), "results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
