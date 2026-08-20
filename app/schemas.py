from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.auth import MAX_PASSWORD_BYTES

# An appointment longer than this is almost certainly a mistake, and it would
# block the doctor's calendar for the whole period.
MAX_APPOINTMENT_HOURS = 4

Role = Literal["patient", "doctor", "admin"]
Status = Literal["Scheduled", "Completed", "Cancelled"]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=6)
    role: Role = "patient"

    @field_validator("username")
    @classmethod
    def normalise_username(cls, value: str) -> str:
        """Usernames are stored lower case and trimmed, so 'Ahmed' and 'ahmed'
        are the same account rather than two different ones."""
        cleaned = value.strip().lower()
        if len(cleaned) < 3:
            raise ValueError("username must be at least 3 characters")
        if not cleaned.replace("_", "").replace(".", "").isalnum():
            raise ValueError("username may only contain letters, digits, dot and underscore")
        return cleaned

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"password is too long ({len(value.encode())} bytes); "
                f"the limit is {MAX_PASSWORD_BYTES} bytes, and non-Latin "
                "characters use more than one byte each"
            )
        return value


class LoginSchema(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def normalise_username(cls, value: str) -> str:
        return value.strip().lower()


class AppointmentCreate(BaseModel):
    doctor_id: int = Field(gt=0)
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def check_interval(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")

        if self.start_time < datetime.now():
            raise ValueError("cannot book an appointment in the past")

        if self.end_time - self.start_time > timedelta(hours=MAX_APPOINTMENT_HOURS):
            raise ValueError(f"an appointment cannot be longer than {MAX_APPOINTMENT_HOURS} hours")

        return self


class StatusUpdate(BaseModel):
    status: Status


class UserOut(BaseModel):
    id: int
    username: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class AppointmentOut(BaseModel):
    id: int
    doctor_id: int
    patient_id: int
    start_time: datetime
    end_time: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)
