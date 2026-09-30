from datetime import datetime

from pydantic import BaseModel


class SubjectCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    status: str = "active"


class SubjectUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    description: str | None = None
    status: str | None = None


class SubjectResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    status: str
    created_at: datetime