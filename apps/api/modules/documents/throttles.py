from hashlib import sha256

from rest_framework.throttling import SimpleRateThrottle


def _fingerprint(value: object) -> str:
    return sha256(str(value or "").strip().encode()).hexdigest()


class PublicDocumentIpThrottle(SimpleRateThrottle):
    scope = "public_document_ip"
    rate = "30/minute"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class PayloadRateThrottle(SimpleRateThrottle):
    field = ""

    def get_cache_key(self, request, view):
        value = request.data.get(self.field)
        if not value:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": _fingerprint(value),
        }


class DocumentOtpRequestThrottle(PayloadRateThrottle):
    field = "access_token"
    scope = "document_otp_request"
    rate = "3/minute"


class DocumentOtpVerifyThrottle(PayloadRateThrottle):
    field = "challenge_id"
    scope = "document_otp_verify"
    rate = "10/minute"


class DocumentGrantThrottle(PayloadRateThrottle):
    field = "grant_token"
    scope = "document_grant"
    rate = "60/minute"
