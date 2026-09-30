from pydantic import BaseModel, Field


class SectionCreate(BaseModel):
    section: str = Field(..., min_length=1, max_length=10)


class SectionUpdate(BaseModel):
    section: str | None = Field(default=None, min_length=1, max_length=10)


class SectionResponse(BaseModel):
    id: int
    section: str

    class Config:
        from_attributes = True