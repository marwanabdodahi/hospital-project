"""Fill the database with demo data for a presentation.

    python seed.py

Existing accounts are left alone; anything already present is skipped.
Every demo account uses the password below.
"""
from datetime import datetime, timedelta

from app.auth import hash_password
from app.db import Base, SessionLocal, engine
from app.models import Appointment, User

PASSWORD = "demo12345"

DEMO_USERS = [
    ("admin",   "admin@hospital.local",  "admin"),
    ("dr.hana", "hana@hospital.local",   "doctor"),
    ("dr.omar", "omar@hospital.local",   "doctor"),
    ("sara",    "sara@example.com",      "patient"),
    ("khaled",  "khaled@example.com",    "patient"),
]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        created = 0
        for username, email, role in DEMO_USERS:
            if db.query(User).filter(User.username == username).first():
                continue
            db.add(User(username=username, email=email,
                        password=hash_password(PASSWORD), role=role))
            created += 1
        db.commit()

        users = {u.username: u for u in db.query(User).all()}
        tomorrow = (datetime.now() + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0)

        plan = [
            ("sara",   "dr.hana", 0, "Scheduled"),
            ("khaled", "dr.hana", 1, "Scheduled"),
            ("sara",   "dr.omar", 2, "Completed"),
        ]

        appointments = 0
        for patient, doctor, hours, status in plan:
            if patient not in users or doctor not in users:
                continue
            start = tomorrow + timedelta(hours=hours)
            exists = db.query(Appointment).filter(
                Appointment.doctor_id == users[doctor].id,
                Appointment.start_time == start,
            ).first()
            if exists:
                continue
            db.add(Appointment(
                doctor_id=users[doctor].id,
                patient_id=users[patient].id,
                start_time=start,
                end_time=start + timedelta(hours=1),
                status=status,
            ))
            appointments += 1
        db.commit()

        print(f"Created {created} user(s) and {appointments} appointment(s).")
        print(f"Every demo account uses the password: {PASSWORD}")
        for username, _, role in DEMO_USERS:
            print(f"  {username:10} {role}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
