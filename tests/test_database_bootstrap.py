import unittest

from sqlalchemy import inspect

import database


class DatabaseBootstrapTests(unittest.TestCase):
    def test_database_bootstrap_function_exists(self):
        self.assertTrue(hasattr(database, "ensure_database_schema"))
        self.assertTrue(callable(database.ensure_database_schema))

    def test_database_bootstrap_creates_split_grade_and_section_tables(self):
        database.ensure_database_schema()
        inspector = inspect(database.engine)

        self.assertIn("grades", inspector.get_table_names())
        self.assertIn("sections", inspector.get_table_names())
        self.assertIn("attendance", inspector.get_table_names())
        self.assertIn("exams", inspector.get_table_names())
        self.assertIn("exam_subjects", inspector.get_table_names())
        self.assertIn("exam_students", inspector.get_table_names())
        self.assertIn("student_marks", inspector.get_table_names())
        self.assertIn("student_marks_audit", inspector.get_table_names())
        self.assertIn("profile_images", inspector.get_table_names())
        self.assertIn("user_details", inspector.get_table_names())

        grade_columns = {column["name"] for column in inspector.get_columns("grades")}
        section_columns = {column["name"] for column in inspector.get_columns("sections")}
        student_columns = {column["name"] for column in inspector.get_columns("students")}
        attendance_columns = {
            column["name"] for column in inspector.get_columns("attendance")
        }
        exam_columns = {
            column["name"] for column in inspector.get_columns("exams")
        }
        exam_subject_columns = {
            column["name"] for column in inspector.get_columns("exam_subjects")
        }
        marks_columns = {
            column["name"] for column in inspector.get_columns("student_marks")
        }
        marks_audit_columns = {
            column["name"]
            for column in inspector.get_columns("student_marks_audit")
        }
        profile_image_columns = {
            column["name"] for column in inspector.get_columns("profile_images")
        }
        user_details_columns = {
            column["name"] for column in inspector.get_columns("user_details")
        }

        self.assertTrue({"academic_year", "grade", "status", "section_id", "staff_id"}.issubset(grade_columns))
        self.assertTrue({"section"}.issubset(section_columns))
        self.assertFalse("staff_id" in section_columns)
        self.assertTrue({"grade", "section"}.issubset(student_columns))
        self.assertIn("academic_year", attendance_columns)
        self.assertTrue(
            {
                "academic_year",
                "grade_id",
                "section_id",
                "created_by",
                "status",
            }.issubset(exam_columns)
        )
        self.assertTrue(
            {
                "exam_id",
                "subject_id",
                "evaluator_staff_id",
                "max_marks",
                "pass_marks",
                "evaluation_status",
            }.issubset(exam_subject_columns)
        )
        self.assertTrue(
            {
                "exam_subject_id",
                "student_id",
                "marks_obtained",
                "is_absent",
                "created_by",
                "updated_by",
            }.issubset(marks_columns)
        )
        self.assertTrue(
            {
                "student_mark_id",
                "action",
                "previous_marks",
                "new_marks",
                "reason",
                "changed_by",
                "changed_at",
            }.issubset(marks_audit_columns)
        )
        self.assertTrue(
            {"user_id", "filename", "content_type", "image_data"}.issubset(
                profile_image_columns
            )
        )
        self.assertTrue(
            {
                "user_id",
                "image_id",
                "full_name",
                "date_of_birth",
                "aadhaar_number",
                "mobile_number",
                "annual_family_income",
                "present_country",
                "same_as_present_address",
                "permanent_country",
            }.issubset(user_details_columns)
        )

    def test_database_bootstrap_creates_staff_table(self):
        database.ensure_database_schema()
        inspector = inspect(database.engine)

        self.assertIn("staff", inspector.get_table_names())
        staff_columns = {column["name"] for column in inspector.get_columns("staff")}

        self.assertTrue({"name", "number", "status"}.issubset(staff_columns))


if __name__ == "__main__":
    unittest.main()
