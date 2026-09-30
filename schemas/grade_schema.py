from pydantic import BaseModel, Field


class GradeCreate(BaseModel):
    academic_year: str = Field(..., min_length=1, max_length=20)
    grade: str = Field(..., min_length=1, max_length=20)
    section_id: int | None = None
    staff_id: int | None = None
    status: str = "active"


class GradeUpdate(BaseModel):
    academic_year: str | None = Field(default=None, min_length=1, max_length=20)
    grade: str | None = Field(default=None, min_length=1, max_length=20)
    section_id: int | None = None
    staff_id: int | None = None
    status: str | None = None


class GradeResponse(BaseModel):
    id: int
    academic_year: str
    grade: str
    section_id: int | None = None
    staff_id: int | None = None
    status: str

    class Config:
        from_attributes = True
