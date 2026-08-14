from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from modules.payments.models import Payment
from ..models import ManualShareEvent, NotificationDelivery, RentalDocument


class RentalDocumentSerializer(serializers.ModelSerializer):
    document_type_label = serializers.CharField(
        source="get_document_type_display", read_only=True
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    period = serializers.SerializerMethodField()
    rent_charge_id = serializers.UUIDField(read_only=True)
    payment_id = serializers.UUIDField(read_only=True, allow_null=True)
    deposit_movement_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = RentalDocument
        fields = (
            "id",
            "reference",
            "document_type",
            "document_type_label",
            "status",
            "status_label",
            "rent_charge_id",
            "payment_id",
            "deposit_movement_id",
            "amount",
            "currency",
            "period",
            "period_start",
            "period_end",
            "payment_method",
            "breakdown",
            "house_name",
            "house_address",
            "tenant_name",
            "owner_name",
            "issued_at",
            "voided_at",
            "void_reason",
        )

    def get_period(self, obj: RentalDocument) -> str:
        return obj.period_start.strftime("%Y-%m")


class ShareDocumentSerializer(serializers.Serializer):
    channels = serializers.ListField(
        child=serializers.ChoiceField(
            choices=(
                NotificationDelivery.Channel.SMS,
                NotificationDelivery.Channel.EMAIL,
                NotificationDelivery.Channel.WHATSAPP,
            )
        ),
        allow_empty=False,
    )


class ManualShareSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=ManualShareEvent.Channel.choices)


class NotificationDeliverySerializer(serializers.ModelSerializer):
    access_link_id = serializers.UUIDField(read_only=True, allow_null=True)
    rent_charge_id = serializers.UUIDField(read_only=True, allow_null=True)
    tenant_invitation_id = serializers.UUIDField(read_only=True, allow_null=True)
    document_id = serializers.SerializerMethodField()
    document_reference = serializers.SerializerMethodField()
    context_label = serializers.SerializerMethodField()
    house_name = serializers.SerializerMethodField()
    tenant_name = serializers.SerializerMethodField()
    period = serializers.SerializerMethodField()
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    channel_label = serializers.CharField(
        source="get_channel_display", read_only=True
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    masked_destination = serializers.SerializerMethodField()

    class Meta:
        model = NotificationDelivery
        fields = (
            "id",
            "access_link_id",
            "rent_charge_id",
            "tenant_invitation_id",
            "document_id",
            "document_reference",
            "context_label",
            "house_name",
            "tenant_name",
            "period",
            "kind",
            "kind_label",
            "channel",
            "channel_label",
            "masked_destination",
            "status",
            "status_label",
            "delivery_status",
            "delivered_at",
            "segments_count",
            "attempt_count",
            "last_attempt_at",
            "next_attempt_at",
            "scheduled_for",
            "sent_at",
            "provider_reference",
            "failure_reason",
            "created_at",
        )

    def get_document_id(self, obj: NotificationDelivery) -> str | None:
        return str(obj.access_link.document_id) if obj.access_link_id else None

    def get_document_reference(self, obj: NotificationDelivery) -> str | None:
        return obj.access_link.document.reference if obj.access_link_id else None

    def get_context_label(self, obj: NotificationDelivery) -> str:
        if obj.access_link_id:
            return obj.access_link.document.reference
        if obj.rent_charge_id:
            return _("Loyer {period}").format(period=obj.rent_charge.period_label)
        if obj.tenant_invitation_id:
            return _("Invitation locataire")
        return _("Notification")

    def get_house_name(self, obj: NotificationDelivery) -> str:
        if obj.access_link_id:
            return obj.access_link.document.house_name
        if obj.rent_charge_id:
            return obj.rent_charge.lease.property.name
        if obj.tenant_invitation_id:
            return obj.tenant_invitation.tenant.property.name
        return ""

    def get_tenant_name(self, obj: NotificationDelivery) -> str:
        if obj.access_link_id:
            return obj.access_link.document.tenant_name
        if obj.rent_charge_id:
            return obj.rent_charge.lease.tenant.full_name
        if obj.tenant_invitation_id:
            return obj.tenant_invitation.tenant.full_name
        return ""

    def get_period(self, obj: NotificationDelivery) -> str:
        if obj.access_link_id:
            return obj.access_link.document.period_start.strftime("%Y-%m")
        if obj.rent_charge_id:
            return obj.rent_charge.period_label
        return ""

    def get_masked_destination(self, obj: NotificationDelivery) -> str:
        destination = obj.destination
        if "@" in destination:
            name, domain = destination.split("@", 1)
            return f"{name[:2]}***@{domain}"
        return f"***{destination[-4:]}"


class RequestOtpSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    channel = serializers.ChoiceField(
        choices=(
            NotificationDelivery.Channel.SMS,
            NotificationDelivery.Channel.EMAIL,
            NotificationDelivery.Channel.WHATSAPP,
        )
    )


class VerifyOtpSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(regex=r"^\d{6}$")


class GrantSerializer(serializers.Serializer):
    grant_token = serializers.CharField()


class PaymentResponseSerializer(GrantSerializer):
    action = serializers.ChoiceField(choices=["CONFIRM", "DISPUTE"])
    reason = serializers.CharField(allow_blank=True, required=False)

    def validate(self, attrs):
        if attrs["action"] == "DISPUTE" and not attrs.get("reason", "").strip():
            raise serializers.ValidationError(
                {"reason": _("Le motif est obligatoire pour contester.")}
            )
        return attrs


class PublicPaymentStatusSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Payment
        fields = ("id", "status", "status_label", "updated_at")


class PublicDocumentVerificationSerializer(serializers.ModelSerializer):
    authentic = serializers.SerializerMethodField()
    document_type_label = serializers.CharField(
        source="get_document_type_display",
        read_only=True,
    )
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    period = serializers.SerializerMethodField()

    class Meta:
        model = RentalDocument
        fields = (
            "authentic",
            "reference",
            "document_type",
            "document_type_label",
            "status",
            "status_label",
            "amount",
            "currency",
            "period",
            "period_start",
            "period_end",
            "issued_at",
            "voided_at",
        )

    def get_authentic(self, obj: RentalDocument) -> bool:
        return True

    def get_period(self, obj: RentalDocument) -> str:
        return obj.period_start.strftime("%Y-%m")
