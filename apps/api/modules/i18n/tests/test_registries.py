from datetime import date

from django.test import SimpleTestCase

from modules.i18n.currencies import CURRENCY_CHOICES, get_currency, is_supported
from modules.i18n.format import (
    format_date,
    format_long_date,
    format_money,
    format_month_name,
    format_number,
)
from modules.i18n.languages import (
    ACTIVE_CODES,
    LANGUAGES,
    LANGUAGE_CODES,
    is_active,
    is_rtl,
    is_supported as language_is_supported,
)
from modules.i18n.timezones import is_supported as tz_is_supported


class LanguagesRegistryTests(SimpleTestCase):
    def test_languages_registry_contains_expected_codes(self):
        expected = {"fr", "en", "es", "pt", "ar"}
        self.assertTrue(expected.issubset(set(LANGUAGE_CODES)))

    def test_future_languages_are_registered_but_inactive(self):
        for code in ("sw", "bm", "wo", "ln", "yo", "ha", "am"):
            self.assertTrue(language_is_supported(code))
            self.assertFalse(is_active(code))

    def test_active_languages_include_the_five_initial_languages(self):
        self.assertEqual(set(ACTIVE_CODES), {"fr", "en", "es", "pt", "ar"})

    def test_arabic_is_rtl(self):
        self.assertTrue(is_rtl("ar"))
        self.assertFalse(is_rtl("fr"))

    def test_unknown_language_is_rejected(self):
        self.assertFalse(language_is_supported("xx"))
        self.assertFalse(language_is_supported("zz"))


class CurrenciesRegistryTests(SimpleTestCase):
    def test_expected_currencies_registered(self):
        for code in ("XOF", "XAF", "USD", "EUR", "GBP", "MAD", "NGN", "KES", "GHS", "ZAR"):
            self.assertTrue(is_supported(code), code)

    def test_xof_properties(self):
        info = get_currency("XOF")
        self.assertEqual(info["symbol"], "FCFA")
        self.assertEqual(info["decimals"], 0)
        self.assertEqual(info["position"], "suffix")

    def test_usd_properties(self):
        info = get_currency("USD")
        self.assertEqual(info["symbol"], "$")
        self.assertEqual(info["decimals"], 2)
        self.assertEqual(info["position"], "prefix")

    def test_choices_are_unique_codes(self):
        codes = [code for code, _name in CURRENCY_CHOICES]
        self.assertEqual(len(codes), len(set(codes)))


class TimezoneRegistryTests(SimpleTestCase):
    def test_common_timezones_are_supported(self):
        self.assertTrue(tz_is_supported("Africa/Abidjan"))
        self.assertTrue(tz_is_supported("Africa/Lagos"))
        self.assertTrue(tz_is_supported("Europe/Paris"))

    def test_unknown_timezone_rejected(self):
        self.assertFalse(tz_is_supported("Not/AZone"))


class FormatTests(SimpleTestCase):
    def setUp(self):
        self.value = date(2026, 8, 5)

    def test_date_dmy(self):
        self.assertEqual(format_date(self.value, "dmy", locale="fr"), "05/08/2026")

    def test_date_mdy(self):
        self.assertEqual(format_date(self.value, "mdy", locale="en"), "08/05/2026")

    def test_date_ymd(self):
        self.assertEqual(format_date(self.value, "ymd", locale="fr"), "2026-08-05")

    def test_date_from_iso_string(self):
        self.assertEqual(
            format_date("2026-08-05T10:00:00Z", "dmy", locale="fr"), "05/08/2026"
        )

    def test_long_date_localized(self):
        self.assertEqual(format_long_date(self.value, locale="fr"), "5 août 2026")
        self.assertEqual(format_long_date(self.value, locale="en"), "August 5, 2026")

    def test_month_name_localized(self):
        self.assertEqual(format_month_name("2026-08", locale="fr"), "août 2026")
        self.assertEqual(format_month_name("2026-08", locale="en"), "August 2026")

    def test_number_french_separators(self):
        self.assertEqual(format_number(1000000.5, locale="fr-FR"), "1 000 000,5")

    def test_number_english_separators(self):
        self.assertEqual(format_number(1000000.5, locale="en-US"), "1,000,000.5")

    def test_money_xof_suffix_no_decimals(self):
        self.assertEqual(
            format_money(1000000, "XOF", locale="fr-FR"), "1 000 000 FCFA"
        )

    def test_money_usd_prefix_two_decimals(self):
        self.assertEqual(
            format_money(1234.5, "USD", locale="en-US"), "$ 1,234.5"
        )

    def test_money_eur_french(self):
        self.assertEqual(
            format_money(1234.5, "EUR", locale="fr-FR"), "1 234,5 €"
        )
