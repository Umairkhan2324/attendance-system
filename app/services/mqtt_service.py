"""app/services/mqtt_service.py — MQTT client that receives attendance events and logs to Excel."""

import json
import logging
import time
import threading

import paho.mqtt.client as mqtt

from app.core.config import MQTTConfig, ExcelConfig
from app.db.oracle import OracleDB
from app.services.excel_service import ExcelService

logger = logging.getLogger(__name__)


class MQTTService:
    def __init__(
        self,
        mqtt_config: MQTTConfig,
        db: OracleDB,
        excel_config: ExcelConfig,
    ):
        self.config = mqtt_config
        self.db = db
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

        # Keep hook for potential future background work (e.g., DB sync)
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
        logger.debug(
            f"MQTT message received | topic={msg.topic} | size={len(msg.payload)}B"
        )
        try:
            data = json.loads(msg.payload.decode("utf-8"))

            emp_code = data.get("employee_code")
            if not emp_code:
                raise ValueError("MQTT payload missing 'employee_code'.")

            emp_name = data.get("employee_name") or data.get("person") or ""
            present_flag = data.get("present", True)
            status_str = "Present" if present_flag else "Absent"

            date_str, time_str = self.excel_svc.log(emp_code, emp_name, status=status_str)

            record = {
                "status": "logged",
                "employee_code": emp_code,
                "employee_name": emp_name,
                "date": date_str,
                "time": time_str,
                "presence": bool(present_flag),
            }

            with self._lock:
                self._last_detection = f"{date_str} {time_str}"
                self._recent_logs.append(record)
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
        # No-op placeholder; kept to avoid breaking existing threading setup.
        while True:
            time.sleep(300)

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
