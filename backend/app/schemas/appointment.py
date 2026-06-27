from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AppointmentBase(BaseModel):
    caller_name: str
    reason: Optional[str] = None
    preferred_date_time: str
    contact_number: str


class AppointmentCreate(AppointmentBase):
    room_name: str


class AppointmentResponse(AppointmentBase):
    id: int
    room_name: str
    confirmation_code: str
    created_at: datetime

    class Config:
        from_attributes = True
