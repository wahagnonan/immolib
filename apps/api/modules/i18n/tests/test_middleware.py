from django.test import TestCase, override_settings
from django.utils import translation

from modules.accounts.models import User
from modules.i18n.middleware import ImmoLocaleMiddleware
from modules.i18n.utils import resolve_language

from ..languages import default_language_code


class ResolveLanguageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="+2250700000001",
            password="un-Mot-de-Passe-1!",
        )

    def test_user_preference_wins(self):
        self.user.preferred_language = "en"
        self.assertEqual(resolve_language(user=self.user), "en")

    def test_cookie_beats_browser(self):
        self.assertEqual(
            resolve_language(cookie_language="es", browser_language="en"), "es"
        )

    def test_browser_beats_default(self):
        self.assertEqual(resolve_language(browser_language="pt"), "pt")

    def test_default_when_nothing(self):
        self.assertEqual(resolve_language(), default_language_code())

    def test_unknown_cookie_falls_back_to_browser(self):
        self.assertEqual(
            resolve_language(cookie_language="xx", browser_language="en"), "en"
        )

    def test_inactive_language_is_ignored(self):
        self.assertEqual(
            resolve_language(cookie_language="sw", browser_language="fr"), "fr"
        )


class MiddlewareTests(TestCase):
    def test_middleware_activates_request_language(self):
        response = self.client.get(
            "/health/", HTTP_ACCEPT_LANGUAGE="pt-BR,pt;q=0.9"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(translation.get_language(), "pt")

    def test_middleware_sets_language_cookie(self):
        response = self.client.get(
            "/health/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9"
        )
        self.assertIn("immolib_language", response.cookies)
        self.assertEqual(response.cookies["immolib_language"].value, "en")

    def test_user_preference_overrides_accept_language(self):
        user = User.objects.create_user(
            phone="+2250700000002",
            password="un-Mot-de-Passe-1!",
            preferred_language="es",
        )
        self.client.force_login(user)
        self.client.get("/health/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")
        self.assertEqual(translation.get_language(), "es")

    @override_settings(LANGUAGE_CODE="fr")
    def test_invalid_accept_language_falls_back_to_default(self):
        self.client.get("/health/", HTTP_ACCEPT_LANGUAGE="xx-YY,xx;q=0.9")
        self.assertEqual(translation.get_language(), "fr")

    def test_middleware_is_registered_in_settings(self):
        from django.conf import settings

        self.assertIn(
            "modules.i18n.middleware.ImmoLocaleMiddleware", settings.MIDDLEWARE
        )

    def test_cookie_language_beats_accept_language(self):
        self.client.cookies["immolib_language"] = "ar"
        self.client.get("/health/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")
        self.assertEqual(translation.get_language(), "ar")
