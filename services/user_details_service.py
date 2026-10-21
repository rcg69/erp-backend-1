from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from schemas.user_details_schema import UserDetailsUpdate
from services.class_assignment_service import teacher_assigned_to_student_class


DETAIL_COLUMNS = (
    "user_id, image_id, full_name, gender, date_of_birth, nationality, mother_tongue, "
    "religion, caste_category, aadhaar_number, identification_mark_1, "
    "identification_mark_2, mobile_number, alternate_mobile_number, "
    "email_address, father_name, father_mobile_number, father_occupation, "
    "mother_name, mother_mobile_number, mother_occupation, "
    "spouse_guardian_name, spouse_guardian_mobile_number, "
    "annual_family_income, present_house_flat_number, "
    "present_street_locality, present_village_town_city, "
    "present_mandal_sub_district, present_district, present_state, "
    "present_pin_code, present_country, same_as_present_address, "
    "permanent_house_flat_number, permanent_street_locality, "
    "permanent_village_town_city, permanent_mandal_sub_district, "
    "permanent_district, permanent_state, permanent_pin_code, "
    "permanent_country, updated_at"
)

PRESENT_ADDRESS_FIELDS = (
    "house_flat_number",
    "street_locality",
    "village_town_city",
    "mandal_sub_district",
    "district",
    "state",
    "pin_code",
    "country",
)


def _get_or_create_details(user_id: int, db: Session) -> dict:
    exists = db.execute(
        text("SELECT id FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="User not found")

    db.execute(
        text(
            """
            INSERT INTO user_details (user_id)
            VALUES (:user_id)
            ON CONFLICT (user_id) DO NOTHING
            """
        ),
        {"user_id": user_id},
    )
    details = db.execute(
        text(
            f"""
            SELECT {DETAIL_COLUMNS}
            FROM user_details
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    if not details:
        raise HTTPException(status_code=404, detail="User details not found")
    return dict(details)


def _authorize_user_details_access(
    user_id: int,
    current_user: dict,
    db: Session,
) -> None:
    if current_user["id"] == user_id:
        return

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
    if actor_role_name == "admin":
        return
    if actor_role_name not in {"staff", "teacher"}:
        raise HTTPException(status_code=403, detail="Profile access denied")

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
    if target_user["role_name"] != "student" or target_user["person_id"] is None:
        raise HTTPException(
            status_code=403,
            detail="Staff can only access profiles of students in assigned classes",
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


def get_user_details(
    user_id: int,
    db: Session,
    current_user: dict,
) -> dict:
    try:
        _authorize_user_details_access(user_id, current_user, db)
        details = _get_or_create_details(user_id, db)
        db.commit()
        return details
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="User details service unavailable",
        ) from exc


def update_user_details(
    user_id: int,
    details_update: UserDetailsUpdate,
    db: Session,
    current_user: dict,
) -> dict:
    try:
        _authorize_user_details_access(user_id, current_user, db)
        existing = _get_or_create_details(user_id, db)
        updates = details_update.model_dump(exclude_unset=True)

        if "email_address" in updates and updates["email_address"] is not None:
            updates["email_address"] = str(updates["email_address"]).strip().lower()

        same_as_present = updates.get(
            "same_as_present_address",
            existing["same_as_present_address"],
        )
        if same_as_present:
            for field in PRESENT_ADDRESS_FIELDS:
                present_field = f"present_{field}"
                permanent_field = f"permanent_{field}"
                updates[permanent_field] = updates.get(
                    present_field,
                    existing[present_field],
                )

        if updates:
            assignments = ", ".join(
                f"{field} = :{field}" for field in updates
            )
            updates["user_id"] = user_id
            db.execute(
                text(
                    f"""
                    UPDATE user_details
                    SET {assignments}, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = :user_id
                    """
                ),
                updates,
            )

        result = db.execute(
            text(
                f"""
                SELECT {DETAIL_COLUMNS}
                FROM user_details
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
        db.commit()
        if not result:
            raise HTTPException(status_code=404, detail="User details not found")
        return dict(result)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="User details service unavailable",
        ) from exc
