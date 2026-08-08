"""Middleware de localisation ImmoLib.

Resout la langue selon la priorite definie dans la specification :
    1. preference ``preferred_language`` du profil utilisateur ;
    2. cookie ``immolib_language`` ;
    3. en-tete ``Accept-Language`` du navigateur ;
    4. langue par defaut (francais).

Seules les langues enregistrees et actives sont acceptees. Le contexte de
devise et de format est egalement applique a la requete.
"""

from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

from .languages import default_language_code, is_active
from .utils import resolve_currency, resolve_language, set_locale_context

#: LANG_COOKIE par defaut de Django, conserve pour la compatibilite.
LANGUAGE_COOKIE_NAME = "immolib_language"


class ImmoLocaleMiddleware(MiddlewareMixin):
    """Middleware de negociation de langue, remplace ``LocaleMiddleware``."""

    def process_request(self, request):
        cookie_language = request.COOKIES.get(LANGUAGE_COOKIE_NAME)
        browser_language = self._pick_browser_language(request)
        language = resolve_language(
            user=getattr(request, "user", None),
            cookie_language=cookie_language,
            browser_language=browser_language,
        )
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

        user = getattr(request, "user", None)
        set_locale_context(
            language=language,
            currency=resolve_currency(user=user),
            timezone=getattr(user, "preferred_timezone", None) or None,
            date_format=getattr(user, "preferred_date_format", None) or None,
            number_format=getattr(user, "preferred_number_format", None) or None,
        )

    def process_response(self, request, response):
        language = getattr(request, "LANGUAGE_CODE", None)
        if language and not response.cookies.get(LANGUAGE_COOKIE_NAME):
            response.set_cookie(
                LANGUAGE_COOKIE_NAME,
                language,
                max_age=60 * 60 * 24 * 365,
                httponly=False,
                samesite="Lax",
            )
        return response

    @staticmethod
    def _pick_browser_language(request) -> str | None:
        header = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
        for part in header.split(","):
            tag = part.split(";")[0].strip().lower()
            if not tag:
                continue
            code = tag.split("-")[0]
            if is_active(code):
                return code
        return None
