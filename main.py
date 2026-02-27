"""
Face Recognition Attendance System — FastAPI Entry Point
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

# Shared service instances (attached to app.state)
mqtt_service: MQTTService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    global mqtt_service

    logger.info("Starting up Attendance System...")

    # Connect to Oracle DB and load encodings
    db = OracleDB(settings.oracle)
    db.connect()
    db.load_encodings()
    app.state.db = db

    # Start MQTT service in background
    mqtt_service = MQTTService(settings.mqtt, db, settings.face, settings.excel)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, mqtt_service.start)
    app.state.mqtt = mqtt_service

    logger.info("System is live and listening for camera frames.")
    yield

    # Shutdown
    logger.info("Shutting down...")
    if mqtt_service:
        mqtt_service.stop()
    db.close()


app = FastAPI(
    title="Face Recognition Attendance System",
    description="MQTT-based face recognition attendance tracker with Oracle DB and Excel export.",
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
