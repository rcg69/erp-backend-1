
import logging

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from models import staff_model
from schemas.staff_schema import StaffCreate, StaffUpdate


logger = logging.getLogger(__name__)


def create_staff(staff: StaffCreate, db: Session) -> dict:
    try:
        created = staff_model.insert_staff(
            db,
            staff.model_dump(),
        )

        if created is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Staff could not be created",
            )

        db.commit()
        return created

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        logger.warning("Staff creation violated a database constraint", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff number already exists",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while creating staff")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Staff service temporarily unavailable",
        ) from exc


def get_staff(db: Session) -> list[dict]:
    try:
        return staff_model.get_all_staff(db)

    except SQLAlchemyError as exc:
        logger.exception("Database error while listing staff")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Staff service temporarily unavailable",
        ) from exc


def get_one_staff(staff_id: int, db: Session) -> dict:
    try:
        staff = staff_model.get_staff_by_id(db, staff_id)

        if staff is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff not found",
            )

        return staff

    except HTTPException:
        raise

    except SQLAlchemyError as exc:
        logger.exception("Database error while retrieving staff")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Staff service temporarily unavailable",
        ) from exc


def update_staff(
    staff_id: int,
    staff: StaffUpdate,
    db: Session,
) -> dict:
    payload = staff.model_dump(exclude_unset=True)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No staff fields were provided for update",
        )

    for field in ("name", "number", "status"):
        if field in payload and payload[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field} cannot be null",
            )

    try:
        existing = staff_model.get_staff_by_id(db, staff_id)

        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff not found",
            )

        updated = staff_model.update_staff_record(
            db,
            staff_id,
            payload,
        )

        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid staff fields were provided for update",
            )

        db.commit()
        return updated

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        logger.warning("Staff update violated a database constraint", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff number already exists",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while updating staff")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Staff service temporarily unavailable",
        ) from exc


def delete_staff(staff_id: int, db: Session) -> dict:
    try:
        deleted = staff_model.delete_staff_record(db, staff_id)

        if deleted is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff not found",
            )

        db.commit()

        return {
            "success": True,
            "message": "Staff deleted successfully",
            "staff": deleted,
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        logger.warning("Staff deletion violated a database constraint", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff cannot be deleted because related records exist",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while deleting staff")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Staff service temporarily unavailable",
        ) from exc
