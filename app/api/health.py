"""app/api/health.py — System health and status endpoint."""

from fastapi import APIRouter, Request
from app.models.schemas import SystemStatusResponse

router = APIRouter()


@router.get("/health", response_model=SystemStatusResponse)
def health_check(request: Request):
    db = request.app.state.db
    mqtt = request.app.state.mqtt

    return SystemStatusResponse(
        status="ok",
        mqtt_connected=mqtt.is_connected,
        employees_loaded=len(db.employees),
        excel_file=mqtt.excel_svc.file_path,
        last_detection=mqtt.last_detection,
    )
