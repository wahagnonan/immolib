from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from modules.documents.models import NotificationDelivery

from ..models import AccountOtpChallenge
from ..services import account_otp_code_for


class AuthenticationApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = get_user_model().objects.create_user(
            phone="+2250700000900",
            password="Une-phrase-secrete-2026!",
            first_name="Awa",
            last_name="Kone",
            email="awa@example.com",
        )

    def _csrf_token(self) -> str:
        response = self.client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("csrftoken", self.client.cookies)
        return response.data["csrf_token"]

    def _login(self):
        token = self._csrf_token()
        return self.client.post(
            "/api/v1/auth/login/",
            {
                "email": self.user.email,
                "password": "Une-phrase-secrete-2026!",
            },
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

    def test_csrf_endpoint_sets_cookie(self):
        response = self.client.get("/api/v1/auth/csrf/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["csrf_token"])
        self.assertIn("csrftoken", self.client.cookies)

    def test_login_rejects_request_without_csrf_token(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "Une-phrase-secrete-2026!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_creates_session_and_returns_safe_profile(self):
        response = self._login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sessionid", self.client.cookies)
        self.assertEqual(response.data["user"]["phone"], self.user.phone)
        self.assertEqual(response.data["user"]["full_name"], "Awa Kone")
        self.assertNotIn("password", response.data["user"])
        self.assertNotIn("is_superuser", response.data["user"])

        me_response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["user"]["id"], str(self.user.id))

    def test_login_uses_generic_error_for_invalid_credentials(self):
        token = self._csrf_token()
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "mot-de-passe-incorrect"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"], "Email ou mot de passe incorrect."
        )

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        token = self._csrf_token()

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "Une-phrase-secrete-2026!"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"], "Email ou mot de passe incorrect."
        )

    @override_settings(EXPOSE_TEST_OTP=True)
    def test_registration_prefers_email_verification_and_opens_session(self):
        payload = {
            "phone": "+2250500000901",
            "password": "Nouvelle-phrase-secrete-2026!",
            "password_confirmation": "Nouvelle-phrase-secrete-2026!",
            "first_name": "Mariam",
            "last_name": "Yao",
            "email": "MARIAM@example.com",
        }
        rejected = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(rejected.status_code, status.HTTP_403_FORBIDDEN)

        token = self._csrf_token()
        response = self.client.post(
            "/api/v1/auth/register/",
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = get_user_model().objects.get(phone=payload["phone"])
        self.assertTrue(created.check_password(payload["password"]))
        self.assertEqual(created.email, "mariam@example.com")
        self.assertIsNone(created.phone_verified_at)
        self.assertIsNone(created.email_verified_at)
        self.assertTrue(response.data["verification_required"])
        self.assertEqual(response.data["verification_channel"], "EMAIL")
        self.assertNotIn("sessionid", self.client.cookies)
        challenge = AccountOtpChallenge.objects.get(user=created)
        self.assertEqual(
            challenge.purpose,
            AccountOtpChallenge.Purpose.EMAIL_VERIFICATION,
        )
        self.assertEqual(challenge.destination, "mariam@example.com")
        self.assertEqual(response.data["otp_code"], account_otp_code_for(challenge))
        self.assertTrue(
            NotificationDelivery.objects.filter(
                account_challenge=challenge,
                kind=NotificationDelivery.Kind.ACCOUNT_OTP,
                channel=NotificationDelivery.Channel.EMAIL,
            ).exists()
        )
        wrong_code = "000000" if response.data["otp_code"] != "000000" else "000001"

        blocked_login = self.client.post(
            "/api/v1/auth/login/",
            {"email": "mariam@example.com", "password": payload["password"]},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(blocked_login.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(blocked_login.data["contact_verification_required"])

        wrong = self.client.post(
            "/api/v1/auth/email-verification/confirm/",
            {"phone": payload["phone"], "code": wrong_code},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(wrong.status_code, status.HTTP_400_BAD_REQUEST)
        challenge.refresh_from_db()
        self.assertEqual(challenge.attempts, 1)

        verified = self.client.post(
            "/api/v1/auth/email-verification/confirm/",
            {"phone": payload["phone"], "code": response.data["otp_code"]},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        created.refresh_from_db()
        self.assertIsNotNone(created.email_verified_at)
        self.assertIsNone(created.phone_verified_at)
        self.assertIn("sessionid", self.client.cookies)

    @override_settings(EXPOSE_TEST_OTP=True)
    def test_registration_without_email_falls_back_to_phone_sms(self):
        token = self._csrf_token()
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "phone": "+2250500000999",
                "password": "Nouvelle-phrase-secrete-2026!",
                "password_confirmation": "Nouvelle-phrase-secrete-2026!",
                "first_name": "Sans",
                "last_name": "Email",
            },
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["verification_channel"], "SMS")
        challenge = AccountOtpChallenge.objects.get(user__phone="+2250500000999")
        self.assertEqual(
            challenge.purpose,
            AccountOtpChallenge.Purpose.PHONE_VERIFICATION,
        )
        self.assertEqual(challenge.channel, AccountOtpChallenge.Channel.SMS)

    def test_registration_rejects_duplicate_phone_and_weak_password(self):
        token = self._csrf_token()
        duplicate = self.client.post(
            "/api/v1/auth/register/",
            {
                "phone": self.user.phone,
                "password": "Autre-phrase-secrete-2026!",
                "password_confirmation": "Autre-phrase-secrete-2026!",
            },
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        weak = self.client.post(
            "/api/v1/auth/register/",
            {
                "phone": "+2250500000902",
                "password": "password",
                "password_confirmation": "password",
            },
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", duplicate.data)
        self.assertEqual(weak.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(EXPOSE_TEST_OTP=True, ACCOUNT_OTP_COOLDOWN_SECONDS=60)
    def test_phone_verification_resend_uses_cooldown(self):
        user = get_user_model().objects.create_user(
            phone="+2250500000903",
            password="Une-phrase-secrete-2026!",
            phone_verified_at=None,
        )
        token = self._csrf_token()

        first = self.client.post(
            "/api/v1/auth/phone-verification/request/",
            {"phone": user.phone},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        second = self.client.post(
            "/api/v1/auth/phone-verification/request/",
            {"phone": user.phone},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data["detail"], second.data["detail"])
        self.assertEqual(first.data["otp_code"], second.data["otp_code"])
        self.assertEqual(AccountOtpChallenge.objects.filter(user=user).count(), 1)
        self.assertEqual(
            NotificationDelivery.objects.filter(account_challenge__user=user).count(),
            1,
        )

    @override_settings(EXPOSE_TEST_OTP=True)
    def test_password_reset_is_generic_and_code_is_single_use(self):
        token = self._csrf_token()
        unknown = self.client.post(
            "/api/v1/auth/password-reset/request/",
            {"phone": "+2250101010101"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        known = self.client.post(
            "/api/v1/auth/password-reset/request/",
            {"phone": self.user.phone},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(unknown.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown.data["detail"], known.data["detail"])
        self.assertNotIn("otp_code", unknown.data)
        challenge = AccountOtpChallenge.objects.get(
            user=self.user,
            purpose=AccountOtpChallenge.Purpose.PASSWORD_RESET,
        )
        self.assertEqual(known.data["otp_code"], account_otp_code_for(challenge))

        payload = {
            "phone": self.user.phone,
            "code": known.data["otp_code"],
            "password": "Nouveau-secret-ImmoLib-2026!",
            "password_confirmation": "Nouveau-secret-ImmoLib-2026!",
        }
        confirmed = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        reused = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(confirmed.status_code, status.HTTP_200_OK)
        self.assertEqual(reused.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(payload["password"]))
        challenge.refresh_from_db()
        self.assertIsNotNone(challenge.consumed_at)

    def test_password_reset_request_requires_csrf(self):
        response = self.client.post(
            "/api/v1/auth/password-reset/request/",
            {"phone": self.user.phone},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(ACCOUNT_OTP_MAX_ATTEMPTS=2)
    def test_account_otp_is_consumed_after_attempt_limit(self):
        user = get_user_model().objects.create_user(
            phone="+2250500000904",
            password="Une-phrase-secrete-2026!",
            phone_verified_at=None,
        )
        token = self._csrf_token()
        self.client.post(
            "/api/v1/auth/phone-verification/request/",
            {"phone": user.phone},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        challenge = AccountOtpChallenge.objects.get(user=user)
        correct_code = account_otp_code_for(challenge)
        wrong_codes = [code for code in ("000000", "000001", "000002") if code != correct_code]

        for code in wrong_codes[:2]:
            response = self.client.post(
                "/api/v1/auth/phone-verification/confirm/",
                {"phone": user.phone, "code": code},
                format="json",
                HTTP_X_CSRFTOKEN=token,
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        challenge.refresh_from_db()
        self.assertEqual(challenge.attempts, 2)
        self.assertIsNotNone(challenge.consumed_at)

    def test_logout_requires_csrf_then_closes_session(self):
        self.assertEqual(self._login().status_code, status.HTTP_200_OK)

        rejected = self.client.post("/api/v1/auth/logout/")
        self.assertEqual(rejected.status_code, status.HTTP_403_FORBIDDEN)

        token = self.client.cookies["csrftoken"].value
        response = self.client.post(
            "/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=token
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        me_response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_session_grants_access_to_existing_protected_endpoints(self):
        self.assertEqual(self._login().status_code, status.HTTP_200_OK)

        response = self.client.get("/api/v1/houses/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
