from rest_framework import status

from django.test import TestCase

from modules.accounts.models import User


class AccountPreferencesApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="+2250700000003",
            password="un-Mot-de-Passe-1!",
        )
        self.client.force_login(self.user)

    def test_get_preferences_returns_defaults_and_catalogs(self):
        response = self.client.get("/api/v1/profile/preferences/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["preferences"]["preferred_language"], "")
        languages = {item["code"] for item in payload["available"]["languages"]}
        self.assertTrue({"fr", "en", "es", "pt", "ar"}.issubset(languages))
        currencies = {item["code"] for item in payload["available"]["currencies"]}
        self.assertIn("XOF", currencies)
        self.assertIn("Africa/Abidjan", payload["available"]["timezones"])

    def test_patch_updates_preferences(self):
        response = self.client.patch(
            "/api/v1/profile/preferences/",
            {
                "preferred_language": "en",
                "preferred_currency": "USD",
                "preferred_timezone": "America/New_York",
                "preferred_date_format": "mdy",
                "preferred_number_format": "en",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, "en")
        self.assertEqual(self.user.preferred_currency, "USD")
        self.assertEqual(self.user.preferred_timezone, "America/New_York")
        self.assertEqual(self.user.preferred_date_format, "mdy")
        self.assertEqual(self.user.preferred_number_format, "en")

    def test_patch_rejects_unknown_language(self):
        response = self.client.patch(
            "/api/v1/profile/preferences/",
            {"preferred_language": "xx"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_rejects_inactive_language(self):
        response = self.client.patch(
            "/api/v1/profile/preferences/",
            {"preferred_language": "sw"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_rejects_unknown_currency(self):
        response = self.client.patch(
            "/api/v1/profile/preferences/",
            {"preferred_currency": "XXX"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_rejects_unknown_timezone(self):
        response = self.client.patch(
            "/api/v1/profile/preferences/",
            {"preferred_timezone": "Not/AZone"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_rejects_bad_date_format(self):
        response = self.client.patch(
            "/api/v1/profile/preferences/",
            {"preferred_date_format": "dd-MM-yyyy"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requires_authentication(self):
        self.client.logout()
        response = self.client.get("/api/v1/profile/preferences/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_preferences_exposed_in_me_endpoint(self):
        self.user.preferred_language = "en"
        self.user.save()
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["user"]["preferred_language"], "en")


class UserPreferenceLocaleTests(TestCase):
    def test_user_preferred_language_activates_locale_on_request(self):
        from django.utils import translation

        user = User.objects.create_user(
            phone="+2250700000004",
            password="un-Mot-de-Passe-1!",
            preferred_language="en",
        )
        self.client.force_login(user)
        self.client.get("/health/", HTTP_ACCEPT_LANGUAGE="fr-FR,fr;q=0.9")
        self.assertEqual(translation.get_language(), "en")
