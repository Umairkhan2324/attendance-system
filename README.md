# Face Recognition Attendance System — FastAPI

## Project Structure

```
attendance_system/
├── main.py                          # FastAPI app entry point
├── requirements.txt
├── logs/                            # Auto-created log files
├── attendance_log.xlsx              # Auto-created on first run
└── app/
    ├── core/
    │   ├── config.py                # All configuration (env vars or edit directly)
    │   └── logger.py                # Rotating log setup
    ├── db/
    │   └── oracle.py                # Oracle DB connection + employee CRUD
    ├── models/
    │   └── schemas.py               # Pydantic request/response models
    ├── services/
    │   ├── face_service.py          # Face detection + matching logic
    │   ├── excel_service.py         # Excel attendance writer
    │   └── mqtt_service.py          # MQTT client + frame processing
    └── api/
        ├── health.py                # GET /api/health
        ├── attendance.py            # Attendance log endpoints
        └── employees.py             # Employee enroll/manage endpoints
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

> Note: `face_recognition` requires `dlib`. On Windows, install prebuilt wheels:
> https://github.com/ageitgey/face_recognition#installation

### 2. Oracle DB — create the employees table
```sql
CREATE TABLE employees (
    employee_code  VARCHAR2(50)  PRIMARY KEY,
    employee_name  VARCHAR2(100),
    face_encoding  BLOB
);
```

### 3. Configure — edit `app/core/config.py` OR set environment variables:
| Variable           | Default                  | Description                |
|--------------------|--------------------------|----------------------------|
| MQTT_BROKER        | 192.168.1.100            | MQTT broker IP             |
| MQTT_PORT          | 1883                     | MQTT broker port           |
| MQTT_USERNAME      | (empty)                  | MQTT username if auth      |
| MQTT_PASSWORD      | (empty)                  | MQTT password if auth      |
| MQTT_TOPIC_FRAME   | attendance/camera/frame  | Camera publishes here      |
| MQTT_TOPIC_RESULT  | attendance/result        | System publishes result    |
| ORACLE_USER        | your_db_user             | Oracle DB username         |
| ORACLE_PASSWORD    | your_db_password         | Oracle DB password         |
| ORACLE_DSN         | hostname:1521/servicename| Oracle DSN                 |
| FACE_TOLERANCE     | 0.5                      | Match threshold (lower=strict) |
| FACE_COOLDOWN      | 30                       | Seconds before re-logging  |
| EXCEL_FILE_PATH    | attendance_log.xlsx      | Output Excel path          |

### 4. Run the server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Endpoints

### Health
| Method | URL           | Description              |
|--------|---------------|--------------------------|
| GET    | /api/health   | System status overview   |

### Attendance
| Method | URL                         | Description                          |
|--------|-----------------------------|--------------------------------------|
| GET    | /api/attendance/            | All attendance records (from Excel)  |
| GET    | /api/attendance/recent      | Last 100 events (in-memory)          |
| GET    | /api/attendance/download    | Download Excel file                  |
| POST   | /api/attendance/verify-frame| Submit JPEG bytes for manual verify  |

### Employees
| Method | URL                              | Description                      |
|--------|----------------------------------|----------------------------------|
| GET    | /api/employees/                  | List enrolled employees          |
| POST   | /api/employees/enroll            | Enroll new employee (base64 img) |
| DELETE | /api/employees/{employee_code}   | Remove employee                  |
| POST   | /api/employees/reload-encodings  | Force reload from Oracle DB      |

### Swagger UI
Visit: http://localhost:8000/docs

---

## How the MQTT Flow Works

```
Camera (JPEG frame)
      │
      ▼  MQTT topic: attendance/camera/frame
 [MQTTService]
      │
      ├──► FaceService.verify()
      │         └── face_recognition against Oracle DB encodings
      │
      ├──► ExcelService.log()  ← writes employee_code + timestamp
      │
      └──► MQTT publish: attendance/result  ← JSON result back to camera/client
```

---

## Enrolling an Employee via API

```bash
# Convert photo to base64
base64 -i employee_photo.jpg -o photo.b64

# POST to enroll endpoint
curl -X POST http://localhost:8000/api/employees/enroll \
  -H "Content-Type: application/json" \
  -d '{
    "employee_code": "EMP001",
    "employee_name": "Ali Hassan",
    "image_base64": "<paste base64 string here>"
  }'
```
"# attendance-system" 
