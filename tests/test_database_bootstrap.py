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

        grade_columns = {column["name"] for column in inspector.get_columns("grades")}
        section_columns = {column["name"] for column in inspector.get_columns("sections")}
        student_columns = {column["name"] for column in inspector.get_columns("students")}

        self.assertTrue({"academic_year", "grade", "status", "section_id", "staff_id"}.issubset(grade_columns))
        self.assertTrue({"section"}.issubset(section_columns))
        self.assertFalse("staff_id" in section_columns)
        self.assertTrue({"grade", "section"}.issubset(student_columns))

    def test_database_bootstrap_creates_staff_table(self):
        database.ensure_database_schema()
        inspector = inspect(database.engine)

        self.assertIn("staff", inspector.get_table_names())
        staff_columns = {column["name"] for column in inspector.get_columns("staff")}

        self.assertTrue({"name", "number", "status"}.issubset(staff_columns))


if __name__ == "__main__":
    unittest.main()
