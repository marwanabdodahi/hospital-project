from typing import List

from fastapi import APIRouter, Depends, HTTPException
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


def create_account(data: UserCreate, db: Session, role: str) -> User:
    """Create a user with the given role, rejecting a username that is taken."""
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

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


def clear_schedule_cache(doctor_id: int, patient_id: int):
    delete_cache(f"doctor_{doctor_id}_appointments", f"patient_{patient_id}_appointments")


# ---------------------------------------------------------------- accounts

@router.post("/register", status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """Public sign-up. Always creates a patient — staff accounts go through /admin/create-user."""
    user = create_account(data, db, role="patient")
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

    clash = db.query(Appointment).filter(
        Appointment.doctor_id == data.doctor_id,
        Appointment.status != "Cancelled",
        Appointment.start_time < data.end_time,
        Appointment.end_time > data.start_time,
    ).first()

    if clash:
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
    appointment_id: int,
    db: Session = Depends(get_db),
    patient: User = Depends(role_required("patient")),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appt.patient_id != patient.id:
        raise HTTPException(status_code=403, detail="This is not your appointment")

    appt.status = "Cancelled"
    db.commit()

    clear_schedule_cache(appt.doctor_id, appt.patient_id)
    logger.info("Appointment %s cancelled by patient %s", appt.id, patient.id)
    return {"msg": "cancelled"}


@router.put("/appointments/{appointment_id}/status")
def update_status(
    appointment_id: int,
    data: StatusUpdate,
    db: Session = Depends(get_db),
    doctor: User = Depends(role_required("doctor")),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appt.doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="This is not your appointment")

    appt.status = data.status
    db.commit()

    clear_schedule_cache(appt.doctor_id, appt.patient_id)
    logger.info("Appointment %s set to %s by doctor %s", appt.id, data.status, doctor.id)
    return {"msg": "status updated"}


@router.get("/appointments", response_model=List[AppointmentOut],
            dependencies=[Depends(role_required("admin"))])
def all_appointments(db: Session = Depends(get_db)):
    return db.query(Appointment).all()


# --------------------------------------------------------------- schedules

@router.get("/doctors/{doctor_id}/appointments")
def doctor_schedule(
    doctor_id: int,
    db: Session = Depends(get_db),
    doctor: User = Depends(role_required("doctor")),
):
    if doctor_id != doctor.id:
        raise HTTPException(status_code=403, detail="You can only view your own schedule")

    def build():
        rows = db.query(Appointment).filter(Appointment.doctor_id == doctor_id).all()
        return [AppointmentOut.model_validate(a).model_dump() for a in rows]

    return cached(f"doctor_{doctor_id}_appointments", build)


@router.get("/patients/{patient_id}/appointments")
def patient_schedule(
    patient_id: int,
    db: Session = Depends(get_db),
    patient: User = Depends(role_required("patient")),
):
    if patient_id != patient.id:
        raise HTTPException(status_code=403, detail="You can only view your own schedule")

    def build():
        rows = db.query(Appointment).filter(Appointment.patient_id == patient_id).all()
        return [AppointmentOut.model_validate(a).model_dump() for a in rows]

    return cached(f"patient_{patient_id}_appointments", build)


# ----------------------------------------------------------------- directories

@router.get("/patients", dependencies=[Depends(role_required("admin"))])
def get_patients(db: Session = Depends(get_db)):
    def build():
        rows = db.query(User).filter(User.role == "patient").all()
        return [UserOut.model_validate(u).model_dump() for u in rows]

    return cached("patients", build)


@router.get("/patients/{patient_id}", response_model=UserOut,
            dependencies=[Depends(role_required("admin"))])
def get_patient_by_id(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(User).filter(User.id == patient_id, User.role == "patient").first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/doctors", dependencies=[Depends(role_required("admin"))])
def get_doctors(db: Session = Depends(get_db)):
    def build():
        rows = db.query(User).filter(User.role == "doctor").all()
        return [UserOut.model_validate(u).model_dump() for u in rows]

    return cached("doctors", build)


# --------------------------------------------------------------------- admin

@router.post("/admin/create-user", status_code=201,
             dependencies=[Depends(role_required("admin"))])
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    user = create_account(data, db, role=data.role)
    delete_cache("patients", "doctors")
    logger.info("Admin created %s (%s)", user.username, user.role)
    return {"msg": "created", "id": user.id}


@router.delete("/admin/users/{user_id}", dependencies=[Depends(role_required("admin"))])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.query(Appointment).filter(
        (Appointment.patient_id == user_id) | (Appointment.doctor_id == user_id)
    ).update({"status": "Cancelled"}, synchronize_session=False)

    db.delete(user)
    db.commit()

    delete_cache("patients", "doctors", f"doctor_{user_id}_appointments",
                 f"patient_{user_id}_appointments")
    logger.info("Admin deleted user %s", user_id)
    return {"msg": "deleted"}


@router.get("/dashboard", dependencies=[Depends(role_required("admin"))])
def dashboard():
    requests = metrics["requests"]
    return {
        "total_requests": requests,
        "error_count": metrics["errors"],
        "avg_response_time": round(metrics["total_time"] / requests, 4) if requests else 0,
        "by_status": dict(metrics["by_status"]),
        "top_endpoints": dict(metrics["by_path"].most_common(5)),
    }
