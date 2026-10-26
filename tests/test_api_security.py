import ast
import unittest
from pathlib import Path
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi import HTTPException
from exceptions.handlers import register_exception_handlers
from schemas.class_session_schema import ClassSessionUpdate
from services import attendance_service, scheduling_service
from services.scheduling_service import update_class_session


ROOT = Path(__file__).resolve().parents[1]


def _route_dependencies(filename, function_name):
    tree = ast.parse((ROOT / "api" / filename).read_text(encoding="utf-8"))
    function = next(node for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == function_name)
    names = set()
    for argument in function.args.defaults + [item for item in function.args.kw_defaults if item]:
        for node in ast.walk(argument):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Depends":
                if node.args and isinstance(node.args[0], ast.Name):
                    names.add(node.args[0].id)
    return names


class ApiSecurityTests(unittest.TestCase):
    def test_sensitive_routes_have_role_guards(self):
        guarded = {
            ("grade_api.py", "create_grade"): "require_admin",
            ("grade_api.py", "get_grades"): "require_admin_or_staff",
            ("sections_api.py", "create_section"): "require_admin",
            ("sections_api.py", "get_sections"): "require_admin_or_staff",
            ("subject_api.py", "create_subject"): "require_admin",
            ("subject_api.py", "get_subjects"): "require_admin_or_staff",
            ("scheduling_api.py", "create_timetable"): "require_admin",
            ("scheduling_api.py", "get_timetables"): "require_admin_or_staff",
            ("scheduling_api.py", "update_class_session"): "require_admin_or_staff",
            ("attendance_api.py", "get_attendance"): "require_admin_staff_or_student",
            ("attendance_api.py", "get_student_attendance_report"): "require_admin_or_staff",
            ("attendance_api.py", "get_my_attendance_report"): "require_student",
            ("attendance_api.py", "get_student_attendance_report"): "require_admin_staff_or_student",
            ("attendance_api.py", "get_attendance_record"): "require_admin_or_staff",
            ("scheduling_api.py", "get_my_class_sessions"): "require_student",
            ("scheduling_api.py", "get_class_sessions"): "require_admin_staff_or_student",
            ("scheduling_api.py", "get_sessions_for_class_on_date"): "require_admin_staff_or_student",
        }

        for (filename, function), expected_guard in guarded.items():
            with self.subTest(route=function):
                self.assertIn(expected_guard, _route_dependencies(filename, function))

    def test_unexpected_error_handler_is_registered(self):
        app = FastAPI()
        register_exception_handlers(app)
        self.assertIn(Exception, app.exception_handlers)

    def test_staff_cannot_reassign_a_session(self):
        db = MagicMock()
        with self.assertRaises(HTTPException) as raised:
            update_class_session(
                12,
                ClassSessionUpdate(staff_id=99),
                db,
                current_user={"role": "staff", "person_id": 7},
            )

        self.assertEqual(raised.exception.status_code, 403)
        db.execute.assert_not_called()

    def test_staff_can_update_status_only_for_their_assigned_session(self):
        db = MagicMock()
        ownership_result = MagicMock()
        ownership_result.first.return_value = {"id": 12}
        update_result = MagicMock()
        update_result.mappings.return_value.first.return_value = {
            "id": 12,
            "timetable_id": 3,
            "subject_id": 5,
            "staff_id": 7,
            "session_date": "2026-10-26",
            "is_conducted": True,
            "remarks": None,
        }
        db.execute.side_effect = [ownership_result, update_result]

        result = update_class_session(
            12,
            ClassSessionUpdate(is_conducted=True),
            db,
            current_user={"role": "staff", "person_id": 7},
        )

        self.assertTrue(result["is_conducted"])
        ownership_params = db.execute.call_args_list[0].args[1]
        self.assertEqual(ownership_params, {"session_id": 12, "staff_id": 7})
        db.commit.assert_called_once()

    @patch.object(attendance_service.model, "get_attendance_report_records")
    @patch.object(attendance_service.model, "get_current_academic_year_for_student")
    @patch.object(attendance_service.model, "get_student_by_id")
    def test_student_attendance_uses_authenticated_student_id(
        self, get_student, get_years, get_records
    ):
        get_student.return_value = {
            "id": 23, "name": "Learner", "roll_number": "R23",
            "grade": "8", "section": "B",
        }
        get_years.return_value = ["2026-2027"]
        get_records.return_value = [
            {"status": "PRESENT"}, {"status": "ABSENT"},
        ]

        report = attendance_service.get_my_attendance_report(23, None, db=None)

        get_student.assert_called_once_with(None, 23)
        get_records.assert_called_once_with(None, 23, "2026-2027")
        self.assertEqual(report["student"]["id"], 23)
        self.assertEqual(report["total_classes"], 2)
        self.assertEqual(report["percentage"], 50.0)

    @patch.object(attendance_service.model, "get_student_by_id")
    def test_student_cannot_view_another_roll_number(self, get_student):
        get_student.return_value = {
            "id": 23, "name": "Learner", "roll_number": "R23",
            "grade": "8", "section": "B",
        }

        with self.assertRaises(HTTPException) as raised:
            attendance_service.get_student_attendance_report(
                "R99", None, None, "2026-2027", db=None,
                current_user={"role": "student", "person_id": 23},
            )

        self.assertEqual(raised.exception.status_code, 404)
        get_student.assert_called_once_with(None, 23)

    @patch.object(attendance_service.model, "get_all_attendance")
    def test_general_attendance_list_is_scoped_to_student(self, get_all_attendance):
        attendance_service.get_attendance(
            db="db",
            academic_year="2026-2027",
            current_user={"role": "student", "person_id": 23},
        )

        get_all_attendance.assert_called_once_with("db", "2026-2027", 23)

    @patch.object(scheduling_service, "get_sessions_for_class_on_date")
    def test_student_sessions_derive_class_from_student_id(self, get_sessions):
        db = MagicMock()
        db.execute.return_value.mappings.return_value.all.return_value = [
            {"grade_id": 18, "section_id": 4}
        ]
        get_sessions.return_value = {"grade_id": 18, "section_id": 4, "sessions": []}
        target_date = date(2026, 10, 26)

        result = scheduling_service.get_student_sessions_for_date(23, target_date, db)

        self.assertEqual(result["grade_id"], 18)
        get_sessions.assert_called_once_with(18, 4, target_date, db)
        self.assertEqual(db.execute.call_args.args[1], {"student_id": 23})


if __name__ == "__main__":
    unittest.main()
