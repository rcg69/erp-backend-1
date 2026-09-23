from pydantic import BaseModel, Field


class SectionCreate(BaseModel):
    section: str = Field(..., min_length=1, max_length=10)
    staff_id: int | None = None


class SectionUpdate(BaseModel):
    section: str | None = Field(default=None, min_length=1, max_length=10)
    staff_id: int | None = None


class SectionResponse(BaseModel):
    id: int
    section: str
    staff_id: int | None = None

    class Config:
        from_attributes = True