from datetime import datetime
from pydantic import BaseModel, Field


class StaffCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    number: str = Field(..., min_length=1, max_length=30)
    status: str = Field(default="active", min_length=1, max_length=20)


class StaffUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    number: str | None = Field(default=None, min_length=1, max_length=30)
    status: str | None = Field(default=None, min_length=1, max_length=20)


class StaffResponse(BaseModel):
    id: int
    name: str
    number: str
    status: str
    created_at: datetime | None = None