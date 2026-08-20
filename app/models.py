from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index
from app.db import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="patient")


class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="Scheduled")

    # Every overlap check filters on the doctor and the interval together.
    __table_args__ = (
        Index("ix_appointments_doctor_window", "doctor_id", "start_time", "end_time"),
        Index("ix_appointments_patient", "patient_id"),
    )
