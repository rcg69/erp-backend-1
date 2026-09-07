from fastapi import APIRouter, Depends, HTTPException, status

from database import supabase_admin
from schemas.student_schema import StudentCreate
from security.auth import get_current_user, require_admin


router = APIRouter(
    prefix="/api/students",
    tags=["Students"]
)


@router.post("")
def create_student(student: StudentCreate, _current_user=Depends(require_admin)):
    try:
        response = (
            supabase_admin
            .table("students")
            .insert({
                "name": student.name,
                "roll_number": student.roll_number,
                **({"admission_date": student.admission_date.isoformat()} if student.admission_date else {})
            })
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=502, detail="Student could not be created")
        return {
            "success": True,
            "message": "Student created successfully",
            "student": response.data[0]
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Student service unavailable") from exc


@router.get("")
def get_students(_current_user=Depends(get_current_user)):
    try:
        response = (
            supabase_admin
            .table("students")
            .select("*")
            .execute()
        )

        return {
            "success": True,
            "count": len(response.data or []),
            "students": response.data or []
        }
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Student service unavailable") from exc