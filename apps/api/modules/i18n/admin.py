from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Country, Currency, Language


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "native_name",
        "english_name",
        "is_active",
        "is_default",
        "is_rtl",
        "order",
    )
    list_editable = ("is_active", "is_default", "is_rtl", "order")
    list_filter = ("is_active", "is_default", "is_rtl")
    search_fields = ("code", "native_name", "english_name")
    ordering = ("order", "code")


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "symbol",
        "decimals",
        "symbol_position",
        "is_active",
        "order",
    )
    list_editable = ("decimals", "symbol_position", "is_active", "order")
    list_filter = ("is_active", "symbol_position")
    search_fields = ("code", "name", "symbol")
    ordering = ("order", "code")


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "currency",
        "default_timezone",
        "is_active",
        "order",
    )
    list_editable = ("currency", "is_active", "order")
    list_filter = ("is_active", "currency")
    search_fields = ("code", "name")
    ordering = ("order", "code")
