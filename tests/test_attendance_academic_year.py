import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services import attendance_service


class AttendanceAcademicYearTests(unittest.TestCase):
    def setUp(self):
        self.student = {
            "id": 14,
            "name": "Student",
            "roll_number": "S-14",
            "grade": "10",
            "section": "A",
        }
        self.records = [
            {
                "attendance_id": 21,
                "status": "PRESENT",
            }
        ]

    @patch.object(
        attendance_service.model,
        "get_attendance_report_records",
    )
    @patch.object(
        attendance_service.model,
        "get_current_academic_year_for_student",
    )
    @patch.object(
        attendance_service.model,
        "get_student_candidates_by_roll",
    )
    def test_report_defaults_to_the_current_class_year(
        self,
        get_candidates,
        get_current_years,
        get_records,
    ):
        get_candidates.return_value = [self.student]
        get_current_years.return_value = ["2026-2027"]
        get_records.return_value = self.records

        report = attendance_service.get_student_attendance_report(
            "S-14", None, None, None, db=None
        )

        self.assertEqual(report["academic_year"], "2026-2027")
        self.assertEqual(report["total_classes"], 1)
        get_records.assert_called_once_with(None, 14, "2026-2027")

    @patch.object(
        attendance_service.model,
        "get_attendance_report_records",
    )
    @patch.object(
        attendance_service.model,
        "get_current_academic_year_for_student",
    )
    @patch.object(
        attendance_service.model,
        "get_student_candidates_by_roll",
    )
    def test_report_can_select_a_previous_year(
        self,
        get_candidates,
        get_current_years,
        get_records,
    ):
        get_candidates.return_value = [self.student]
        get_records.return_value = self.records

        report = attendance_service.get_student_attendance_report(
            "S-14", None, None, "2025-2026", db=None
        )

        self.assertEqual(report["academic_year"], "2025-2026")
        get_current_years.assert_not_called()
        get_records.assert_called_once_with(None, 14, "2025-2026")

    @patch.object(
        attendance_service.model,
        "get_current_academic_year_for_student",
        return_value=["2026-2027", "2025-2026"],
    )
    @patch.object(
        attendance_service.model,
        "get_student_candidates_by_roll",
        return_value=[{
            "id": 14,
            "name": "Student",
            "roll_number": "S-14",
            "grade": "10",
            "section": "A",
        }],
    )
    def test_report_requires_year_when_active_year_is_ambiguous(
        self,
        _get_candidates,
        _get_current_years,
    ):
        with self.assertRaises(HTTPException) as raised:
            attendance_service.get_student_attendance_report(
                "S-14", None, None, None, db=None
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("provide academic_year", raised.exception.detail)

    def test_attendance_cannot_be_saved_without_session_year(self):
        with self.assertRaises(HTTPException) as raised:
            attendance_service._require_session_academic_year(
                {"academic_year": None}
            )

        self.assertEqual(raised.exception.status_code, 409)

    @patch.object(
        attendance_service.model,
        "get_all_attendance",
        return_value=[],
    )
    def test_attendance_list_can_filter_by_year(self, get_all_attendance):
        attendance_service.get_attendance(db=None, academic_year=" 2025-2026 ")

        get_all_attendance.assert_called_once_with(None, "2025-2026")

    def test_attendance_list_rejects_blank_year_filter(self):
        with self.assertRaises(HTTPException) as raised:
            attendance_service.get_attendance(db=None, academic_year="  ")

        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
