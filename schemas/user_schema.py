from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    role: str = Field(min_length=1, max_length=30)
    person_id: int


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    email: EmailStr
    username: str
    person_id: int | None = None
    role_id: int
    is_active: bool