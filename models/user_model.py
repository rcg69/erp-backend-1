from pydantic import BaseModel, EmailStr


class UserRecord(BaseModel):
    id: int
    username: str
    email: EmailStr
    password_hash: str
    person_id: int | None = None
    role_id: int
    is_active: bool = True