from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from modules.properties.services import CreateHouseData, create_house
from modules.subscriptions.models import Subscription, SubscriptionPlan
from modules.subscriptions.services import (
    FeatureDenied,
    HouseLimitReached,
    assert_can_create_house,
    assert_has_feature,
    cancel_subscription,
    check_subscription_expirations,
    ensure_subscription,
    get_effective_plan,
    get_usage,
    has_feature,
    upgrade,
)

User = get_user_model()


def make_user(phone: str):
    return User.objects.create_user(phone=phone, password="password")


def grant_plan(user, slug: str) -> Subscription:
    plan = SubscriptionPlan.objects.get(slug=slug)
    subscription = ensure_subscription(user)
    subscription.plan = plan
    subscription.status = Subscription.Status.ACTIVE
    subscription.started_at = timezone.now()
    subscription.expires_at = timezone.now() + timedelta(days=30)
    subscription.save()
    return subscription


def build_house(owner, name: str):
    return create_house(
        owner=owner,
        data=CreateHouseData(name=name, address="Yopougon", city="Abidjan"),
    )


class HouseLimitTests(TestCase):
    def test_free_zero_house_allowed(self):
        user = make_user("+2250700000101")
        assert_can_create_house(user)
        self.assertEqual(get_usage(user).max_houses, 1)

    def test_free_one_house_allowed(self):
        user = make_user("+2250700000102")
        build_house(user, "Maison 1")
        self.assertEqual(get_usage(user).house_count, 1)
        self.assertEqual(get_usage(user).remaining, 0)
        with self.assertRaises(HouseLimitReached):
            assert_can_create_house(user)

    def test_free_two_houses_rejected(self):
        user = make_user("+2250700000103")
        build_house(user, "Maison 1")
        with self.assertRaises(HouseLimitReached):
            build_house(user, "Maison 2")
        self.assertEqual(get_usage(user).house_count, 1)
        self.assertEqual(get_usage(user).remaining, 0)

    def test_essential_limits(self):
        user = make_user("+2250700000104")
        grant_plan(user, "essential")
        self.assertEqual(get_usage(user).max_houses, 5)
        for index in range(5):
            build_house(user, f"Maison {index}")
        self.assertEqual(get_usage(user).house_count, 5)
        with self.assertRaises(HouseLimitReached):
            assert_can_create_house(user)
        with self.assertRaises(HouseLimitReached):
            build_house(user, "Maison 6")
        self.assertEqual(get_usage(user).house_count, 5)

    def test_pro_limits(self):
        user = make_user("+2250700000105")
        grant_plan(user, "pro")
        self.assertEqual(get_usage(user).max_houses, 15)
        for index in range(15):
            build_house(user, f"Maison {index}")
        self.assertEqual(get_usage(user).house_count, 15)
        with self.assertRaises(HouseLimitReached):
            assert_can_create_house(user)
        with self.assertRaises(HouseLimitReached):
            build_house(user, "Maison 16")

    def test_limit_message_suggests_next_plan(self):
        user = make_user("+2250700000106")
        build_house(user, "Maison 1")
        with self.assertRaises(HouseLimitReached) as context:
            assert_can_create_house(user)
        self.assertIn("Passez à Essentiel", str(context.exception))
        self.assertEqual(context.exception.next_plan_slug, "essential")

    def test_existing_houses_never_deleted_on_limit(self):
        user = make_user("+2250700000107")
        grant_plan(user, "pro")
        for index in range(10):
            build_house(user, f"Maison {index}")
        grant_plan(user, "free")
        with self.assertRaises(HouseLimitReached):
            assert_can_create_house(user)
        self.assertEqual(get_usage(user).house_count, 10)


class FeatureAccessTests(TestCase):
    def test_free_has_base_features(self):
        user = make_user("+2250700000201")
        self.assertTrue(has_feature(user, "tenant_management"))
        self.assertTrue(has_feature(user, "receipt_generation"))
        self.assertFalse(has_feature(user, "co_owners"))
        self.assertFalse(has_feature(user, "payment_reminders"))
        self.assertFalse(has_feature(user, "advanced_statistics"))

    def test_essential_unlocks_coowners_and_reminders(self):
        user = make_user("+2250700000202")
        grant_plan(user, "essential")
        self.assertTrue(has_feature(user, "co_owners"))
        self.assertTrue(has_feature(user, "payment_reminders"))
        self.assertFalse(has_feature(user, "advanced_statistics"))

    def test_pro_unlocks_advanced_features(self):
        user = make_user("+2250700000203")
        grant_plan(user, "pro")
        for feature in (
            "advanced_statistics",
            "data_export",
            "multi_user",
            "financial_reports",
            "unpaid_tracking",
        ):
            self.assertTrue(has_feature(user, feature))

    def test_assert_has_feature_denies_with_required_plan(self):
        user = make_user("+2250700000204")
        with self.assertRaises(FeatureDenied) as context:
            assert_has_feature(user, "co_owners")
        self.assertEqual(context.exception.required_plan_slug, "essential")
        self.assertIn("Essentiel", str(context.exception))

    def test_assert_has_feature_allows_after_upgrade(self):
        user = make_user("+2250700000205")
        grant_plan(user, "essential")
        assert_has_feature(user, "co_owners")


class SubscriptionLifecycleTests(TestCase):
    def test_new_user_has_no_subscription_until_landlord(self):
        user = make_user("+2250700000301")
        self.assertIsNone(getattr(user, "subscription", None) and user.subscription)

    def test_first_house_creates_free_subscription(self):
        user = make_user("+2250700000302")
        build_house(user, "Première maison")
        subscription = user.subscription
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.plan.slug, "free")
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)

    def test_upgrade_pilot_mode_activates_immediately(self):
        user = make_user("+2250700000303")
        grant_plan(user, "free")
        result = upgrade(user, "essential")
        self.assertTrue(result.activated)
        self.assertIsNone(result.redirect_url)
        self.assertEqual(result.transaction.provider, "MANUAL")
        self.assertEqual(result.transaction.status, "SUCCESSFUL")
        self.assertEqual(get_effective_plan(user).slug, "essential")
        self.assertIsNotNone(user.subscription.expires_at)

    def test_upgrade_same_plan_rejected(self):
        user = make_user("+2250700000304")
        grant_plan(user, "free")
        with self.assertRaises(Exception):
            upgrade(user, "free")

    def test_upgrade_unknown_plan_rejected(self):
        user = make_user("+2250700000305")
        with self.assertRaises(Exception):
            upgrade(user, "platinum")

    def test_cancel_returns_to_free_fallback(self):
        user = make_user("+2250700000306")
        upgrade(user, "pro")
        cancel_subscription(user)
        subscription = Subscription.objects.get(user=user)
        self.assertEqual(subscription.status, Subscription.Status.CANCELLED)
        self.assertEqual(get_effective_plan(user).slug, "free")

    def test_expired_subscription_falls_back_to_free_and_keeps_data(self):
        user = make_user("+2250700000307")
        upgrade(user, "pro")
        for index in range(3):
            build_house(user, f"Maison {index}")
        Subscription.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(days=1)
        )

        expired = check_subscription_expirations()
        self.assertEqual(expired, 1)
        self.assertEqual(
            Subscription.objects.get(user=user).status,
            Subscription.Status.EXPIRED,
        )
        self.assertEqual(get_effective_plan(user).slug, "free")
        self.assertEqual(get_usage(user).house_count, 3)
        with self.assertRaises(HouseLimitReached):
            build_house(user, "Maison 4")
        self.assertEqual(get_usage(user).house_count, 3)

    def test_expiry_never_deletes_payments_or_houses(self):
        user = make_user("+2250700000308")
        upgrade(user, "pro")
        build_house(user, "Maison 1")
        Subscription.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(days=1)
        )
        check_subscription_expirations()
        self.assertEqual(get_usage(user).house_count, 1)
        self.assertIsNotNone(get_effective_plan(user))
