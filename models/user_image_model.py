from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserImageRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    filename: str
    content_type: str
    image_data: bytes
    created_at: datetime
