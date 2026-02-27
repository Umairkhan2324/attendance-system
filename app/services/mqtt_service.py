"""app/services/mqtt_service.py — MQTT client that receives frames and triggers face verification."""

import json
import logging
import time
import threading

import paho.mqtt.client as mqtt

from app.core.config import MQTTConfig, FaceConfig, ExcelConfig
from app.db.oracle import OracleDB
from app.services.face_service import FaceService
from app.services.excel_service import ExcelService

logger = logging.getLogger(__name__)


class MQTTService:
    def __init__(
        self,
        mqtt_config: MQTTConfig,
        db: OracleDB,
        face_config: FaceConfig,
        excel_config: ExcelConfig,
    ):
        self.config = mqtt_config
        self.db = db
        self.face_svc = FaceService(db, face_config)
        self.excel_svc = ExcelService(excel_config)

        self.client = mqtt.Client(client_id="attendance_fastapi_server")
        self._connected = False
        self._last_detection: str | None = None
        self._recent_logs: list[dict] = []   # in-memory cache for API reads
        self._lock = threading.Lock()

        if mqtt_config.username:
            self.client.username_pw_set(mqtt_config.username, mqtt_config.password)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # Background thread to reload DB encodings every 5 minutes
        self._reload_thread = threading.Thread(
            target=self._reload_loop, daemon=True
        )

    # ─────────────────────────────────────────
    #  MQTT Callbacks
    # ─────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            client.subscribe(self.config.topic_frame)
            logger.info(
                f"MQTT connected to {self.config.broker}:{self.config.port} | "
                f"Subscribed to '{self.config.topic_frame}'"
            )
        else:
            logger.error(f"MQTT connection failed (rc={rc})")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        logger.warning(f"MQTT disconnected (rc={rc}). Will auto-reconnect...")

    def _on_message(self, client, userdata, msg):
        logger.debug(f"Frame received | topic={msg.topic} | size={len(msg.payload)}B")
        try:
            image = self.face_svc.decode_image(msg.payload)
            matches = self.face_svc.verify(image)

            if not matches:
                self._publish({"status": "no_match", "message": "No recognized face in frame."})
                return

            for match in matches:
                emp_code = match["employee_code"]

                if self.face_svc.is_on_cooldown(emp_code):
                    logger.info(f"Cooldown active for {emp_code}. Skipping.")
                    continue

                emp_name = match["employee_name"]
                date_str, time_str = self.excel_svc.log(emp_code, emp_name)
                self.face_svc.set_cooldown(emp_code)

                record = {
                    "status": "verified",
                    "employee_code": emp_code,
                    "employee_name": emp_name,
                    "date": date_str,
                    "time": time_str,
                    "confidence": match["confidence"],
                }

                with self._lock:
                    self._last_detection = f"{date_str} {time_str}"
                    self._recent_logs.append(record)
                    # Keep only last 100 in memory
                    if len(self._recent_logs) > 100:
                        self._recent_logs.pop(0)

                self._publish(record)

        except Exception as e:
            logger.error(f"Frame processing error: {e}", exc_info=True)
            self._publish({"status": "error", "message": str(e)})

    # ─────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────

    def _publish(self, payload: dict):
        self.client.publish(self.config.topic_result, json.dumps(payload))

    def _reload_loop(self):
        while True:
            time.sleep(300)
            try:
                logger.info("Reloading employee encodings from Oracle DB...")
                self.db.load_encodings()
            except Exception as e:
                logger.error(f"Reload failed: {e}")

    # ─────────────────────────────────────────
    #  Lifecycle
    # ─────────────────────────────────────────

    def start(self):
        self._reload_thread.start()
        try:
            self.client.connect(
                self.config.broker, self.config.port, self.config.keepalive
            )
            self.client.loop_forever()
        except Exception as e:
            logger.error(f"MQTT loop error: {e}")

    def stop(self):
        self.client.disconnect()
        logger.info("MQTT service stopped.")

    # ─────────────────────────────────────────
    #  Status / Data for API
    # ─────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def last_detection(self) -> str | None:
        return self._last_detection

    def get_recent_logs(self) -> list[dict]:
        with self._lock:
            return list(self._recent_logs)
