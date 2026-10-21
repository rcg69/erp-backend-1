from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from database import get_db
from schemas.user_image_schema import UserImageResponse
from security.auth import get_current_user
from services import user_image_service


router = APIRouter(
    prefix="/api/user-images",
    tags=["User Images"],
)


@router.put(
    "/users/{user_id}",
    response_model=UserImageResponse,
    status_code=status.HTTP_200_OK,
)
async def replace_user_image(
    user_id: int,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    image_data = await file.read(user_image_service.MAX_IMAGE_SIZE + 1)
    if len(image_data) > user_image_service.MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image must be no larger than 5 MB",
        )
    content_type = user_image_service.validate_image(
        file.content_type or "",
        image_data,
    )
    return user_image_service.replace_user_image(
        user_id,
        current_user,
        file.filename or "profile-image",
        content_type,
        image_data,
        db,
    )


@router.get("/{image_id}")
def get_user_image(
    image_id: int,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    image = user_image_service.get_user_image(image_id, db)
    return Response(
        content=image["image_data"],
        media_type=image["content_type"],
        headers={"X-Content-Type-Options": "nosniff"},
    )
