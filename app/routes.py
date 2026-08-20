import threading
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password, create_token
from app.cache import cached, delete_cache
from app.dependencies import get_db, get_current_user, role_required
from app.logger import logger
from app.models import User, Appointment
from app.monitor import metrics
from app.schemas import (
    UserCreate,
    LoginSchema,
    AppointmentCreate,
    StatusUpdate,
    UserOut,
    AppointmentOut,
)

router = APIRouter()

# SQLite stores a 64-bit integer. Anything larger raises OverflowError on bind,
# so ids are bounded here and rejected with 422 instead of a server error.
MAX_ID = 2 ** 63 - 1


def IdParam():
    """A path id bounded to what SQLite can store. A fresh instance is needed
    per parameter, since FastAPI binds the parameter name onto the object."""
    return Path(ge=1, le=MAX_ID)

# The overlap check reads the table and then writes to it. Two requests that
# arrive together can both read "the slot is free" before either writes, so the
# pair is held under one lock. This covers a single-process server, which is how
# the project runs; a multi-process deployment would need a database-level lock.
booking_lock = threading.Lock()

# A cancelled appointment may be revived, but only back into an open slot.
ALLOWED_TRANSITIONS = {
    "Scheduled": {"Completed", "Cancelled"},
    "Completed": {"Scheduled"},
    "Cancelled": {"Scheduled"},
}


def create_account(data: UserCreate, db: Session, role: str) -> User:
    """Create a user with the given role, rejecting a taken username or email."""
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=data.username,
        email=data.email,
        password=hash_password(data.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def find_clash(db: Session, doctor_id: int, start, end, ignore_id: int | None = None):
    """Return an active appointment for this doctor that overlaps [start, end)."""
    query = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status != "Cancelled",
        Appointment.start_time < end,
        Appointment.end_time > start,
    )
    if ignore_id is not None:
        query = query.filter(Appointment.id != ignore_id)
    return query.first()


def clear_schedule_cache(doctor_id: int, patient_id: int):
    delete_cache(f"doctor_{doctor_id}_appointments", f"patient_{patient_id}_appointments")


# ---------------------------------------------------------------- accounts

@router.post("/register", status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """Public sign-up. Always creates a patient - staff accounts go through /admin/create-user."""
    user = create_account(data, db, role="patient")
    delete_cache("patients")
    logger.info("Registered patient %s", user.username)
    return {"msg": "registered", "id": user.id}


@router.post("/login")
def login(data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()

    if not user or not verify_password(data.password, user.password):
        logger.warning("Failed login for %s", data.username)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    logger.info("Login ok for %s (%s)", user.username, user.role)
    return {"access_token": create_token({"sub": user.username, "role": user.role})}


# ------------------------------------------------------------ appointments

@router.post("/appointments", status_code=201)
def book(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    patient: User = Depends(role_required("patient")),
):
    doctor = db.query(User).filter(User.id == data.doctor_id, User.role == "doctor").first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    with booking_lock:
        if find_clash(db, data.doctor_id, data.start_time, data.end_time):
            raise HTTPException(status_code=400, detail="Doctor is already booked at that time")

        appt = Appointment(
            doctor_id=data.doctor_id,
            patient_id=patient.id,
            start_time=data.start_time,
            end_time=data.end_time,
            status="Scheduled",
        )
        db.add(appt)
        db.commit()
        db.refresh(appt)

    clear_schedule_cache(appt.doctor_id, appt.patient_id)
    logger.info("Appointment %s booked: patient %s with doctor %s", appt.id, patient.id, doctor.id)
    return {"msg": "booked", "id": appt.id}


@router.delete("/appointments/{appointment_id}")
def cancel_appointment(
    appointment_id: int = IdParam(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """A patient may cancel their own appointment; a doctor theirs; an admin any."""
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    owns = (
        user.role == "admin"
        or (user.role == "patient" and appt.patient_id == user.id)
        or (user.role == "doctor" and appt.doctor_id == user.id)
    )
    if not owns:
        raise HTTPException(status_code=403, detail="This is not your appointment")

    if appt.status == "Cancelled":
        raise HTTPException(status_code=400, detail="Appointment is already cancelled")

    if appt.status != "Scheduled":
        raise HTTPException(
            status_code=400,
            detail=f"Only a scheduled appointment can be cancelled; this one is {appt.status}",
        )

    appt.status = "Cancelled"
    db.commit()

    clear_schedule_cache(appt.doctor_id, appt.patient_id)
    logger.info("Appointment %s cancelled by %s (%s)", appt.id, user.username, user.role)
    return {"msg": "cancelled"}


@router.put("/appointments/{appointment_id}/status")
def update_status(
    data: StatusUpdate,
    appointment_id: int = IdParam(),
    db: Session = Depends(get_db),
    doctor: User = Depends(role_required("doctor")),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appt.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="This is not your appointment")

    if data.status == appt.status:
        return {"msg": "status unchanged", "status": appt.status}

    if data.status not in ALLOWED_TRANSITIONS[appt.status]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move an appointment from {appt.status} to {data.status}",
        )

    with booking_lock:
        # Reviving an appointment puts it back on the calendar, so the slot has
        # to be free again - it may have been taken while this one was cancelled.
        if data.status == "Scheduled":
            clash = find_clash(db, appt.doctor_id, appt.start_time, appt.end_time, ignore_id=appt.id)
            if clash:
                raise HTTPException(
                    status_code=400,
                    detail="That slot has since been booked, so this appointment cannot be restored",
                )

        appt.status = data.status
        db.commit()

    clear_schedule_cache(appt.doctor_id, appt.patient_id)
    logger.info("Appointment %s set to %s by doctor %s", appt.id, data.status, doctor.id)
    return {"msg": "status updated", "status": appt.status}


@router.get("/appointments", response_model=List[AppointmentOut],
            dependencies=[Depends(role_required("admin"))])
def all_appointments(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return (
        db.query(Appointment)
        .order_by(Appointment.start_time)
        .offset(offset)
        .limit(limit)
        .all()
    )


# --------------------------------------------------------------- schedules

@router.get("/doctors/{doctor_id}/appointments")
def doctor_schedule(
    doctor_id: int = IdParam(),
    db: Session = Depends(get_db),
    doctor: User = Depends(role_required("doctor")),
):
    if doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="You can only view your own schedule")

    def build():
        rows = (
            db.query(Appointment)
            .filter(Appointment.doctor_id == doctor_id)
            .order_by(Appointment.start_time)
            .all()
        )
        return [AppointmentOut.model_validate(a).model_dump() for a in rows]

    return cached(f"doctor_{doctor_id}_appointments", build)


@router.get("/patients/{patient_id}/appointments")
def patient_schedule(
    patient_id: int = IdParam(),
    db: Session = Depends(get_db),
    patient: User = Depends(role_required("patient")),
):
    if patient_id != patient.id:
        raise HTTPException(status_code=403, detail="You can only view your own schedule")

    def build():
        rows = (
            db.query(Appointment)
            .filter(Appointment.patient_id == patient_id)
            .order_by(Appointment.start_time)
            .all()
        )
        return [AppointmentOut.model_validate(a).model_dump() for a in rows]

    return cached(f"patient_{patient_id}_appointments", build)


# ----------------------------------------------------------------- directories

def list_users_by_role(db: Session, role: str, limit: int, offset: int):
    rows = (
        db.query(User)
        .filter(User.role == role)
        .order_by(User.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [UserOut.model_validate(u).model_dump() for u in rows]


@router.get("/patients", dependencies=[Depends(role_required("admin"))])
def get_patients(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if offset or limit != 50:
        return list_users_by_role(db, "patient", limit, offset)
    return cached("patients", lambda: list_users_by_role(db, "patient", limit, offset))


@router.get("/patients/{patient_id}", response_model=UserOut,
            dependencies=[Depends(role_required("admin"))])
def get_patient_by_id(patient_id: int = IdParam(), db: Session = Depends(get_db)):
    patient = db.query(User).filter(User.id == patient_id, User.role == "patient").first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/doctors", dependencies=[Depends(role_required("admin"))])
def get_doctors(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if offset or limit != 50:
        return list_users_by_role(db, "doctor", limit, offset)
    return cached("doctors", lambda: list_users_by_role(db, "doctor", limit, offset))


# --------------------------------------------------------------------- admin

@router.post("/admin/create-user", status_code=201,
             dependencies=[Depends(role_required("admin"))])
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    user = create_account(data, db, role=data.role)
    delete_cache("patients", "doctors")
    logger.info("Admin created %s (%s)", user.username, user.role)
    return {"msg": "created", "id": user.id}


@router.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int = IdParam(),
    db: Session = Depends(get_db),
    admin: User = Depends(role_required("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    if user.role == "admin" and db.query(User).filter(User.role == "admin").count() <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last administrator")

    # Remove their appointments first so no row is left pointing at a missing user.
    removed = db.query(Appointment).filter(
        (Appointment.patient_id == user_id) | (Appointment.doctor_id == user_id)
    ).delete(synchronize_session=False)

    db.delete(user)
    db.commit()

    delete_cache("patients", "doctors", f"doctor_{user_id}_appointments",
                 f"patient_{user_id}_appointments")
    logger.info("Admin deleted user %s and %s appointment(s)", user_id, removed)
    return {"msg": "deleted", "appointments_removed": removed}


@router.get("/dashboard", dependencies=[Depends(role_required("admin"))])
def dashboard():
    requests = metrics["requests"]
    return {
        "total_requests": requests,
        "error_count": metrics["errors"],
        "avg_response_time": round(metrics["total_time"] / requests, 4) if requests else 0,
        "by_status": dict(sorted(metrics["by_status"].items())),
        "top_endpoints": dict(metrics["by_route"].most_common(5)),
    }
