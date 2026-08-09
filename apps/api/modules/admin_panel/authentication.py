"""Authentification des routes admin.

SessionAuthentication ne fournit pas de header WWW-Authenticate : DRF
convertit alors les NotAuthenticated en 403. Cette sous-classe annonce
`Session` afin que les requetes anonymes sur les routes admin obtiennent
bien un 401 (le navigateur n'affiche jamais de popup : le header reste
informatif). Le comportement de session Django est inchange.
"""

from rest_framework.authentication import SessionAuthentication


class AdminSessionAuthentication(SessionAuthentication):
    def authenticate_header(self, request) -> str:
        return "Session"
