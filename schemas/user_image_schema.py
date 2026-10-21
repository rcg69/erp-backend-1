from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
