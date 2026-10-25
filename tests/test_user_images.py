import unittest
from datetime import datetime, timezone

from fastapi import HTTPException

from services.user_image_service import (
    MAX_IMAGE_SIZE,
    get_user_image,
    replace_user_image,
    validate_image,
)


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


class _ImageSession:
    def __init__(self, actor_role, target_user, assignments=None):
        self.actor_role = actor_role
        self.target_user = target_user
        self.assignments = assignments or []
        self.image_row = {
            "id": 23,
            "user_id": target_user["id"],
            "filename": "portrait.png",
            "content_type": "image/png",
            "image_data": b"\x89PNG\r\n\x1a\n",
            "size_bytes": 12,
            "created_at": datetime.now(timezone.utc),
        }
        self.read_image_row = {
            key: value for key, value in self.image_row.items()
            if key != "size_bytes"
        }
        self.statements = []
        self.committed = False
        self.rolled_back = False

    def execute(self, statement, parameters=None):
        query = str(statement)
        self.statements.append((query, parameters))
        if "SELECT role_name FROM roles" in query:
            return _Result({"role_name": self.actor_role})
        if "FROM users u" in query:
            return _Result(self.target_user)
        if "FROM staff" in query:
            return _Result((12,))
        if "FROM students" in query:
            return _Result({"id": 42, "grade": "10th Class", "section": "A"})
        if "FROM grades g" in query:
            return _Result(rows=self.assignments)
        if "INSERT INTO profile_images" in query:
            return _Result(self.image_row)
        if "FROM profile_images" in query:
            return _Result(self.read_image_row)
        if "INSERT INTO user_details" in query:
            return _Result()
        if "DELETE FROM profile_images" in query:
            return _Result()
        raise AssertionError(f"Unexpected query: {query}")

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class UserImageTests(unittest.TestCase):
    def test_get_image_returns_stored_bytes(self):
        db = _ImageSession(
            "staff",
            {"id": 8, "person_id": 12, "role_name": "staff"},
        )

        image = get_user_image(23, db)

        self.assertEqual(image["id"], 23)
        self.assertEqual(image["image_data"], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(image["content_type"], "image/png")
        self.assertIn("created_at", image)

    def test_get_image_converts_database_memoryview_to_bytes(self):
        db = _ImageSession(
            "staff",
            {"id": 8, "person_id": 12, "role_name": "staff"},
        )
        db.read_image_row["image_data"] = memoryview(b"\x89PNG\r\n\x1a\n")

        image = get_user_image(23, db)

        self.assertIsInstance(image["image_data"], bytes)
        self.assertEqual(image["image_data"], b"\x89PNG\r\n\x1a\n")

    def test_validates_mime_type_and_image_signature(self):
        image = b"\x89PNG\r\n\x1a\nimage bytes"

        self.assertEqual(validate_image("image/png", image), "image/png")

        with self.assertRaises(HTTPException) as raised:
            validate_image("image/jpeg", image)

        self.assertEqual(raised.exception.status_code, 400)

    def test_rejects_images_larger_than_five_megabytes(self):
        with self.assertRaises(HTTPException) as raised:
            validate_image("image/png", b"\x89PNG\r\n\x1a\n" + b"x" * MAX_IMAGE_SIZE)

        self.assertEqual(raised.exception.status_code, 413)

    def test_assigned_teacher_can_replace_student_image(self):
        db = _ImageSession(
            "staff",
            {"id": 42, "person_id": 42, "role_name": "student"},
            [{"grade": "10", "section": "a"}],
        )

        result = replace_user_image(
            42,
            {"id": 8, "role_id": 2, "person_id": 12},
            "C:\\uploads\\portrait.png",
            "image/png",
            b"\x89PNG\r\n\x1a\n",
            db,
        )

        self.assertEqual(result["id"], 23)
        self.assertEqual(result["user_id"], 42)
        self.assertTrue(db.committed)
        self.assertEqual(
            db.statements[-2][1],
            {"user_id": 42, "image_id": 23},
        )
        self.assertEqual(db.statements[-3][1]["filename"], "portrait.png")
        cleanup_query, cleanup_parameters = db.statements[-1]
        self.assertIn("DELETE FROM profile_images", cleanup_query)
        self.assertIn("id <> :image_id", cleanup_query)
        self.assertEqual(cleanup_parameters, {"user_id": 42, "image_id": 23})

    def test_staff_can_replace_their_own_image(self):
        db = _ImageSession(
            "staff",
            {"id": 8, "person_id": 12, "role_name": "staff"},
        )

        result = replace_user_image(
            8,
            {"id": 8, "role_id": 2, "person_id": 12},
            "portrait.png",
            "image/png",
            b"\x89PNG\r\n\x1a\n",
            db,
        )

        self.assertEqual(result["user_id"], 8)
        self.assertTrue(db.committed)

    def test_admin_can_replace_any_user_image(self):
        db = _ImageSession(
            "admin",
            {"id": 42, "person_id": 42, "role_name": "student"},
        )

        result = replace_user_image(
            42,
            {"id": 1, "role_id": 1, "person_id": None},
            "portrait.png",
            "image/png",
            b"\x89PNG\r\n\x1a\n",
            db,
        )

        self.assertEqual(result["user_id"], 42)
        self.assertTrue(db.committed)

    def test_teacher_cannot_replace_unassigned_student_image(self):
        db = _ImageSession(
            "teacher",
            {"id": 42, "person_id": 42, "role_name": "student"},
        )

        with self.assertRaises(HTTPException) as raised:
            replace_user_image(
                42,
                {"id": 8, "role_id": 2, "person_id": 12},
                "portrait.png",
                "image/png",
                b"\x89PNG\r\n\x1a\n",
                db,
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertTrue(db.rolled_back)
        self.assertFalse(any("INSERT INTO profile_images" in query for query, _ in db.statements))

    def test_students_cannot_change_any_profile_image(self):
        db = _ImageSession(
            "student",
            {"id": 42, "person_id": 42, "role_name": "student"},
        )

        with self.assertRaises(HTTPException) as raised:
            replace_user_image(
                42,
                {"id": 42, "role_id": 3, "person_id": 42},
                "portrait.png",
                "image/png",
                b"\x89PNG\r\n\x1a\n",
                db,
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertTrue(db.rolled_back)


if __name__ == "__main__":
    unittest.main()
