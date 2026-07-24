from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase


class UserModelTests(TestCase):
    def test_user_is_created_with_phone_as_login(self):
        user = get_user_model().objects.create_user(
            phone="+2250700000000",
            password="a-secure-password",
            first_name="Jean",
        )

        self.assertEqual(user.phone, "+2250700000000")
        self.assertEqual(user.first_name, "Jean")
        self.assertTrue(user.check_password("a-secure-password"))

    def test_phone_is_required(self):
        with self.assertRaisesMessage(ValueError, "obligatoire"):
            get_user_model().objects.create_user(phone="", password="password")

    def test_phone_is_stored_in_canonical_e164_format(self):
        user = get_user_model().objects.create_user(
            phone="00 225 05 00 00 00 01",
            password="password",
        )

        self.assertEqual(user.phone, "+2250500000001")

    def test_invalid_national_phone_is_rejected(self):
        with self.assertRaises(ValidationError):
            get_user_model().objects.create_user(
                phone="0700000000",
                password="password",
            )
