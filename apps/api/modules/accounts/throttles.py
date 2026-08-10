from hashlib import sha256

from rest_framework.throttling import SimpleRateThrottle


def _fingerprint(value: object) -> str:
    return sha256(str(value or "").strip().casefold().encode()).hexdigest()


class IpRateThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class PublicAuthIpThrottle(IpRateThrottle):
    scope = "public_auth_ip"
    rate = "300/minute"


class RegisterIpThrottle(IpRateThrottle):
    scope = "register_ip"
    rate = "100/hour"


class PhoneRateThrottle(SimpleRateThrottle):
    field = "phone"

    def get_cache_key(self, request, view):
        value = request.data.get(self.field)
        if not value:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": _fingerprint(value),
        }


class LoginEmailThrottle(SimpleRateThrottle):
    scope = "login_email"
    rate = "10/minute"

    def get_cache_key(self, request, view):
        value = request.data.get("email")
        if not value:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": _fingerprint(value),
        }


class RegisterPhoneThrottle(PhoneRateThrottle):
    scope = "register_phone"
    rate = "5/hour"


class OtpRequestPhoneThrottle(PhoneRateThrottle):
    scope = "otp_request_phone"
    rate = "3/minute"


class OtpConfirmPhoneThrottle(PhoneRateThrottle):
    scope = "otp_confirm_phone"
    rate = "10/minute"
