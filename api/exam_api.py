from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.exam_schema import (
    ExamCreate,
    ExamResponse,
    ExamStatus,
    ExamSubjectCreate,
    ExamSubjectResponse,
    ExamSubjectUpdate,
    ExamUpdate,
    EvaluationProgress,
    MarksCorrection,
    StudentMarkEntry,
    StudentMarkResponse,
)
from security.auth import get_current_user, require_admin, require_staff
from services import exam_service


router = APIRouter(
    prefix="/api/exams",
    tags=["Exams and Marks"],
)


@router.post(
    "",
    response_model=ExamResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_exam(
    data: ExamCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.create_exam(data, current_user, db)


@router.get("", response_model=list[ExamResponse])
def list_exams(
    academic_year: Annotated[str | None, Query(min_length=1, max_length=20)] = None,
    grade_id: int | None = Query(default=None, gt=0),
    exam_status: ExamStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.list_exams(
        academic_year, grade_id, exam_status, limit, offset, db
    )


@router.get("/assigned")
def list_assigned_exams(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(require_staff),
    db: Session = Depends(get_db),
):
    return exam_service.list_assigned_subjects(
        current_user["person_id"], limit, offset, db
    )


@router.get("/assigned/subjects/{exam_subject_id}/roster")
def get_assigned_roster(
    exam_subject_id: int,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(require_staff),
    db: Session = Depends(get_db),
):
    return exam_service.get_assigned_roster(
        exam_subject_id,
        current_user["person_id"],
        limit,
        offset,
        db,
    )


@router.get(
    "/assigned/subjects/{exam_subject_id}/progress",
    response_model=EvaluationProgress,
)
def get_assigned_progress(
    exam_subject_id: int,
    current_user=Depends(require_staff),
    db: Session = Depends(get_db),
):
    return exam_service.get_evaluation_progress(
        exam_subject_id, current_user["person_id"], db
    )


@router.put(
    "/assigned/subjects/{exam_subject_id}/marks/{student_id}",
    response_model=StudentMarkResponse,
)
def enter_student_marks(
    exam_subject_id: int,
    student_id: int,
    data: StudentMarkEntry,
    current_user=Depends(require_staff),
    db: Session = Depends(get_db),
):
    return exam_service.enter_student_marks(
        exam_subject_id,
        student_id,
        data,
        current_user,
        current_user["person_id"],
        db,
    )


@router.post(
    "/assigned/subjects/{exam_subject_id}/complete",
    response_model=EvaluationProgress,
)
def complete_evaluation(
    exam_subject_id: int,
    current_user=Depends(require_staff),
    db: Session = Depends(get_db),
):
    return exam_service.complete_evaluation(
        exam_subject_id, current_user["person_id"], db
    )


@router.get("/results/{exam_id}")
def get_exam_results(
    exam_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return exam_service.get_exam_results(
        exam_id, current_user, limit, offset, db
    )


@router.put(
    "/exam-subjects/{exam_subject_id}/marks/{student_id}/correction",
    response_model=StudentMarkResponse,
)
def correct_student_marks(
    exam_subject_id: int,
    student_id: int,
    data: MarksCorrection,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.correct_student_marks(
        exam_subject_id, student_id, data, current_user, db
    )


@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam(
    exam_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.get_exam(exam_id, db)


@router.post("/{exam_id}/roster/sync")
def sync_exam_roster(
    exam_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.sync_exam_roster(exam_id, db)


@router.put("/{exam_id}", response_model=ExamResponse)
def update_exam(
    exam_id: int,
    data: ExamUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.update_exam(exam_id, data, db)


@router.delete("/{exam_id}")
def delete_exam(
    exam_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.delete_exam(exam_id, db)


@router.post("/{exam_id}/schedule", response_model=ExamResponse)
def schedule_exam(
    exam_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.schedule_exam(exam_id, db)


@router.post("/{exam_id}/publish", response_model=ExamResponse)
def publish_exam(
    exam_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.publish_exam(exam_id, db)


@router.get("/{exam_id}/progress")
def get_exam_progress(
    exam_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.list_exam_subjects(exam_id, db)


@router.get(
    "/{exam_id}/subjects",
    response_model=list[ExamSubjectResponse],
)
def list_exam_subjects(
    exam_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.list_exam_subjects(exam_id, db)


@router.post(
    "/{exam_id}/subjects",
    response_model=ExamSubjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_exam_subject(
    exam_id: int,
    data: ExamSubjectCreate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.add_exam_subject(exam_id, data, db)


@router.put(
    "/{exam_id}/subjects/{exam_subject_id}",
    response_model=ExamSubjectResponse,
)
def update_exam_subject(
    exam_id: int,
    exam_subject_id: int,
    data: ExamSubjectUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.update_exam_subject(
        exam_id, exam_subject_id, data, db
    )


@router.delete("/{exam_id}/subjects/{exam_subject_id}")
def delete_exam_subject(
    exam_id: int,
    exam_subject_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return exam_service.delete_exam_subject(
        exam_id, exam_subject_id, db
    )
