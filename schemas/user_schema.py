
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    role: str = Field(min_length=1, max_length=30)
    person_id: int | None = None

    @model_validator(mode="after")
    def validate_person_id(self):
        role_name = self.role.strip().lower()

        if role_name in {"student", "staff", "teacher"}:
            if self.person_id is None:
                raise ValueError(
                    "person_id is required for student and staff accounts"
                )

        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    email: EmailStr
    username: str
    person_id: int | None = None
    role_id: int
    is_active: bool
