# Hospital Appointment Management System

A REST API for managing medical appointments between patients and doctors, built with
FastAPI. The system handles user registration and authentication, role-based access
control, appointment booking with double-booking prevention, and administrative oversight
of patients, doctors, and schedules.

---

## Project Description

The system solves three problems that arise when hospital scheduling is handled manually:

- **Double booking** — a doctor can never be assigned two overlapping appointments. The
  API rejects any booking whose time interval intersects an existing one for the same
  doctor.
- **Access separation** — patients, doctors, and administrators each see a different slice
  of the data. Authorization is enforced on the server for every route, not in the client.
- **Visibility** — schedules, patient and doctor directories, and basic runtime metrics are
  all retrievable through consistent, documented endpoints.

Authentication uses JSON Web Tokens (JWT). On login the API returns a signed token that
carries the user's username and role; every protected route decodes that token, loads the
user, and checks the role before the request handler runs.

### Roles

| Role | What they can do |
|------|------------------|
| `patient` | Book appointments, cancel their own appointments, view their own schedule |
| `doctor` | View their own schedule, update appointment status (Scheduled / Completed / Cancelled) |
| `admin` | View all appointments, list and inspect patients and doctors, create and delete users |

### Features

- User registration and JWT-based login
- Role-based access control on every protected endpoint
- Appointment booking with interval-overlap (double-booking) detection
- Appointment cancellation with ownership verification
- Appointment status lifecycle management
- Patient and doctor directories for administrators
- Redis caching on read-heavy endpoints (optional — the API works without Redis)
- Request/error/latency metrics exposed at `/dashboard`
- Automatic interactive API documentation via Swagger UI and ReDoc

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Web framework | FastAPI |
| ASGI server | Uvicorn |
| ORM | SQLAlchemy |
| Database | SQLite |
| Validation | Pydantic |
| Tokens | python-jose (HS256) |
| Password hashing | passlib[bcrypt] |
| Cache | Redis (optional) |
| Testing | pytest + httpx |

---

## Setup Instructions

### Prerequisites

- Python 3.13 or later
- Redis (optional — if it is not running, caching is skipped and the API works normally)

### 1. Clone the repository

```bash
git clone https://github.com/marwanabdodahi/hospital-project.git
cd hospital-project
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The database file `hospital.db` and all its tables are created automatically on first
startup — there is no migration step.

### 5. Open the API documentation

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8000/docs | Swagger UI — send authenticated requests from the browser |
| http://127.0.0.1:8000/redoc | ReDoc rendering of the same specification |
| http://127.0.0.1:8000/openapi.json | Raw OpenAPI schema |

---

## Usage

### 1. Register a user

```bash
curl -X POST http://127.0.0.1:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username":"marwan","email":"marwan@hospital.com","password":"secret123","role":"patient"}'
```

### 2. Log in and get a token

```bash
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"marwan","password":"secret123"}'
```

Response:

```json
{ "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." }
```

### 3. Call a protected endpoint

Send the token in the `Authorization` header on every protected request:

```bash
curl -X POST http://127.0.0.1:8000/appointments \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"doctor_id":1,"patient_id":1,"start_time":"2026-09-01T10:00:00","end_time":"2026-09-01T11:00:00"}'
```

---

## API Endpoints

Full interactive documentation is generated automatically by FastAPI at `/docs`.

| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| `POST` | `/register` | public | Create a user account |
| `POST` | `/login` | public | Log in and receive a JWT |
| `POST` | `/appointments` | patient | Book an appointment |
| `DELETE` | `/appointments/{id}` | patient | Cancel own appointment |
| `PUT` | `/appointments/{id}/status` | doctor | Update appointment status |
| `GET` | `/appointments` | admin | List all appointments |
| `GET` | `/doctors/{id}/appointments` | doctor | A doctor's schedule |
| `GET` | `/patients/{id}/appointments` | patient | A patient's schedule |
| `GET` | `/patients` | admin | List all patients |
| `GET` | `/patients/{id}` | admin | Get one patient |
| `GET` | `/doctors` | admin | List all doctors |
| `POST` | `/admin/create-user` | admin | Create a user of any role |
| `DELETE` | `/admin/users/{id}` | admin | Delete a user |
| `GET` | `/dashboard` | public | Request, error, and latency metrics |

---

## Running the Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

The suite covers registration, login, token validation, role-based access, and
double-booking prevention.

---

## Project Structure

```
hospital-project/
├── app/
│   ├── main.py           # ASGI entry point, middleware, startup
│   ├── routes.py         # All API endpoints
│   ├── models.py         # SQLAlchemy ORM models
│   ├── schemas.py        # Pydantic request schemas
│   ├── db.py             # Engine, session factory, declarative base
│   ├── auth.py           # Password hashing and JWT creation
│   ├── dependencies.py   # DB session and role-based guards
│   ├── cache.py          # Redis cache helpers
│   ├── logger.py         # Application logger
│   └── monitor.py        # Request metrics
├── tests/
│   └── test_auth.py      # Functional tests
├── requirements.txt
└── README.md
```

---

## Database Schema

| Table | Description |
|-------|-------------|
| `users` | Identity records — username, email, password, role |
| `doctors` | Doctor profiles, linked to `users` |
| `patients` | Patient profiles, linked to `users` |
| `appointments` | Bookings — doctor, patient, start time, end time, status |

---

## Team Members and Roles

| # | Name | Student ID | Level | Role |
|---|------|-----------|-------|------|
| 1 | Marwan Abdo Dahi | 931250674 | Level 3 | Team Leader |
| 2 | Youssef Khaled Mohamed | 931250679 | Level 2 | Member |
| 3 | Youssef Osama Abdel-Moez | 931230358 | Level 4 | Member |
| 4 | Abdelrahman Hamed Hamdan | 931240192 | Level 3 | Member |
| 5 | Naira Qasem Sayed Ahmed | 931250514 | Level 4 | Member |

---

## License

This project was developed for academic purposes.
