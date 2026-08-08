from pydantic import BaseModel
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str

class LoginSchema(BaseModel):
    username: str
    password: str

class AppointmentCreate(BaseModel):
    doctor_id: int
    patient_id: int
    start_time: datetime
    end_time: datetime