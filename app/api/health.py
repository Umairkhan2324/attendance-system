"""app/api/health.py — System health and status endpoint."""

from fastapi import APIRouter, Request
from app.models.schemas import SystemStatusResponse

router = APIRouter()


@router.get("/health", response_model=SystemStatusResponse)
def health_check(request: Request):
    db = getattr(request.app.state, "db", None)
    mqtt = request.app.state.mqtt

    employees_loaded = len(db.employees) if db is not None else 0

    return SystemStatusResponse(
        status="ok",
        mqtt_connected=mqtt.is_connected,
        employees_loaded=employees_loaded,
        excel_file=mqtt.excel_svc.file_path,
        last_detection=mqtt.last_detection,
    )
