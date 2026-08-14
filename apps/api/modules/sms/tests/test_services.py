from django.test import TestCase

from modules.documents.models import NotificationDelivery
from modules.sms.models import SmsDeliveryReceipt
from modules.sms.services import (
    InvalidDrPayload,
    handle_orange_dr_payload,
    validate_dr_payload,
)

from .helpers import build_delivery, dr_payload


class ValidateDrPayloadTests(TestCase):
    def test_valid_payload_extracts_fields(self):
        resource_id, status, address = validate_dr_payload(dr_payload())

        self.assertEqual(resource_id, "resource-ABC")
        self.assertEqual(status, "DeliveredToTerminal")
        self.assertEqual(address, "tel:+2250700000001")

    def test_missing_notification_is_invalid(self):
        with self.assertRaises(InvalidDrPayload):
            validate_dr_payload({})

    def test_missing_callback_data_is_invalid(self):
        with self.assertRaises(InvalidDrPayload):
            validate_dr_payload(dr_payload(resource_id=""))

    def test_missing_delivery_status_is_invalid(self):
        with self.assertRaises(InvalidDrPayload):
            validate_dr_payload(dr_payload(status=""))


class HandleOrangeDrPayloadTests(TestCase):
    def setUp(self):
        self.delivery = build_delivery()
        self.delivery.provider_reference = "resource-ABC"
        self.delivery.save()

    def test_delivery_receipt_correlates_delivery(self):
        summary = handle_orange_dr_payload(dr_payload())

        self.assertTrue(summary["created"])
        self.assertTrue(summary["correlated"])
        self.assertEqual(summary["normalized_status"], "DELIVERED")
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, "DELIVERED")
        self.assertIsNotNone(self.delivery.delivered_at)

    def test_duplicate_delivery_receipt_is_idempotent(self):
        first = handle_orange_dr_payload(dr_payload())
        self.delivery.refresh_from_db()
        delivered_at = self.delivery.delivered_at
        second = handle_orange_dr_payload(dr_payload())

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(SmsDeliveryReceipt.objects.count(), 1)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivered_at, delivered_at)

    def test_failure_marks_pending_delivery_as_failed(self):
        summary = handle_orange_dr_payload(dr_payload(status="DeliveryImpossible"))

        self.assertTrue(summary["correlated"])
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, "FAILED")

    def test_failure_does_not_downgrade_delivered_delivery(self):
        handle_orange_dr_payload(dr_payload())
        summary = handle_orange_dr_payload(dr_payload(status="DeliveryImpossible"))

        self.assertFalse(summary["correlated"])
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, "DELIVERED")

    def test_unknown_resource_id_is_not_correlated(self):
        summary = handle_orange_dr_payload(dr_payload(resource_id="unknown-resource"))

        self.assertFalse(summary["correlated"])
        self.assertEqual(SmsDeliveryReceipt.objects.count(), 1)

    def test_intermediate_status_is_recorded_but_not_delivered(self):
        handle_orange_dr_payload(dr_payload(status="MessageWaiting"))

        receipt = SmsDeliveryReceipt.objects.get(provider_message_id="resource-ABC")
        self.assertEqual(receipt.delivery_status, "MessageWaiting")
        self.assertEqual(receipt.address, "tel:+2250700000001")
        self.assertIn("deliveryInfoNotification", receipt.raw_payload)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, "PENDING_DR")
        self.assertIsNone(self.delivery.delivered_at)

    def test_unknown_status_is_mapped_to_unknown(self):
        summary = handle_orange_dr_payload(dr_payload(status="WeirdStatus"))

        self.assertEqual(summary["normalized_status"], "UNKNOWN")
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, "UNKNOWN")
