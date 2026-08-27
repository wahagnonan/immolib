"""Registre des PaymentProviders — évite if/else dispersés."""

from __future__ import annotations

from django.conf import settings

from .base import PaymentProvider

_REGISTRY: dict[str, type[PaymentProvider]] = {}


def register_provider(code: str, cls: type[PaymentProvider]) -> None:
    _REGISTRY[code.upper()] = cls


def get_provider(code: str) -> PaymentProvider:
    key = code.strip().upper()
    if key not in _REGISTRY:
        raise ValueError(f"Provider inconnu: {code} (registre={list(_REGISTRY)})")
    return _REGISTRY[key]()


def available_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


# Auto-register builtins
def _bootstrap() -> None:
    from .mock_pi_spi import MockPiSpiProvider  # noqa: PLC0415
    from .pi_spi import PiSpiProvider  # noqa: PLC0415

    register_provider("PI_SPI", PiSpiProvider)
    # Alias pour compatibilité operator
    register_provider("PI-SPI", PiSpiProvider)
    register_provider("MOCK_PI_SPI", MockPiSpiProvider)

    # Legacy mobile money reste hors registry (webhook historique)
    # mais on l'expose si besoin
    try:
        from .legacy_mobile_money import LegacyMobileMoneyProvider  # noqa: PLC0415

        register_provider("MOBILE_MONEY", LegacyMobileMoneyProvider)
    except ImportError:
        pass


_bootstrap()


def pi_spi_enabled() -> bool:
    return getattr(settings, "PI_SPI_ENABLED", False) or getattr(settings, "DEBUG", False)
