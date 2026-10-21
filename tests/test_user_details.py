import unittest

from fastapi import HTTPException

from schemas.user_details_schema import UserDetailsUpdate
from services.user_details_service import (
    PRESENT_ADDRESS_FIELDS,
    _authorize_user_details_access,
    update_user_details,
)


class _Result:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def first(self):
        return self.row

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _ProfileSession:
    def __init__(self):
        self.profile = {
            "same_as_present_address": False,
            **{f"present_{field}": None for field in PRESENT_ADDRESS_FIELDS},
            **{f"permanent_{field}": None for field in PRESENT_ADDRESS_FIELDS},
        }
        self.update_parameters = None

    def execute(self, statement, parameters=None):
        query = str(statement)
        if "SELECT id FROM users" in query:
            return _Result((1,))
        if "INSERT INTO user_details" in query:
            return _Result()
        if "SELECT" in query and "FROM user_details" in query:
            return _Result(dict(self.profile))
        if "UPDATE user_details" in query:
            self.update_parameters = parameters
            self.profile.update(
                {
                    key: value
                    for key, value in parameters.items()
                    if key != "user_id"
                }
            )
            return _Result()
        raise AssertionError(f"Unexpected query: {query}")

    def commit(self):
        pass

    def rollback(self):
        pass


class UserDetailsTests(unittest.TestCase):
    def test_profile_update_accepts_personal_contact_family_and_address_fields(self):
        details = UserDetailsUpdate.model_validate(
            {
                "full_name": "Rahul Kumar",
                "gender": "Male",
                "date_of_birth": "2008-03-12",
                "nationality": "Indian",
                "mobile_number": "9876543210",
                "father_name": "Father Kumar",
                "annual_family_income": "120000.00",
                "present_country": "India",
                "permanent_country": "India",
            }
        )

        self.assertEqual(details.full_name, "Rahul Kumar")
        self.assertEqual(details.mobile_number, "9876543210")
        self.assertEqual(details.father_name, "Father Kumar")
        self.assertEqual(details.model_dump(exclude_unset=True)["present_country"], "India")

    def test_same_present_address_copies_and_tracks_address_fields(self):
        db = _ProfileSession()
        details = UserDetailsUpdate(
            present_street_locality="Main Road",
            present_village_town_city="Hyderabad",
            same_as_present_address=True,
        )

        result = update_user_details(1, details, db, {"id": 1})

        self.assertEqual(
            db.update_parameters["permanent_street_locality"],
            "Main Road",
        )
        self.assertEqual(
            db.update_parameters["permanent_village_town_city"],
            "Hyderabad",
        )
        self.assertTrue(result["same_as_present_address"])


class _AccessSession:
    def __init__(self, role_name, student, assignments=(), staff_active=True):
        self.role_name = role_name
        self.student = student
        self.assignments = assignments
        self.staff_active = staff_active

    def execute(self, statement, parameters=None):
        query = str(statement)
        if "SELECT role_name FROM roles" in query:
            return _Result({"role_name": self.role_name})
        if "FROM users u" in query:
            return _Result(
                {"id": 42, "person_id": 501, "role_name": "student"}
            )
        if "FROM staff" in query:
            return _Result((12,) if self.staff_active else None)
        if "FROM students" in query:
            return _Result(self.student)
        if "FROM grades g" in query:
            return _Result(rows=self.assignments)
        raise AssertionError(f"Unexpected query: {query}")


class UserDetailsAccessTests(unittest.TestCase):
    def setUp(self):
        self.teacher = {"id": 8, "role_id": 2, "person_id": 12}
        self.student = {"id": 501, "grade": "10th Class", "section": "A"}

    def test_assigned_teacher_can_access_student_profile(self):
        db = _AccessSession(
            "staff",
            self.student,
            [{"grade": "10", "section": "a"}],
        )

        _authorize_user_details_access(42, self.teacher, db)

    def test_teacher_cannot_access_unassigned_student_profile(self):
        db = _AccessSession("staff", self.student)

        with self.assertRaises(HTTPException) as raised:
            _authorize_user_details_access(42, self.teacher, db)

        self.assertEqual(raised.exception.status_code, 403)

    def test_teacher_cannot_access_profile_if_staff_record_is_inactive(self):
        db = _AccessSession(
            "staff",
            self.student,
            [{"grade": "10", "section": "A"}],
            staff_active=False,
        )

        with self.assertRaises(HTTPException) as raised:
            _authorize_user_details_access(42, self.teacher, db)

        self.assertEqual(raised.exception.status_code, 403)

    def test_admin_can_access_any_student_profile(self):
        db = _AccessSession("admin", self.student)

        _authorize_user_details_access(
            42,
            {"id": 1, "role_id": 1, "person_id": None},
            db,
        )


if __name__ == "__main__":
    unittest.main()
