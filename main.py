"""
Attendance System — FastAPI Entry Point
Run with: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import attendance, employees, health
from app.core.config import settings
from app.core.logger import setup_logger
from app.services.mqtt_service import MQTTService
from app.db.oracle import OracleDB

setup_logger()
logger = logging.getLogger(__name__)

mqtt_service: MQTTService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    global mqtt_service

    logger.info("Starting up Attendance System...")

    db: OracleDB | None = None
    try:
        db = OracleDB(settings.oracle)
        db.connect()
        app.state.db = db
        logger.info("Oracle DB connected for employee management.")
    except Exception as exc:
        logger.error("Oracle DB unavailable; continuing without DB: %s", exc)
        app.state.db = None

    mqtt_service = MQTTService(settings.mqtt, db, settings.excel)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, mqtt_service.start)
    app.state.mqtt = mqtt_service

    logger.info("System is live and listening for MQTT attendance events.")
    yield

    logger.info("Shutting down...")
    if mqtt_service:
        mqtt_service.stop()
    if db is not None:
        db.close()


app = FastAPI(
    title="Attendance System",
    description="MQTT-based attendance tracker with Excel export.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["Attendance"])
app.include_router(employees.router, prefix="/api/employees", tags=["Employees"])
