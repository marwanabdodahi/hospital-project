from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models import User, Doctor, Patient, Appointment
from app.schemas import UserCreate, LoginSchema, AppointmentCreate
from app.auth import hash_password, verify_password, create_token
from app.dependencies import get_db, role_required, get_current_user
from app.cache import get_cache, set_cache, delete_cache
from app.logger import logger

router = APIRouter()

@router.post("/register")
def register(data: UserCreate, db: Session = Depends(get_db)):
    user = User(
        username=data.username,
        email=data.email,
        password=data.password,
        role=data.role
    )
    db.add(user)
    db.commit()
    return {"msg": "registered"}


@router.post("/login")
def login(data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not (data.password, user.password):
        raise HTTPException(status_code=401)

    token = create_token({"sub": user.username, "role": user.role})
    return {"access_token": token}


@router.post("/appointments", dependencies=[Depends(role_required("patient"))])
def book(data: AppointmentCreate, db: Session = Depends(get_db)):

    existing = db.query(Appointment).filter(
        Appointment.doctor_id == data.doctor_id,
        Appointment.start_time < data.end_time,
        Appointment.end_time > data.start_time
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Invalid Double booking")
    

    appt = Appointment(**data.dict())
    appt.status = "Scheduled"  

    db.add(appt)
    db.commit()

    delete_cache("appointments")

    logger.info("Appointment booked")
    return {"msg": "booked"}

@router.delete("/appointments/{id}",dependencies=[Depends(role_required("patient"))])
def cancel_appointment(id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    appt = db.query(Appointment).filter(Appointment.id == id).first()

    if not appt:
        raise HTTPException(404)

    if appt.patient_id != current_user.id:
        raise HTTPException(403, "Not allowed")

    appt.status = "Cancelled"
    db.commit()
    delete_cache("appointments")
    return {"msg": "cancelled"}

@router.put("/appointments/{id}/status",dependencies=[Depends(role_required("doctor"))])
def update_status(id: int, status: str,
                  db: Session = Depends(get_db) ):
    appt = db.query(Appointment).filter(Appointment.id == id).first()

    if not appt:
        raise HTTPException(status_code=404)

    if status not in ["Scheduled", "Completed", "Cancelled"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    appt.status = status
    db.commit()

    delete_cache("appointments")
    return {"msg": "status updated"}

@router.get("/appointments", dependencies=[Depends(role_required("admin"))])
def all_appointments(db: Session = Depends(get_db)):
    return db.query(Appointment).all()

@router.get("/doctors/{id}/appointments",dependencies=[Depends(role_required("doctor"))])
def doctor_schedule(id: int, db: Session = Depends(get_db)):
    cached = get_cache(f"doctor_{id}_appointments")
    if cached:
        return cached

    data = db.query(Appointment).filter(Appointment.doctor_id == id).all()

    result = [
        {
            "id": a.id,
            "patient_id": a.patient_id,
            "start": a.start_time,
            "end": a.end_time,
            "status": a.status
        }
        for a in data
    ]

    set_cache(f"doctor_{id}_appointments", result)
    return result
@router.get("/patients/{id}/appointments",dependencies=[Depends(role_required("patient"))])
def patient_schedule(id: int, db: Session = Depends(get_db)):
    cached = get_cache(f"patient_{id}_appointments")
    if cached:
        return cached

    data = db.query(Appointment).filter(Appointment.patient_id == id).all()

    result = [
        {
            "id": a.id,
            "doctor_id": a.doctor_id,
            "start": a.start_time,
            "end": a.end_time,
            "status": a.status
        }
        for a in data
    ]

    set_cache(f"patient_{id}_appointments", result)
    return result
@router.get("/patients", dependencies=[Depends(role_required("admin"))])
def get_patients(db: Session = Depends(get_db)):

    cached = get_cache("patients")  
    if cached:
        return cached

    patients = db.query(User).filter(User.role == "patient").all()

    result = [
        {
            "id": p.id,
            "username": p.username,
            "email": p.email
        }
        for p in patients
    ]

    set_cache("patients", result)  

    return result
@router.get("/patients/{id}", dependencies=[Depends(role_required("admin"))])
def get_patient_by_id(id: int, db: Session = Depends(get_db)):

    cache_key = f"patient_{id}"
    cached = get_cache(cache_key)

    if cached:
        return cached

    patient = db.query(User).filter(
        User.id == id,
        User.role == "patient"
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    result = {
        "id": patient.id,
        "username": patient.username,
        "email": patient.email
    }

    set_cache(cache_key, result)

    return result

@router.get("/doctors", dependencies=[Depends(role_required("admin"))])
def get_doctors(db: Session = Depends(get_db)):

    cached = get_cache("doctors")
    if cached:
        return cached

    doctors = db.query(User).filter(User.role == "doctor").all()

    result = [
        {
            "id": d.id,
            "username": d.username,
            "email": d.email
        }
        for d in doctors
    ]

    set_cache("doctors", result)

    return result
@router.post("/admin/create-user", dependencies=[Depends(role_required("admin"))])
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    user = User(
        username=data.username,
        email=data.email,
        password=data.password,
        role=data.role
    )
    db.add(user)
    db.commit()

    delete_cache("patients")
    delete_cache("doctors")

    return {"msg": "created"}
@router.delete("/admin/users/{id}", dependencies=[Depends(role_required("admin"))])
def delete_user(id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(404)

    db.delete(user)
    db.commit()

    delete_cache("patients")
    delete_cache("doctors")

    return {"msg": "deleted"}
from app.monitor import metrics

@router.get("/dashboard")
def dashboard():
    avg_time = 0
    if metrics["requests"] > 0:
        avg_time = metrics["total_time"] / metrics["requests"]

    return {
        "total_requests": metrics["requests"],
        "error_count": metrics["errors"],
        "avg_response_time": avg_time
    }