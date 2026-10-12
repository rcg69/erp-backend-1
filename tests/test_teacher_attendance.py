import unittest

from fastapi import HTTPException

from schemas.attendance_schema import TeacherAttendanceBulkCreate
from security.auth import require_staff
from services.user_create_service import _validate_person_for_role


class FakeResult:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class FakeDatabase:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.statements = []

    def execute(self, statement, parameters=None):
        self.statements.append((str(statement), parameters))
        return FakeResult(next(self.rows))


class TeacherAttendanceTests(unittest.TestCase):
    def test_staff_users_must_link_to_a_staff_record(self):
        db = FakeDatabase([{"id": 14}])

        _validate_person_for_role(db, "staff", 14)

        self.assertIn("FROM staff", db.statements[0][0])
        self.assertEqual(db.statements[0][1], {"person_id": 14})

    def test_staff_users_cannot_link_to_missing_staff(self):
        db = FakeDatabase([None])

        with self.assertRaises(HTTPException) as raised:
            _validate_person_for_role(db, "staff", 14)

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("existing staff member", raised.exception.detail)

    def test_staff_access_uses_user_person_id_as_staff_id(self):
        db = FakeDatabase([{"role_name": "staff"}, {"id": 14}])
        user = {"role_id": 2, "person_id": 14}

        authenticated_user = require_staff(user, db)

        self.assertIs(authenticated_user, user)
        self.assertEqual(authenticated_user["role"], "staff")
        self.assertEqual(db.statements[1][1], {"staff_id": 14})

    def test_non_staff_users_cannot_use_teacher_attendance(self):
        db = FakeDatabase([{"role_name": "student"}])

        with self.assertRaises(HTTPException) as raised:
            require_staff({"role_id": 3, "person_id": 14}, db)

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, "Staff access required")

    def test_teacher_attendance_payload_requires_records(self):
        with self.assertRaises(ValueError):
            TeacherAttendanceBulkCreate(records=[])


if __name__ == "__main__":
    unittest.main()
