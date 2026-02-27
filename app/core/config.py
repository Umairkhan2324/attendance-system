"""
app/core/config.py — All configuration in one place.
You can also load from a .env file using python-dotenv.
"""

from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class MQTTConfig:
    broker: str = os.getenv("MQTT_BROKER", "192.168.1.100")
    port: int = int(os.getenv("MQTT_PORT", "1883"))
    username: str = os.getenv("MQTT_USERNAME", "")
    password: str = os.getenv("MQTT_PASSWORD", "")
    topic_frame: str = os.getenv("MQTT_TOPIC_FRAME", "attendance/camera/frame")
    topic_result: str = os.getenv("MQTT_TOPIC_RESULT", "attendance/result")
    keepalive: int = 60


@dataclass
class OracleConfig:
    user: str = os.getenv("ORACLE_USER", "your_db_user")
    password: str = os.getenv("ORACLE_PASSWORD", "your_db_password")
    dsn: str = os.getenv("ORACLE_DSN", "hostname:1521/servicename")


@dataclass
class FaceConfig:
    tolerance: float = float(os.getenv("FACE_TOLERANCE", "0.5"))
    model: str = os.getenv("FACE_MODEL", "hog")   # "hog" or "cnn"
    cooldown_seconds: int = int(os.getenv("FACE_COOLDOWN", "30"))


@dataclass
class ExcelConfig:
    file_path: str = os.getenv("EXCEL_FILE_PATH", "attendance_log.xlsx")
    sheet_name: str = os.getenv("EXCEL_SHEET_NAME", "Attendance")


@dataclass
class Settings:
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    oracle: OracleConfig = field(default_factory=OracleConfig)
    face: FaceConfig = field(default_factory=FaceConfig)
    excel: ExcelConfig = field(default_factory=ExcelConfig)


settings = Settings()
