"""app/services/face_service.py — Face detection and matching logic."""

import logging
import base64
import time
from io import BytesIO

import cv2
import numpy as np
import face_recognition
from PIL import Image

from app.core.config import FaceConfig
from app.db.oracle import OracleDB

logger = logging.getLogger(__name__)


class FaceService:
    def __init__(self, db: OracleDB, config: FaceConfig):
        self.db = db
        self.config = config
        self._cooldown_tracker: dict[str, float] = {}

    # ─────────────────────────────────────────
    #  Image decoding
    # ─────────────────────────────────────────

    def decode_image(self, payload: bytes) -> np.ndarray:
        """Accept raw JPEG bytes or base64-encoded image. Returns RGB numpy array."""
        # Try raw JPEG
        nparr = np.frombuffer(payload, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Try base64 fallback
        try:
            decoded = base64.b64decode(payload)
            nparr = np.frombuffer(decoded, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except Exception:
            pass

        raise ValueError("Unable to decode image from payload.")

    def decode_base64_image(self, b64_string: str) -> np.ndarray:
        """Decode a base64 string (from API request) to RGB numpy array."""
        # Strip data URI prefix if present
        if "," in b64_string:
            b64_string = b64_string.split(",", 1)[1]
        raw = base64.b64decode(b64_string)
        pil_img = Image.open(BytesIO(raw)).convert("RGB")
        return np.array(pil_img)

    # ─────────────────────────────────────────
    #  Face encoding extraction
    # ─────────────────────────────────────────

    def extract_encoding(self, image: np.ndarray) -> np.ndarray:
        """Extract face encoding from an image. Raises if no face found."""
        encodings = face_recognition.face_encodings(image)
        if not encodings:
            raise ValueError("No face detected in the provided image.")
        if len(encodings) > 1:
            logger.warning("Multiple faces found; using the first detected face.")
        return encodings[0]

    # ─────────────────────────────────────────
    #  Verification
    # ─────────────────────────────────────────

    def verify(self, image: np.ndarray) -> list[dict]:
        """
        Match all faces in an image against enrolled employees.
        Returns list of: {employee_code, employee_name, confidence}
        """
        known_encodings, known_codes = self.db.get_all_encodings()
        if not known_encodings:
            logger.warning("No encodings loaded. Reload employees first.")
            return []

        face_locations = face_recognition.face_locations(image, model=self.config.model)
        if not face_locations:
            logger.debug("No faces detected in frame.")
            return []

        face_encodings = face_recognition.face_encodings(image, face_locations)
        matches = []

        for face_enc in face_encodings:
            distances = face_recognition.face_distance(known_encodings, face_enc)
            best_idx = int(np.argmin(distances))
            best_dist = float(distances[best_idx])

            if best_dist <= self.config.tolerance:
                emp_code = known_codes[best_idx]
                confidence = round((1 - best_dist) * 100, 2)
                emp_name = self.db.get_employee_name(emp_code)
                logger.info(f"Match: {emp_code} ({emp_name}) @ {confidence}% confidence")
                matches.append({
                    "employee_code": emp_code,
                    "employee_name": emp_name,
                    "confidence": confidence,
                })
            else:
                logger.info(f"No match. Closest distance: {best_dist:.3f}")

        return matches

    # ─────────────────────────────────────────
    #  Cooldown
    # ─────────────────────────────────────────

    def is_on_cooldown(self, employee_code: str) -> bool:
        last = self._cooldown_tracker.get(employee_code)
        if last and (time.time() - last) < self.config.cooldown_seconds:
            remaining = int(self.config.cooldown_seconds - (time.time() - last))
            logger.debug(f"Cooldown active for {employee_code}. {remaining}s remaining.")
            return True
        return False

    def set_cooldown(self, employee_code: str):
        self._cooldown_tracker[employee_code] = time.time()

    def clear_cooldown(self, employee_code: str):
        self._cooldown_tracker.pop(employee_code, None)
