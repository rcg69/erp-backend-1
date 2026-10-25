import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from schemas.exam_schema import (
    ExamCreate,
    ExamSubjectCreate,
    ExamSubjectUpdate,
    StudentMarkEntry,
)
from services import exam_service


class _FakeDatabase:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class ExamManagementTests(unittest.TestCase):
    def setUp(self):
        self.db = _FakeDatabase()
        self.staff_user = {"id": 6, "person_id": 19}

    def test_exam_dates_must_be_ordered(self):
        with self.assertRaises(ValidationError):
            ExamCreate(
                name="Unit Test",
                academic_year="2026-2027",
                grade_id=3,
                start_date="2026-11-10",
                end_date="2026-11-09",
            )

    def test_subject_pass_marks_must_not_exceed_maximum(self):
        with self.assertRaises(ValidationError):
            ExamSubjectCreate(
                subject_id=4,
                max_marks=Decimal("50"),
                pass_marks=Decimal("51"),
                evaluator_staff_id=19,
            )

    def test_marks_must_not_exceed_configured_maximum(self):
        with self.assertRaises(HTTPException) as raised:
            exam_service._validate_mark_payload(
                {
                    "marks_obtained": Decimal("51"),
                    "is_absent": False,
                    "remarks": None,
                },
                Decimal("50"),
            )

        self.assertEqual(raised.exception.status_code, 422)

    @patch.object(
        exam_service.model,
        "list_student_exams",
        return_value=[{"id": 2, "status": "scheduled"}],
    )
    @patch.object(exam_service.model, "get_role_name", return_value="student")
    def test_student_exam_list_is_scoped_to_linked_student(
        self,
        _get_role,
        list_student_exams,
    ):
        result = exam_service.list_student_exams(
            {"role_id": 4, "person_id": 45},
            100,
            0,
            self.db,
        )

        self.assertEqual(result, [{"id": 2, "status": "scheduled"}])
        list_student_exams.assert_called_once_with(self.db, 45, 100, 0)

    @patch.object(exam_service.model, "list_student_exams")
    @patch.object(exam_service.model, "get_role_name", return_value="staff")
    def test_non_student_cannot_list_student_exams(
        self,
        _get_role,
        list_student_exams,
    ):
        with self.assertRaises(HTTPException) as raised:
            exam_service.list_student_exams(
                {"role_id": 2, "person_id": 19},
                100,
                0,
                self.db,
            )

        self.assertEqual(raised.exception.status_code, 403)
        list_student_exams.assert_not_called()

    @patch.object(exam_service, "_require_exam", return_value={"id": 2, "status": "published"})
    @patch.object(exam_service.model, "set_exam_status")
    @patch.object(
        exam_service.model,
        "get_exam_subjects",
        return_value=[
            {"marked_count": 2, "student_count": 10},
            {"marked_count": 0, "student_count": 10},
        ],
    )
    @patch.object(
        exam_service,
        "_lock_exam",
        return_value={"id": 2, "status": "scheduled"},
    )
    def test_admin_override_publishes_entered_marks_before_evaluation_is_complete(
        self,
        _lock_exam,
        _get_subjects,
        set_exam_status,
        _require_exam,
    ):
        result = exam_service.override_publish_exam(2, self.db)

        self.assertEqual(result["status"], "published")
        set_exam_status.assert_called_once_with(self.db, 2, "published")
        self.assertEqual(self.db.commits, 1)

    @patch.object(exam_service.model, "set_exam_status")
    @patch.object(
        exam_service.model,
        "get_exam_subjects",
        return_value=[{"marked_count": 0, "student_count": 10}],
    )
    @patch.object(
        exam_service,
        "_lock_exam",
        return_value={"id": 2, "status": "scheduled"},
    )
    def test_admin_override_requires_at_least_one_entered_mark(
        self,
        _lock_exam,
        _get_subjects,
        set_exam_status,
    ):
        with self.assertRaises(HTTPException) as raised:
            exam_service.override_publish_exam(2, self.db)

        self.assertEqual(raised.exception.status_code, 409)
        set_exam_status.assert_not_called()
        self.assertEqual(self.db.rollbacks, 1)

    @patch.object(exam_service.model, "get_exam_subjects")
    @patch.object(
        exam_service,
        "_lock_exam",
        return_value={"id": 2, "status": "completed"},
    )
    def test_admin_override_is_only_available_for_scheduled_exams(
        self,
        _lock_exam,
        get_subjects,
    ):
        with self.assertRaises(HTTPException) as raised:
            exam_service.override_publish_exam(2, self.db)

        self.assertEqual(raised.exception.status_code, 409)
        get_subjects.assert_not_called()
        self.assertEqual(self.db.rollbacks, 1)

    @patch.object(
        exam_service.model,
        "list_student_exam_subjects",
        return_value=[{"subject_id": 3, "max_marks": Decimal("100")}],
    )
    @patch.object(
        exam_service.model,
        "get_exam_ids_for_student",
        return_value={"status": "scheduled"},
    )
    @patch.object(exam_service.model, "get_role_name", return_value="student")
    def test_student_can_view_allocations_for_rostered_exam(
        self,
        _get_role,
        get_student_exam,
        list_subjects,
    ):
        result = exam_service.list_student_exam_subjects(
            2,
            {"role_id": 4, "person_id": 45},
            self.db,
        )

        self.assertEqual(result, [{"subject_id": 3, "max_marks": Decimal("100")}])
        get_student_exam.assert_called_once_with(self.db, 45, 2)
        list_subjects.assert_called_once_with(self.db, 2)

    @patch.object(exam_service.model, "list_student_exam_subjects")
    @patch.object(exam_service.model, "get_exam_ids_for_student", return_value=None)
    @patch.object(exam_service.model, "get_role_name", return_value="student")
    def test_student_cannot_view_allocations_for_unrostered_exam(
        self,
        _get_role,
        get_student_exam,
        list_subjects,
    ):
        with self.assertRaises(HTTPException) as raised:
            exam_service.list_student_exam_subjects(
                2,
                {"role_id": 4, "person_id": 45},
                self.db,
            )

        self.assertEqual(raised.exception.status_code, 404)
        get_student_exam.assert_called_once_with(self.db, 45, 2)
        list_subjects.assert_not_called()

    @patch.object(exam_service.model, "create_exam")
    @patch.object(exam_service.model, "get_grade_class", return_value=None)
    def test_exam_creation_rejects_class_year_mismatch(
        self,
        get_grade_class,
        create_exam,
    ):
        with self.assertRaises(HTTPException) as raised:
            exam_service.create_exam(
                ExamCreate(
                    name="Unit Test",
                    academic_year="2026-2027",
                    grade_id=3,
                    start_date=date(2026, 11, 1),
                    end_date=date(2026, 11, 2),
                ),
                {"id": 7},
                self.db,
            )

        self.assertEqual(raised.exception.status_code, 422)
        get_grade_class.assert_called_once_with(
            self.db, 3, "2026-2027"
        )
        create_exam.assert_not_called()

    @patch.object(exam_service, "_lock_exam", return_value={
        "id": 2,
        "status": "draft",
        "start_date": date(2026, 11, 1),
        "end_date": date(2026, 11, 10),
    })
    @patch.object(exam_service.model, "get_active_staff", return_value=None)
    @patch.object(exam_service.model, "get_subject", return_value={
        "id": 4,
        "status": "active",
    })
    @patch.object(exam_service.model, "create_exam_subject")
    def test_inactive_evaluator_cannot_be_assigned(
        self,
        create_exam_subject,
        _get_subject,
        get_active_staff,
        _lock_exam,
    ):
        with self.assertRaises(HTTPException) as raised:
            exam_service.add_exam_subject(
                2,
                ExamSubjectCreate(
                    subject_id=4,
                    max_marks=Decimal("100"),
                    pass_marks=Decimal("40"),
                    evaluator_staff_id=19,
                ),
                self.db,
            )

        self.assertEqual(raised.exception.status_code, 422)
        get_active_staff.assert_called_once_with(self.db, 19)
        create_exam_subject.assert_not_called()

    @patch.object(
        exam_service.model,
        "update_exam_subject",
        return_value={"id": 12, "evaluator_staff_id": 20},
    )
    @patch.object(
        exam_service.model,
        "get_active_staff",
        return_value={"id": 20, "name": "Staff"},
    )
    @patch.object(
        exam_service.model,
        "get_exam_subject",
        return_value={
            "id": 12,
            "exam_id": 2,
            "max_marks": Decimal("100"),
            "pass_marks": Decimal("40"),
            "exam_date": date(2026, 11, 5),
        },
    )
    @patch.object(
        exam_service.model,
        "get_exam",
        return_value={
            "id": 2,
            "status": "scheduled",
            "start_date": date(2026, 11, 1),
            "end_date": date(2026, 11, 10),
        },
    )
    @patch.object(
        exam_service.model,
        "lock_exam_subject",
        return_value={
            "id": 12,
            "exam_id": 2,
            "evaluator_staff_id": 19,
            "evaluation_status": "in_progress",
            "exam_status": "scheduled",
        },
    )
    def test_admin_can_reassign_evaluator_before_completion(
        self,
        _lock_subject,
        _get_exam,
        _get_exam_subject,
        get_active_staff,
        update_exam_subject,
    ):
        updated = exam_service.update_exam_subject(
            2,
            12,
            ExamSubjectUpdate(evaluator_staff_id=20),
            self.db,
        )

        self.assertEqual(updated["evaluator_staff_id"], 20)
        get_active_staff.assert_called_once_with(self.db, 20)
        update_exam_subject.assert_called_once()
        self.assertEqual(self.db.commits, 1)

    def test_absent_student_cannot_have_marks(self):
        with self.assertRaises(HTTPException) as raised:
            exam_service._validate_mark_payload(
                {
                    "marks_obtained": Decimal("1"),
                    "is_absent": True,
                    "remarks": None,
                },
                Decimal("50"),
            )

        self.assertEqual(raised.exception.status_code, 422)

    @patch.object(exam_service.model, "save_mark")
    @patch.object(exam_service.model, "get_exam_student", return_value=True)
    @patch.object(
        exam_service.model,
        "lock_exam_subject",
        return_value={
            "id": 12,
            "exam_id": 2,
            "max_marks": Decimal("50"),
            "evaluation_status": "pending",
            "evaluator_staff_id": 20,
            "exam_status": "scheduled",
        },
    )
    def test_staff_cannot_enter_marks_for_another_evaluator(
        self,
        _lock_subject,
        _get_exam_student,
        save_mark,
    ):
        with self.assertRaises(HTTPException) as raised:
            exam_service.enter_student_marks(
                12,
                45,
                StudentMarkEntry(marks_obtained=Decimal("40")),
                self.staff_user,
                19,
                self.db,
            )

        self.assertEqual(raised.exception.status_code, 404)
        save_mark.assert_not_called()
        self.assertEqual(self.db.rollbacks, 1)

    @patch.object(exam_service.model, "save_mark")
    @patch.object(exam_service.model, "get_exam_student", return_value=True)
    @patch.object(
        exam_service.model,
        "lock_exam_subject",
        return_value={
            "id": 12,
            "exam_id": 2,
            "max_marks": Decimal("50"),
            "evaluation_status": "completed",
            "evaluator_staff_id": 19,
            "exam_status": "scheduled",
        },
    )
    def test_completed_evaluation_is_locked(
        self,
        _lock_subject,
        _get_exam_student,
        save_mark,
    ):
        with self.assertRaises(HTTPException) as raised:
            exam_service.enter_student_marks(
                12,
                45,
                StudentMarkEntry(marks_obtained=Decimal("40")),
                self.staff_user,
                19,
                self.db,
            )

        self.assertEqual(raised.exception.status_code, 409)
        save_mark.assert_not_called()

    @patch.object(
        exam_service.model,
        "count_subject_marks",
        return_value=2,
    )
    @patch.object(
        exam_service.model,
        "count_exam_students",
        return_value=3,
    )
    @patch.object(exam_service.model, "set_evaluation_status")
    @patch.object(
        exam_service.model,
        "lock_exam_subject",
        return_value={
            "id": 12,
            "exam_id": 2,
            "evaluator_staff_id": 19,
            "evaluation_status": "in_progress",
            "exam_status": "scheduled",
        },
    )
    def test_evaluation_cannot_complete_with_unmarked_students(
        self,
        _lock_subject,
        set_evaluation_status,
        _count_students,
        _count_marks,
    ):
        with self.assertRaises(HTTPException) as raised:
            exam_service.complete_evaluation(12, 19, self.db)

        self.assertEqual(raised.exception.status_code, 409)
        set_evaluation_status.assert_not_called()

    @patch.object(exam_service.model, "get_results")
    @patch.object(
        exam_service.model,
        "get_exam_ids_for_student",
        return_value={"status": "published"},
    )
    @patch.object(exam_service.model, "get_role_name", return_value="student")
    def test_students_only_receive_their_own_published_results(
        self,
        _get_role,
        _get_student_exam,
        get_results,
    ):
        get_results.return_value = [{
            "exam_id": 2,
            "exam_name": "Quarterly",
            "academic_year": "2026-2027",
            "status": "published",
            "student_id": 45,
            "student_name": "Student",
            "roll_number": "S-45",
            "subject_id": 3,
            "subject_name": "Science",
            "max_marks": Decimal("100"),
            "pass_marks": Decimal("35"),
            "marks_obtained": Decimal("80"),
            "is_absent": False,
            "remarks": None,
        }]

        result = exam_service.get_exam_results(
            2,
            {"role_id": 4, "person_id": 45},
            100,
            0,
            self.db,
        )

        self.assertEqual(result["students"][0]["student_id"], 45)
        get_results.assert_called_once_with(
            self.db, 2, 45, None, 100, 0
        )

    @patch.object(exam_service.model, "get_exam_subject_progress")
    @patch.object(exam_service.model, "get_mark_response")
    @patch.object(exam_service.model, "save_mark")
    @patch.object(exam_service.model, "get_exam_student", return_value=True)
    @patch.object(
        exam_service.model,
        "lock_exam_subject",
        return_value={
            "id": 12,
            "exam_id": 2,
            "max_marks": Decimal("50"),
            "evaluation_status": "completed",
            "evaluator_staff_id": 19,
            "exam_status": "published",
        },
    )
    def test_admin_corrections_require_reason_and_are_audited(
        self,
        _lock_subject,
        _get_exam_student,
        save_mark,
        get_mark_response,
        _get_progress,
    ):
        get_mark_response.return_value = {
            "student_id": 45,
            "name": "Student",
            "roll_number": "S-45",
            "marks_obtained": Decimal("42"),
            "is_absent": False,
            "remarks": "Corrected",
            "created_at": None,
            "updated_at": None,
        }

        result = exam_service.correct_student_marks(
            12,
            45,
            exam_service.MarksCorrection(
                marks_obtained=Decimal("42"),
                is_absent=False,
                remarks="Corrected",
                reason="Verified answer sheet",
            ),
            {"id": 7},
            self.db,
        )

        self.assertEqual(result["marks_obtained"], Decimal("42"))
        self.assertEqual(save_mark.call_args.args[6], "correction")
        self.assertEqual(save_mark.call_args.args[5], "Verified answer sheet")
        self.assertEqual(self.db.commits, 1)

    @patch.object(exam_service.model, "get_results")
    @patch.object(
        exam_service.model,
        "get_exam_ids_for_student",
        return_value={"status": "scheduled"},
    )
    @patch.object(exam_service.model, "get_role_name", return_value="student")
    def test_students_cannot_read_unpublished_results(
        self,
        _get_role,
        _get_student_exam,
        get_results,
    ):
        with self.assertRaises(HTTPException) as raised:
            exam_service.get_exam_results(
                2,
                {"role_id": 4, "person_id": 45},
                100,
                0,
                self.db,
            )

        self.assertEqual(raised.exception.status_code, 403)
        get_results.assert_not_called()

    @patch.object(exam_service.model, "get_results", return_value=[{
        "exam_id": 2,
        "exam_name": "Quarterly",
        "academic_year": "2026-2027",
        "status": "published",
        "student_id": 45,
        "student_name": "Student",
        "roll_number": "S-45",
        "subject_id": 3,
        "subject_name": "Science",
        "max_marks": Decimal("100"),
        "pass_marks": Decimal("35"),
        "marks_obtained": Decimal("80"),
        "is_absent": False,
        "remarks": None,
    }])
    @patch.object(
        exam_service.model,
        "get_exam",
        return_value={
            "id": 2,
            "name": "Quarterly",
            "academic_year": "2026-2027",
            "status": "published",
        },
    )
    @patch.object(
        exam_service.model,
        "has_staff_assignment",
        return_value=True,
    )
    @patch.object(
        exam_service.model,
        "get_active_staff",
        return_value={"id": 19, "name": "Evaluator"},
    )
    @patch.object(exam_service.model, "get_role_name", return_value="staff")
    def test_staff_result_query_is_scoped_to_assigned_evaluator(
        self,
        _get_role,
        _get_active_staff,
        has_assignment,
        _get_exam,
        get_results,
    ):
        exam_service.get_exam_results(
            2,
            {"role_id": 2, "person_id": 19},
            100,
            0,
            self.db,
        )

        has_assignment.assert_called_once_with(self.db, 2, 19)
        get_results.assert_called_once_with(
            self.db, 2, None, 19, 100, 0
        )

    @patch.object(exam_service.model, "get_results", return_value=[])
    @patch.object(
        exam_service.model,
        "get_exam",
        return_value={
            "id": 2,
            "name": "Quarterly",
            "academic_year": "2026-2027",
            "status": "completed",
        },
    )
    @patch.object(exam_service.model, "get_role_name", return_value="admin")
    def test_admin_results_are_unfiltered(self, _get_role, _get_exam, get_results):
        result = exam_service.get_exam_results(
            2,
            {"role_id": 1},
            100,
            0,
            self.db,
        )

        self.assertEqual(result["students"], [])
        get_results.assert_called_once_with(
            self.db, 2, None, None, 100, 0
        )


if __name__ == "__main__":
    unittest.main()
