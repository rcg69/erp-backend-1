import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from services import password_reset_service as reset_service


class PasswordResetServiceTests(unittest.TestCase):
    @patch.object(reset_service.auth_model, "get_user_by_email")
    @patch.object(reset_service, "send_password_reset_email")
    def test_unknown_email_gets_generic_response_without_mail(self, send_email, get_user):
        get_user.return_value = None

        result = reset_service.request_password_reset("unknown@example.com", MagicMock())

        self.assertEqual(result["message"], reset_service.GENERIC_REQUEST_MESSAGE)
        send_email.assert_not_called()

    @patch.object(reset_service.auth_model, "get_user_by_email")
    @patch.object(reset_service.auth_model, "create_password_reset_token")
    @patch.object(reset_service, "send_password_reset_email")
    @patch.object(reset_service.secrets, "token_urlsafe", return_value="raw-reset-token-value")
    def test_reset_request_stores_only_token_digest_and_emails_link(
        self, token_factory, send_email, create_token, get_user
    ):
        get_user.return_value = {"id": 7, "is_active": True}
        db = MagicMock()

        result = reset_service.request_password_reset("USER@example.com", db)

        self.assertEqual(result["message"], reset_service.GENERIC_REQUEST_MESSAGE)
        self.assertEqual(create_token.call_args.args[1], 7)
        stored_digest = create_token.call_args.args[2]
        self.assertEqual(stored_digest, reset_service._token_hash("raw-reset-token-value"))
        self.assertNotEqual(stored_digest, "raw-reset-token-value")
        self.assertIn("token=raw-reset-token-value", send_email.call_args.args[1])
        db.commit.assert_called_once()

    @patch.object(reset_service.auth_model, "consume_password_reset_token", return_value=7)
    @patch.object(reset_service.auth_model, "update_user_password")
    @patch.object(reset_service, "hash_password", return_value="argon2-hash")
    def test_confirm_changes_password_and_commits(self, hash_password, update_password, consume):
        db = MagicMock()

        result = reset_service.confirm_password_reset("one-time-token", "long-enough-password", db)

        self.assertTrue(result["success"])
        consume.assert_called_once_with(db, reset_service._token_hash("one-time-token"))
        update_password.assert_called_once_with(db, 7, "argon2-hash")
        db.commit.assert_called_once()

    @patch.object(reset_service.auth_model, "consume_password_reset_token", return_value=None)
    def test_confirm_rejects_invalid_or_expired_token(self, consume):
        db = MagicMock()

        with self.assertRaises(HTTPException) as raised:
            reset_service.confirm_password_reset("bad-token", "long-enough-password", db)

        self.assertEqual(raised.exception.status_code, 400)
        db.rollback.assert_called_once()
        db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
