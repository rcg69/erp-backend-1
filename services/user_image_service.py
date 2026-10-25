import logging
from pathlib import PureWindowsPath

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.user_image_model import UserImageRecord
from services.class_assignment_service import teacher_assigned_to_student_class


logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 5 * 1024 * 1024

_IMAGE_SIGNATURES = {
    "image/jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "image/png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/gif": lambda data: data.startswith((b"GIF87a", b"GIF89a")),
    "image/webp": lambda data: (
        len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    ),
}


def validate_image(content_type: str, image_data: bytes) -> str:
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    signature_matches = _IMAGE_SIGNATURES.get(normalized_type)

    if signature_matches is None or not signature_matches(image_data):
        raise HTTPException(
            status_code=400,
            detail="Upload a valid JPEG, PNG, GIF, or WebP image",
        )

    if len(image_data) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image must be no larger than 5 MB",
        )

    return normalized_type


def _authorize_image_change(
    user_id: int,
    current_user: dict,
    db: Session,
) -> dict:
    actor_role = db.execute(
        text("SELECT role_name FROM roles WHERE role_id = :role_id"),
        {"role_id": current_user["role_id"]},
    ).mappings().first()
    target_user = db.execute(
        text(
            """
            SELECT u.id, u.person_id, LOWER(r.role_name) AS role_name
            FROM users u
            JOIN roles r ON r.role_id = u.role_id
            WHERE u.id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().first()

    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if not actor_role:
        raise HTTPException(status_code=403, detail="User role not found")

    actor_role_name = str(actor_role["role_name"]).strip().lower()
    actor_id = current_user["id"]

    if actor_role_name == "admin":
        return dict(target_user)

    if actor_role_name not in {"staff", "teacher"}:
        raise HTTPException(
            status_code=403,
            detail="Only staff and administrators can change profile images",
        )

    staff = db.execute(
        text(
            """
            SELECT id
            FROM staff
            WHERE id = :staff_id
              AND LOWER(status) = 'active'
            """
        ),
        {"staff_id": current_user.get("person_id")},
    ).first()
    if not staff:
        raise HTTPException(
            status_code=403,
            detail="Staff profile is missing or inactive",
        )

    if actor_id == user_id and target_user["role_name"] in {"staff", "teacher"}:
        return dict(target_user)

    if target_user["role_name"] != "student" or target_user["person_id"] is None:
        raise HTTPException(
            status_code=403,
            detail="Staff can only change their own image or an assigned student's image",
        )

    student = db.execute(
        text(
            """
            SELECT id, grade, section
            FROM students
            WHERE id = :student_id
            """
        ),
        {"student_id": target_user["person_id"]},
    ).mappings().first()

    if not student or not teacher_assigned_to_student_class(
        db,
        current_user["person_id"],
        student["grade"],
        student["section"],
    ):
        raise HTTPException(
            status_code=403,
            detail="Student is not in a class assigned to this teacher",
        )

    return dict(target_user)


def replace_user_image(
    user_id: int,
    current_user: dict,
    filename: str,
    content_type: str,
    image_data: bytes,
    db: Session,
) -> dict:
    if not image_data:
        raise HTTPException(status_code=400, detail="Image file is empty")

    safe_filename = PureWindowsPath(filename.replace("/", "\\")).name[:255]

    try:
        target_user = _authorize_image_change(user_id, current_user, db)
        image = db.execute(
            text(
                """
                INSERT INTO profile_images (
                    user_id,
                    filename,
                    content_type,
                    image_data
                )
                VALUES (
                    :user_id,
                    :filename,
                    :content_type,
                    :image_data
                )
                RETURNING
                    id,
                    user_id,
                    filename,
                    content_type,
                    octet_length(image_data) AS size_bytes,
                    created_at
                """
            ),
            {
                "user_id": target_user["id"],
                "filename": safe_filename or "profile-image",
                "content_type": content_type,
                "image_data": image_data,
            },
        ).mappings().first()

        if not image:
            raise HTTPException(
                status_code=502,
                detail="Profile image could not be stored",
            )

        db.execute(
            text(
                """
                INSERT INTO user_details (user_id, image_id)
                VALUES (:user_id, :image_id)
                ON CONFLICT (user_id) DO UPDATE
                SET image_id = EXCLUDED.image_id,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {"user_id": target_user["id"], "image_id": image["id"]},
        )
        db.execute(
            text(
                """
                DELETE FROM profile_images
                WHERE user_id = :user_id
                  AND id <> :image_id
                """
            ),
            {"user_id": target_user["id"], "image_id": image["id"]},
        )
        db.commit()
        return dict(image)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to store profile image")
        raise HTTPException(
            status_code=503,
            detail="Profile image service unavailable",
        ) from exc


def get_user_image(image_id: int, db: Session) -> dict:
    try:
        image = db.execute(
            text(
                """
                SELECT
                    id,
                    user_id,
                    filename,
                    content_type,
                    image_data,
                    created_at
                FROM profile_images
                WHERE id = :image_id
                """
            ),
            {"image_id": image_id},
        ).mappings().first()
        if not image:
            raise HTTPException(status_code=404, detail="Profile image not found")
        image_record = dict(image)
        image_record["image_data"] = bytes(image_record["image_data"])
        return UserImageRecord.model_validate(image_record).model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to retrieve profile image")
        raise HTTPException(
            status_code=503,
            detail="Profile image service unavailable",
        ) from exc
