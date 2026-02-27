"""app/models/schemas.py — Pydantic models for request/response validation."""

from pydantic import BaseModel
from typing import Optional
from datetime import date, time as time_type


class AttendanceRecord(BaseModel):
    employee_code: str
    employee_name: str
    date: str
    time: str
    confidence: float
    status: str = "Present"


class EmployeeBase(BaseModel):
    employee_code: str
    employee_name: str


class EmployeeEnrollRequest(BaseModel):
    employee_code: str
    employee_name: str
    image_base64: str  # base64 encoded JPEG/PNG


class EmployeeEnrollResponse(BaseModel):
    success: bool
    message: str
    employee_code: Optional[str] = None


class AttendanceListResponse(BaseModel):
    total: int
    records: list[AttendanceRecord]


class SystemStatusResponse(BaseModel):
    status: str
    mqtt_connected: bool
    employees_loaded: int
    excel_file: str
    last_detection: Optional[str] = None


class MQTTVerificationResult(BaseModel):
    status: str                     # "verified" | "no_match" | "error"
    employee_code: Optional[str] = None
    employee_name: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    confidence: Optional[float] = None
    message: Optional[str] = None
