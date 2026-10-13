from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class CreateUserCommandTests(TestCase):
    def run_command(self, emails, passwords):
        with patch("builtins.input", side_effect=emails), patch("sme.management.commands.createuser.getpass", side_effect=passwords):
            call_command("createuser", stdout=StringIO(), stderr=StringIO())

    def test_creates_active_regular_user_with_hashed_password(self):
        self.run_command(["  Person@Example.org "], ["Secure-long-secret-2026!", "Secure-long-secret-2026!"])
        user = get_user_model().objects.get(email="person@example.org")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("Secure-long-secret-2026!"))
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/fontes/").status_code, 200)
        self.assertEqual(self.client.post("/api/fontes/").status_code, 403)

    def test_retries_invalid_duplicate_email_and_bad_passwords(self):
        User = get_user_model()
        original = User.objects.create_superuser("taken@example.org", "Original-secret-2026!")
        self.run_command(["invalid", "TAKEN@example.org", "new@example.org"],
                         ["one", "two", "short", "short", "Secure-long-secret-2026!", "Secure-long-secret-2026!"])
        self.assertEqual(User.objects.count(), 2)
        original.refresh_from_db()
        self.assertTrue(original.is_staff)
        self.assertTrue(original.check_password("Original-secret-2026!"))
        self.assertTrue(User.objects.get(email="new@example.org").check_password("Secure-long-secret-2026!"))

    def test_cancel_before_save_creates_nothing(self):
        with self.assertRaises(CommandError):
            self.run_command(["new@example.org"], [KeyboardInterrupt()])
        self.assertFalse(get_user_model().objects.exists())
