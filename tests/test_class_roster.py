import unittest
from datetime import date, datetime, timezone

from fastapi import HTTPException

from services.class_roster_service import get_class_roster


class _Result:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def mappings(self):
        return self

    def first(self):
        return self.row

    def all(self):
        return self.rows


class _RosterDatabase:
    def __init__(self, class_row, students=None):
        self.results = [_Result(row=class_row), _Result(rows=students)]
        self.statements = []

    def execute(self, statement, parameters=None):
        self.statements.append((str(statement), parameters))
        return self.results.pop(0)


class ClassRosterTests(unittest.TestCase):
    def setUp(self):
        self.class_row = {
            "id": 9,
            "grade": "10",
            "academic_year": "2026-2027",
            "staff_id": 15,
            "section_id": 3,
            "section": "A",
        }
        self.students = [
            {
                "id": 42,
                "user_id": 71,
                "name": "Rahul Kumar",
                "roll_number": "23A91A0502",
                "admission_date": date(2026, 6, 1),
                "parent_name": "Parent Name",
                "mobile_number": "9876543210",
                "grade": "10",
                "section": "A",
                "status": "active",
                "created_at": datetime.now(timezone.utc),
            }
        ]

    def test_assigned_staff_receives_only_active_class_students(self):
        db = _RosterDatabase(self.class_row, self.students)

        roster = get_class_roster(
            "10",
            "A",
            "2026-2027",
            {"role": "staff", "person_id": 15},
            db,
        )

        self.assertEqual(roster["count"], 1)
        self.assertEqual(roster["students"], self.students)
        self.assertIn("LOWER(status) = 'active'", db.statements[1][0])
        self.assertIn("AS user_id", db.statements[1][0])
        self.assertEqual(
            db.statements[0][1],
            {"grade": "10", "section": "A", "academic_year": "2026-2027"},
        )

    def test_staff_cannot_read_another_staff_members_class(self):
        db = _RosterDatabase(self.class_row)

        with self.assertRaises(HTTPException) as raised:
            get_class_roster(
                "10",
                "A",
                "2026-2027",
                {"role": "staff", "person_id": 99},
                db,
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(len(db.statements), 1)

    def test_admin_can_read_any_active_class_roster(self):
        db = _RosterDatabase(self.class_row, self.students)

        roster = get_class_roster(
            "10",
            "A",
            "2026-2027",
            {"role": "admin"},
            db,
        )

        self.assertEqual(roster["academic_year"], "2026-2027")
        self.assertEqual(roster["students"], self.students)

    def test_missing_active_class_returns_not_found(self):
        db = _RosterDatabase(None)

        with self.assertRaises(HTTPException) as raised:
            get_class_roster(
                "10",
                "A",
                "2026-2027",
                {"role": "admin"},
                db,
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(len(db.statements), 1)


if __name__ == "__main__":
    unittest.main()
