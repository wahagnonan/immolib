from django.test import SimpleTestCase

from modules.sms.phones import InvalidPhoneNumber, normalize_ci_phone


class NormalizeCiPhoneTests(SimpleTestCase):
    def test_local_format_adds_country_code(self):
        self.assertEqual(normalize_ci_phone("0700000001"), "+2250700000001")

    def test_leading_plus_is_kept(self):
        self.assertEqual(normalize_ci_phone("+2250700000001"), "+2250700000001")

    def test_country_code_without_plus(self):
        self.assertEqual(normalize_ci_phone("2250700000001"), "+2250700000001")

    def test_whitespace_and_dots_are_stripped(self):
        self.assertEqual(
            normalize_ci_phone(" 07 00 00 00 01 "), "+2250700000001"
        )

    def test_invalid_length_is_rejected(self):
        with self.assertRaises(InvalidPhoneNumber):
            normalize_ci_phone("070000")

    def test_invalid_prefix_is_rejected(self):
        with self.assertRaises(InvalidPhoneNumber):
            normalize_ci_phone("1100000001")

    def test_foreign_country_code_is_rejected(self):
        with self.assertRaises(InvalidPhoneNumber):
            normalize_ci_phone("+33612345678")

    def test_non_numeric_is_rejected(self):
        with self.assertRaises(InvalidPhoneNumber):
            normalize_ci_phone("07 00 00 00 0a")
