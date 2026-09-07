from pydantic import BaseModel
from datetime import date


class StudentCreate(BaseModel):
    name: str
    roll_number: str
    admission_date: date | None = None


class StudentResponse(BaseModel):
    id: int
    name: str
    roll_number: str
    admission_date: date | None = None
    status: str
    created_at: str | None = None