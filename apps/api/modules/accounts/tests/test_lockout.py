"""Verrouillage login : trop de tentatives echouees -> compte bloque.

Le test est independant du backend de cache : il observe uniquement le
comportement du service et de l'endpoint, sans supposer locmem/Redis.

Chaque test utilise un email unique : le compteur de verrouillage vit
dans le cache partage du process et n'est pas isole par le cycle de vie
du test.
"""

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from ..services import (
    login_is_locked,
    record_login_failure,
    record_login_success,
)

User = get_user_model()

PASSWORD = "Une-phrase-secrete-2026!"


class LoginLockoutApiTests(APITestCase):
    """Verrouillage via l'endpoint /auth/login/ (backend de cache quelconque)."""

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.email = f"lockout-{id(self):x}@example.com"
        self.user = User.objects.create_user(
            phone="+2250700001901",
            password=PASSWORD,
            first_name="Awa",
            last_name="Kone",
            email=self.email,
            phone_verified_at=timezone.now(),
        )

    def _csrf_token(self) -> str:
        response = self.client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["csrf_token"]

    def _login(self, email, password):
        token = self._csrf_token()
        return self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": password},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

    @override_settings(LOGIN_LOCKOUT_MAX_ATTEMPTS=3)
    def test_account_locked_after_max_failures_even_with_correct_password(self):
        for _ in range(3):
            response = self._login(self.email, "mot-de-passe-incorrect")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        blocked = self._login(self.email, PASSWORD)
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tentatives", blocked.data["detail"].lower())
        self.assertTrue(login_is_locked(email=self.email))

    @override_settings(LOGIN_LOCKOUT_MAX_ATTEMPTS=3)
    def test_failures_below_threshold_do_not_block_correct_login(self):
        for _ in range(2):
            self._login(self.email, "mot-de-passe-incorrect")

        response = self._login(self.email, PASSWORD)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(LOGIN_LOCKOUT_MAX_ATTEMPTS=3)
    def test_lockout_is_keyed_per_email_not_per_account(self):
        other = User.objects.create_user(
            phone="+2250700001902",
            password=PASSWORD,
            email=f"autre-lockout-{id(self):x}@example.com",
            phone_verified_at=timezone.now(),
        )
        for _ in range(3):
            self._login(self.email, "mot-de-passe-incorrect")

        self.assertTrue(login_is_locked(email=self.email))
        self.assertFalse(login_is_locked(email=other.email))
        response = self._login(other.email, PASSWORD)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class LoginLockoutServiceTests(APITestCase):
    """Verrouillage au niveau service : independant du backend de cache."""

    def setUp(self):
        self.email = f"service-lockout-{id(self):x}@example.com"

    @override_settings(LOGIN_LOCKOUT_MAX_ATTEMPTS=3)
    def test_service_blocks_after_max_failures(self):
        for _ in range(3):
            record_login_failure(email=self.email)
        self.assertTrue(login_is_locked(email=self.email))

    @override_settings(LOGIN_LOCKOUT_MAX_ATTEMPTS=3)
    def test_service_below_threshold_is_not_locked(self):
        for _ in range(2):
            record_login_failure(email=self.email)
        self.assertFalse(login_is_locked(email=self.email))

    @override_settings(LOGIN_LOCKOUT_MAX_ATTEMPTS=3)
    def test_successful_login_clears_lockout(self):
        for _ in range(3):
            record_login_failure(email=self.email)
        self.assertTrue(login_is_locked(email=self.email))
        record_login_success(email=self.email)
        self.assertFalse(login_is_locked(email=self.email))

    @override_settings(LOGIN_LOCKOUT_MAX_ATTEMPTS=3)
    def test_lockout_is_independent_across_emails(self):
        other = f"autre-service-lockout-{id(self):x}@example.com"
        for _ in range(3):
            record_login_failure(email=self.email)
        self.assertTrue(login_is_locked(email=self.email))
        self.assertFalse(login_is_locked(email=other))
