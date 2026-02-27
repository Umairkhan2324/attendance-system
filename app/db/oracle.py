"""app/db/oracle.py — Oracle DB connection and employee encoding management."""

import logging
import numpy as np
import oracledb
from app.core.config import OracleConfig

logger = logging.getLogger(__name__)


class OracleDB:
    def __init__(self, config: OracleConfig):
        self.config = config
        self.connection = None
        # {employee_code: {"name": str, "encoding": np.ndarray}}
        self.employees: dict = {}

    def connect(self):
        try:
            self.connection = oracledb.connect(
                user=self.config.user,
                password=self.config.password,
                dsn=self.config.dsn,
            )
            logger.info("Oracle DB connected.")
        except Exception as e:
            logger.error(f"Oracle DB connection error: {e}")
            raise

    def load_encodings(self):
        """Load all enrolled employee face encodings from DB into memory."""
        if not self.connection:
            self.connect()

        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT employee_code, employee_name, face_encoding FROM employees"
            )
            rows = cursor.fetchall()
            self.employees = {}
            for emp_code, emp_name, face_blob in rows:
                if face_blob:
                    encoding_bytes = (
                        face_blob.read() if hasattr(face_blob, "read") else bytes(face_blob)
                    )
                    encoding = np.frombuffer(encoding_bytes, dtype=np.float64)
                    self.employees[emp_code] = {"name": emp_name, "encoding": encoding}
            logger.info(f"Loaded {len(self.employees)} employee encodings.")
        finally:
            cursor.close()

    def get_all_encodings(self) -> tuple[list, list]:
        """Returns (encodings_list, codes_list)."""
        codes = list(self.employees.keys())
        encodings = [self.employees[c]["encoding"] for c in codes]
        return encodings, codes

    def get_employee_name(self, employee_code: str) -> str:
        return self.employees.get(employee_code, {}).get("name", "Unknown")

    def get_all_employees(self) -> list[dict]:
        return [
            {"employee_code": code, "employee_name": data["name"]}
            for code, data in self.employees.items()
        ]

    def enroll_employee(self, employee_code: str, employee_name: str, encoding: np.ndarray):
        """Insert or update an employee with their face encoding."""
        if not self.connection:
            self.connect()

        encoding_bytes = encoding.tobytes()
        blob_var = self.connection.createlob(oracledb.DB_TYPE_BLOB)
        blob_var.write(encoding_bytes)

        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                MERGE INTO employees e
                USING dual ON (e.employee_code = :emp_code)
                WHEN MATCHED THEN
                    UPDATE SET employee_name = :emp_name, face_encoding = :enc
                WHEN NOT MATCHED THEN
                    INSERT (employee_code, employee_name, face_encoding)
                    VALUES (:emp_code, :emp_name, :enc)
                """,
                emp_code=employee_code,
                emp_name=employee_name,
                enc=blob_var,
            )
            self.connection.commit()
            # Update in-memory cache too
            self.employees[employee_code] = {
                "name": employee_name,
                "encoding": encoding,
            }
            logger.info(f"Enrolled employee: {employee_code} — {employee_name}")
        finally:
            cursor.close()

    def delete_employee(self, employee_code: str):
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "DELETE FROM employees WHERE employee_code = :emp_code",
                emp_code=employee_code,
            )
            self.connection.commit()
            self.employees.pop(employee_code, None)
            logger.info(f"Deleted employee: {employee_code}")
        finally:
            cursor.close()

    def close(self):
        if self.connection:
            self.connection.close()
            logger.info("Oracle DB connection closed.")
