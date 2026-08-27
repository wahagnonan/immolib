from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from ..models import (
    Payment,
    PaymentAllocation,
    PaymentEvent,
    PaymentMethodAccount,
    PaymentRequest,
    SecurityDepositMovement,
)


class PaymentAllocationSerializer(serializers.ModelSerializer):
    rent_charge_id = serializers.UUIDField(read_only=True)
    obligation_id = serializers.UUIDField(source="rent_charge_id", read_only=True)
    obligation_type = serializers.CharField(
        source="rent_charge.charge_type", read_only=True
    )
    obligation_label = serializers.CharField(
        source="rent_charge.obligation_label", read_only=True
    )
    period = serializers.CharField(source="rent_charge.period_label", read_only=True)
    house_name = serializers.CharField(
        source="rent_charge.lease.property.name",
        read_only=True,
    )
    tenant_name = serializers.CharField(
        source="rent_charge.lease.tenant.full_name",
        read_only=True,
    )

    class Meta:
        model = PaymentAllocation
        fields = (
            "id",
            "rent_charge_id",
            "obligation_id",
            "obligation_type",
            "obligation_label",
            "period",
            "house_name",
            "tenant_name",
            "amount",
            "created_at",
        )


class PaymentEventSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(source="get_event_type_display", read_only=True)

    class Meta:
        model = PaymentEvent
        fields = ("id", "event_type", "event_label", "reason", "created_at")


class PaymentSerializer(serializers.ModelSerializer):
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    events = PaymentEventSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "amount",
            "currency",
            "method",
            "method_label",
            "status",
            "status_label",
            "received_at",
            "external_reference",
            "note",
            "is_cash_movement",
            "idempotency_key",
            "allocations",
            "events",
            "created_at",
            "updated_at",
        )


class PaymentAllocationInputSerializer(serializers.Serializer):
    obligation_id = serializers.UUIDField()
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )


class RecordOfflinePaymentSerializer(serializers.Serializer):
    rent_charge_id = serializers.UUIDField(required=False)
    allocations = PaymentAllocationInputSerializer(many=True, required=False)
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    method = serializers.ChoiceField(
        choices=(
            Payment.Method.CASH,
            Payment.Method.BANK_TRANSFER,
            Payment.Method.EXTERNAL_MOBILE_MONEY,
            Payment.Method.OTHER,
        )
    )
    received_at = serializers.DateTimeField(required=False)
    external_reference = serializers.CharField(
        max_length=120, allow_blank=True, required=False
    )
    note = serializers.CharField(allow_blank=True, required=False)
    idempotency_key = serializers.UUIDField()

    def validate(self, attrs):
        legacy_charge_id = attrs.get("rent_charge_id")
        allocations = attrs.get("allocations")
        if legacy_charge_id and allocations:
            raise serializers.ValidationError(
                "Utilise rent_charge_id ou allocations, mais pas les deux."
            )
        if not legacy_charge_id and not allocations:
            raise serializers.ValidationError(
                _("Affecte le paiement à au moins une obligation.")
            )
        if allocations:
            obligation_ids = [item["obligation_id"] for item in allocations]
            if len(obligation_ids) != len(set(obligation_ids)):
                raise serializers.ValidationError(
                    {"allocations": _("Une obligation ne peut apparaître qu'une fois.")}
                )
            allocated_total = sum(
                (item["amount"] for item in allocations), start=Decimal("0")
            )
            if allocated_total != attrs["amount"]:
                raise serializers.ValidationError(
                    {
                        "allocations": (
                            _(
                                "La somme des affectations doit être égale au montant "
                                "du paiement."
                            )
                        )
                    }
                )
        return attrs


class CancelPaymentSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3)


class SecurityDepositMovementSerializer(serializers.ModelSerializer):
    movement_type_label = serializers.CharField(
        source="get_movement_type_display",
        read_only=True,
    )
    target_rent_charge_id = serializers.UUIDField(read_only=True, allow_null=True)
    target_label = serializers.CharField(
        source="target_rent_charge.obligation_label",
        read_only=True,
        allow_null=True,
    )
    resulting_payment_id = serializers.UUIDField(read_only=True, allow_null=True)
    document_id = serializers.SerializerMethodField()
    document_reference = serializers.SerializerMethodField()

    class Meta:
        model = SecurityDepositMovement
        fields = (
            "id",
            "movement_type",
            "movement_type_label",
            "amount",
            "reason",
            "agreement_confirmed",
            "agreement_reference",
            "target_rent_charge_id",
            "target_label",
            "resulting_payment_id",
            "document_id",
            "document_reference",
            "occurred_at",
            "created_at",
        )

    def _document(self, obj):
        return next(
            (
                document
                for document in obj.rental_documents.all()
                if document.status == "ACTIVE"
            ),
            None,
        )

    def get_document_id(self, obj) -> str | None:
        document = self._document(obj)
        return str(document.id) if document else None

    def get_document_reference(self, obj) -> str:
        document = self._document(obj)
        return document.reference if document else ""


class SecurityDepositSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    lease_id = serializers.UUIDField(read_only=True)
    house_id = serializers.UUIDField(source="lease.property_id", read_only=True)
    house_name = serializers.CharField(source="lease.property.name", read_only=True)
    tenant_name = serializers.CharField(source="lease.tenant.full_name", read_only=True)
    amount_due = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    amount_paid = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    amount_released = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    held_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    deposit_state = serializers.CharField(read_only=True)
    deposit_state_label = serializers.SerializerMethodField()
    currency = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    movements = SecurityDepositMovementSerializer(
        source="security_deposit_movements",
        many=True,
        read_only=True,
    )

    def get_deposit_state_label(self, obj) -> str:
        return {
            "EXPECTED": _("À encaisser"),
            "PARTIALLY_HELD": _("Partiellement détenue"),
            "HELD": _("Détenue"),
            "PARTIALLY_SETTLED": _("Partiellement clôturée"),
            "SETTLED": _("Clôturée"),
        }.get(obj.deposit_state, obj.deposit_state)


class SettleSecurityDepositSerializer(serializers.Serializer):
    movement_type = serializers.ChoiceField(
        choices=SecurityDepositMovement.Type.choices
    )
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    reason = serializers.CharField(allow_blank=True, required=False)
    agreement_confirmed = serializers.BooleanField(required=False, default=False)
    agreement_reference = serializers.CharField(
        max_length=160,
        allow_blank=True,
        required=False,
    )
    target_rent_charge_id = serializers.UUIDField(required=False, allow_null=True)
    idempotency_key = serializers.UUIDField()
    occurred_at = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        movement_type = attrs["movement_type"]
        if (
            movement_type == SecurityDepositMovement.Type.RETENTION
            and not attrs.get("reason", "").strip()
        ):
            raise serializers.ValidationError(
                {"reason": _("Le motif de la retenue est obligatoire.")}
            )
        if movement_type == SecurityDepositMovement.Type.APPLY_TO_RENT:
            errors = {}
            if not attrs.get("target_rent_charge_id"):
                errors["target_rent_charge_id"] = _("Sélectionnez un loyer.")
            if not attrs.get("agreement_confirmed"):
                errors["agreement_confirmed"] = (
                    _("Confirmez que le locataire a donné son accord.")
                )
            if not attrs.get("agreement_reference", "").strip():
                errors["agreement_reference"] = _("Indiquez la référence de l'accord.")
            if errors:
                raise serializers.ValidationError(errors)
        return attrs


class PaymentMethodAccountSerializer(serializers.ModelSerializer):
    operator_label = serializers.CharField(
        source="get_operator_display", read_only=True
    )

    class Meta:
        model = PaymentMethodAccount
        fields = (
            "id",
            "operator",
            "operator_label",
            "account_identifier",
            "account_holder",
            "is_default",
            "created_at",
            "updated_at",
        )


class PaymentMethodAccountCreateSerializer(serializers.Serializer):
    operator = serializers.ChoiceField(choices=PaymentMethodAccount.Operator.choices)
    account_identifier = serializers.CharField(max_length=120)
    account_holder = serializers.CharField(
        max_length=120, allow_blank=True, required=False
    )
    is_default = serializers.BooleanField(required=False, default=False)


class PaymentMethodAccountBriefSerializer(serializers.ModelSerializer):
    operator_label = serializers.CharField(
        source="get_operator_display", read_only=True
    )

    class Meta:
        model = PaymentMethodAccount
        fields = (
            "id",
            "operator",
            "operator_label",
            "account_identifier",
            "account_holder",
        )


class PaymentRequestSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    operator_label = serializers.CharField(
        source="get_operator_display", read_only=True
    )
    rent_charge_id = serializers.UUIDField(source="rent_charge.id", read_only=True)
    lease_id = serializers.UUIDField(source="rent_charge.lease_id", read_only=True)
    house_id = serializers.UUIDField(
        source="rent_charge.lease.property_id", read_only=True
    )
    house_name = serializers.CharField(
        source="rent_charge.lease.property.name", read_only=True
    )
    tenant_id = serializers.UUIDField(
        source="rent_charge.lease.tenant_id", read_only=True
    )
    tenant_name = serializers.CharField(
        source="rent_charge.lease.tenant.full_name", read_only=True
    )
    period = serializers.CharField(source="rent_charge.period_label", read_only=True)
    charge_status = serializers.CharField(
        source="rent_charge.status", read_only=True
    )
    charge_balance_due = serializers.DecimalField(
        source="rent_charge.balance_due",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    method_account = PaymentMethodAccountBriefSerializer(read_only=True)
    payment_id = serializers.UUIDField(source="payment.id", read_only=True)

    class Meta:
        model = PaymentRequest
        fields = (
            "id",
            "reference",
            "amount",
            "amount_received",
            "currency",
            "rent_charge_id",
            "lease_id",
            "house_id",
            "house_name",
            "tenant_id",
            "tenant_name",
            "period",
            "charge_status",
            "charge_balance_due",
            "operator",
            "operator_label",
            "method_account",
            "payee_name",
            "payee_phone",
            "status",
            "status_label",
            "note",
            "processing_note",
            "payment_id",
            "external_transaction_id",
            "provider",
            "provider_status",
            "provider_reference",
            "failure_reason",
            "expires_at",
            "created_at",
            "updated_at",
        )


class PaymentRequestCreateSerializer(serializers.Serializer):
    rent_charge_id = serializers.UUIDField()
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    operator = serializers.ChoiceField(choices=PaymentRequest.Operator.choices)
    method_account_id = serializers.UUIDField(required=False, allow_null=True)
    note = serializers.CharField(allow_blank=True, required=False)


class PaymentRequestConfirmSerializer(serializers.Serializer):
    received_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        allow_null=True,
    )
    note = serializers.CharField(allow_blank=True, required=False)


class PaymentRequestRefuseSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3)


class PaymentRequestCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=True, required=False)
