"""Modeles du module i18n : langues, devises, pays.

Ces modeles sont administrables : une langue ou une devise s'ajoute sans
modification de code (le registre statique de ``languages.py`` et
``currencies.py`` fournit les valeurs initiales et la validation).
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from .currencies import CURRENCIES, SYMBOL_POSITION_CHOICES
from .languages import LANGUAGES


class Language(models.Model):
    """Langue supportee par la plateforme (interface, emails, PDF)."""

    code = models.CharField(
        _("code"), max_length=10, unique=True,
        help_text=_("Code ISO 639-1, ex. fr, en, es, pt, ar."),
    )
    native_name = models.CharField(_("nom natif"), max_length=100)
    english_name = models.CharField(_("nom anglais"), max_length=100, blank=True)
    is_active = models.BooleanField(
        _("active"), default=True,
        help_text=_("Une langue inactive ne peut jamais etre servie."),
    )
    is_default = models.BooleanField(
        _("langue par defaut"), default=False,
        help_text=_("Utilisee lorsque aucune preference n'est exprimable."),
    )
    is_rtl = models.BooleanField(
        _("ecriture droite a gauche"), default=False,
        help_text=_("Coche pour l'arabe et autres ecritures RTL."),
    )
    order = models.PositiveSmallIntegerField(_("ordre"), default=0)

    class Meta:
        ordering = ["order", "code"]
        verbose_name = _("langue")
        verbose_name_plural = _("langues")

    def __str__(self) -> str:
        return self.native_name

    def save(self, *args, **kwargs):
        if self.is_default:
            Language.objects.filter(is_default=True).exclude(pk=self.pk).update(
                is_default=False
            )
        super().save(*args, **kwargs)


class Currency(models.Model):
    """Devise : code ISO 4217, symbole, decimales, position du symbole."""

    code = models.CharField(
        _("code ISO 4217"), max_length=3, unique=True,
        help_text=_("Ex. XOF, USD, EUR, MAD, NGN, KES, GHS, ZAR."),
    )
    name = models.CharField(_("nom"), max_length=100)
    symbol = models.CharField(_("symbole"), max_length=16, blank=True)
    decimals = models.PositiveSmallIntegerField(_("decimales"), default=2)
    symbol_position = models.CharField(
        _("position du symbole"),
        max_length=8,
        choices=SYMBOL_POSITION_CHOICES,
        default="suffix",
    )
    is_active = models.BooleanField(_("active"), default=True)
    order = models.PositiveSmallIntegerField(_("ordre"), default=0)

    class Meta:
        ordering = ["order", "code"]
        verbose_name = _("devise")
        verbose_name_plural = _("devises")

    def __str__(self) -> str:
        return f"{self.code} - {self.symbol or self.name}"


class Country(models.Model):
    """Pays : code ISO 3166-1 alpha-2, devise et fuseau par defaut."""

    code = models.CharField(
        _("code ISO 3166-1"), max_length=2, unique=True,
        help_text=_("Ex. CI, FR, US, MA, NG, KE, GH, ZA."),
    )
    name = models.CharField(_("nom"), max_length=100)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name="countries",
        verbose_name=_("devise"),
    )
    default_timezone = models.CharField(
        _("fuseau par defaut"), max_length=64, blank=True,
        help_text=_("Code IANA, ex. Africa/Abidjan."),
    )
    is_active = models.BooleanField(_("actif"), default=True)
    order = models.PositiveSmallIntegerField(_("ordre"), default=0)

    class Meta:
        ordering = ["order", "code"]
        verbose_name = _("pays")
        verbose_name_plural = _("pays")

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
