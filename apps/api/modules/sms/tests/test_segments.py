from django.test import SimpleTestCase

from modules.sms.segments import count_segments


class CountSegmentsTests(SimpleTestCase):
    def test_short_ascii_message_is_one_segment(self):
        self.assertEqual(count_segments("Quittance de loyer"), 1)

    def test_ascii_at_160_chars_is_one_segment(self):
        self.assertEqual(count_segments("a" * 160), 1)

    def test_ascii_161_chars_is_two_segments(self):
        self.assertEqual(count_segments("a" * 161), 2)

    def test_ascii_306_chars_is_two_segments(self):
        self.assertEqual(count_segments("a" * 306), 2)

    def test_ascii_307_chars_is_three_segments(self):
        self.assertEqual(count_segments("a" * 307), 3)

    def test_unicode_message_uses_70_char_segments(self):
        self.assertEqual(count_segments("€" * 70), 1)
        self.assertEqual(count_segments("€" * 71), 2)

    def test_unicode_then_ascii_uses_utf16_limits(self):
        self.assertEqual(count_segments(("€" * 1) + ("a" * 66)), 1)
        self.assertEqual(count_segments(("€" * 1) + ("a" * 67)), 2)

    def test_unicode_134_chars_is_two_segments(self):
        self.assertEqual(count_segments("€" * 134), 2)

    def test_unicode_135_chars_is_three_segments(self):
        self.assertEqual(count_segments("€" * 135), 3)

    def test_empty_message_is_one_segment(self):
        self.assertEqual(count_segments(""), 1)
