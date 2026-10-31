import unittest

from database import normalize_database_url


class DatabaseConnectionSettingsTests(unittest.TestCase):
    def test_render_external_postgres_url_requires_tls_when_unspecified(self):
        url = normalize_database_url(
            "postgresql://user:password@dpg-example-a.oregon-postgres.render.com/app"
        )

        self.assertEqual(url.query["sslmode"], "require")

    def test_render_external_postgres_url_replaces_disabled_tls(self):
        url = normalize_database_url(
            "postgresql://user:password@dpg-example-a.oregon-postgres.render.com/app?sslmode=disable"
        )

        self.assertEqual(url.query["sslmode"], "require")

    def test_existing_stronger_tls_mode_is_preserved(self):
        url = normalize_database_url(
            "postgresql://user:password@dpg-example-a.oregon-postgres.render.com/app?sslmode=verify-full"
        )

        self.assertEqual(url.query["sslmode"], "verify-full")

    def test_non_render_database_url_is_unchanged(self):
        original = "postgresql://user:password@db.example.com/app"
        url = normalize_database_url(original)

        self.assertEqual(url.host, "db.example.com")
        self.assertEqual(url.query, {})


if __name__ == "__main__":
    unittest.main()
