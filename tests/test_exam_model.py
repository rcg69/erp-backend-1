import unittest

from models.exam_model import (
    get_results,
    list_exams,
    list_student_exam_subjects,
    list_student_exams,
)


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _Database:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.statement = None
        self.parameters = None

    def execute(self, statement, parameters):
        self.statement = str(statement)
        self.parameters = parameters
        return _Result(self.rows)


class ListExamsTests(unittest.TestCase):
    def _assert_filter_case(
        self,
        academic_year=None,
        grade_id=None,
        exam_status=None,
        expected_filters=(),
    ):
        db = _Database(rows=[{"id": 17, "name": "Quarterly"}])

        results = list_exams(
            db,
            academic_year,
            grade_id,
            exam_status,
            limit=25,
            offset=50,
        )

        self.assertEqual(results, [{"id": 17, "name": "Quarterly"}])
        self.assertIn("ORDER BY e.start_date DESC, e.id DESC", db.statement)
        self.assertIn("LIMIT :limit OFFSET :offset", db.statement)
        self.assertEqual(db.parameters["limit"], 25)
        self.assertEqual(db.parameters["offset"], 50)

        expected_parameters = {"limit", "offset"}
        for name, value in (
            ("academic_year", academic_year),
            ("grade_id", grade_id),
            ("exam_status", exam_status),
        ):
            if value is not None:
                expected_parameters.add(name)
                self.assertIn(f":{name}", db.statement)
                self.assertEqual(db.parameters[name], value)
            else:
                self.assertNotIn(name, db.parameters)
        self.assertEqual(set(db.parameters), expected_parameters)

        where_clause = db.statement.split("ORDER BY", maxsplit=1)[0]
        for expression in (
            "e.academic_year = :academic_year",
            "e.grade_id = :grade_id",
            "e.status = :exam_status",
        ):
            if expression in expected_filters:
                self.assertIn(expression, where_clause)
            else:
                self.assertNotIn(expression, where_clause)

    def test_list_exams_without_filters(self):
        self._assert_filter_case()

    def test_list_exams_filtered_by_academic_year(self):
        self._assert_filter_case(
            academic_year="2026-2027",
            expected_filters=("e.academic_year = :academic_year",),
        )

    def test_list_exams_filtered_by_grade(self):
        self._assert_filter_case(
            grade_id=12,
            expected_filters=("e.grade_id = :grade_id",),
        )

    def test_list_exams_filtered_by_status(self):
        self._assert_filter_case(
            exam_status="scheduled",
            expected_filters=("e.status = :exam_status",),
        )

    def test_list_exams_with_multiple_filters(self):
        self._assert_filter_case(
            academic_year="2026-2027",
            grade_id=12,
            exam_status="scheduled",
            expected_filters=(
                "e.academic_year = :academic_year",
                "e.grade_id = :grade_id",
                "e.status = :exam_status",
            ),
        )


class GetResultsTests(unittest.TestCase):
    def _assert_result_filters(
        self,
        student_id=None,
        staff_id=None,
        expected_filters=(),
    ):
        db = _Database(rows=[{"exam_id": 17, "student_id": 42}])

        results = get_results(
            db,
            exam_id=17,
            student_id=student_id,
            staff_id=staff_id,
            limit=25,
            offset=50,
        )

        self.assertEqual(results, [{"exam_id": 17, "student_id": 42}])
        self.assertIn("x.exam_id = :exam_id", db.statement)
        self.assertIn("e.id = :exam_id", db.statement)
        self.assertIn("ORDER BY s.roll_number, sub.name", db.statement)
        self.assertIn("LIMIT :limit OFFSET :offset", db.statement)
        self.assertEqual(db.parameters["exam_id"], 17)
        self.assertEqual(db.parameters["limit"], 25)
        self.assertEqual(db.parameters["offset"], 50)

        expected_parameters = {"exam_id", "limit", "offset"}
        if student_id is not None:
            expected_parameters.add("student_id")
            self.assertEqual(db.parameters["student_id"], student_id)
        if staff_id is not None:
            expected_parameters.add("staff_id")
            self.assertEqual(db.parameters["staff_id"], staff_id)
        self.assertEqual(set(db.parameters), expected_parameters)

        for expression in (
            "x.student_id = :student_id",
            "es.evaluator_staff_id = :staff_id",
        ):
            if expression in expected_filters:
                self.assertIn(expression, db.statement)
            else:
                self.assertNotIn(expression, db.statement)

    def test_admin_result_query_has_no_optional_filters(self):
        self._assert_result_filters()

    def test_student_result_query_filters_to_student(self):
        self._assert_result_filters(
            student_id=42,
            expected_filters=("x.student_id = :student_id",),
        )

    def test_staff_result_query_filters_to_assigned_subjects(self):
        self._assert_result_filters(
            staff_id=19,
            expected_filters=("es.evaluator_staff_id = :staff_id",),
        )

    def test_result_query_supports_both_filters(self):
        self._assert_result_filters(
            student_id=42,
            staff_id=19,
            expected_filters=(
                "x.student_id = :student_id",
                "es.evaluator_staff_id = :staff_id",
            ),
        )


class ListStudentExamsTests(unittest.TestCase):
    def test_list_student_exams_is_roster_scoped_and_excludes_drafts(self):
        db = _Database(rows=[{"id": 17, "name": "Quarterly"}])

        exams = list_student_exams(db, student_id=42, limit=25, offset=50)

        self.assertEqual(exams, [{"id": 17, "name": "Quarterly"}])
        self.assertIn("JOIN exam_students x ON x.exam_id = e.id", db.statement)
        self.assertIn("x.student_id = :student_id", db.statement)
        self.assertIn("e.status IN ('scheduled', 'completed', 'published')", db.statement)
        self.assertIn("LIMIT :limit OFFSET :offset", db.statement)
        self.assertEqual(
            db.parameters,
            {"student_id": 42, "limit": 25, "offset": 50},
        )

    def test_list_student_exam_subjects_returns_only_mark_allocations(self):
        db = _Database(rows=[{"subject_id": 3, "max_marks": 100}])

        subjects = list_student_exam_subjects(db, exam_id=17)

        self.assertEqual(subjects, [{"subject_id": 3, "max_marks": 100}])
        self.assertIn("FROM exam_subjects es", db.statement)
        self.assertIn("WHERE es.exam_id = :exam_id", db.statement)
        self.assertNotIn("evaluator_staff_id", db.statement)
        self.assertEqual(db.parameters, {"exam_id": 17})


if __name__ == "__main__":
    unittest.main()
