from pydantic import BaseModel, Field


class GradeCreate(BaseModel):
    academic_year: str = Field(..., min_length=1, max_length=20)
    grade: str = Field(..., min_length=1, max_length=20)
    status: str = "active"


class GradeUpdate(BaseModel):
    academic_year: str | None = Field(default=None, min_length=1, max_length=20)
    grade: str | None = Field(default=None, min_length=1, max_length=20)
    status: str | None = None


class GradeResponse(BaseModel):
    id: int
    academic_year: str
    grade: str
    status: str

    class Config:
        from_attributes = True
