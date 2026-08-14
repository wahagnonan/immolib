from datetime import date

from rest_framework import serializers

from ..models import RentCharge


class RentChargeSerializer(serializers.ModelSerializer):
    lease_id = serializers.UUIDField(read_only=True)
    house_id = serializers.UUIDField(source="lease.property_id", read_only=True)
    house_name = serializers.CharField(source="lease.property.name", read_only=True)
    tenant_id = serializers.UUIDField(source="lease.tenant_id", read_only=True)
    tenant_name = serializers.CharField(source="lease.tenant.full_name", read_only=True)
    period = serializers.CharField(source="period_label", read_only=True)
    obligation_type = serializers.CharField(source="charge_type", read_only=True)
    obligation_type_label = serializers.CharField(
        source="get_charge_type_display", read_only=True
    )
    obligation_label = serializers.CharField(read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = RentCharge
        fields = (
            "id",
            "lease_id",
            "house_id",
            "house_name",
            "tenant_id",
            "tenant_name",
            "obligation_type",
            "obligation_type_label",
            "obligation_label",
            "period",
            "period_start",
            "period_end",
            "due_date",
            "rent_amount",
            "charges_amount",
            "amount_due",
            "amount_paid",
            "amount_released",
            "balance_due",
            "held_balance",
            "deposit_state",
            "currency",
            "status",
            "status_label",
            "generated_at",
            "updated_at",
        )


class GenerateRentChargesSerializer(serializers.Serializer):
    period = serializers.RegexField(
        regex=r"^\d{4}-(0[1-9]|1[0-2])$",
        help_text="Mois au format AAAA-MM, par exemple 2026-08.",
    )

    def validate_period(self, value: str) -> date:
        year, month = value.split("-")
        return date(int(year), int(month), 1)


class PreparePaymentObligationsSerializer(serializers.Serializer):
    lease_id = serializers.UUIDField()
    period_start = serializers.RegexField(
        regex=r"^\d{4}-(0[1-9]|1[0-2])$",
        required=False,
        allow_blank=True,
        help_text=_("Premier mois de loyer au format AAAA-MM."),
    )
    period_end = serializers.RegexField(
        regex=r"^\d{4}-(0[1-9]|1[0-2])$",
        required=False,
        allow_blank=True,
        help_text=_("Dernier mois de loyer au format AAAA-MM."),
    )
    include_security_deposit = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        period_start = attrs.get("period_start", "")
        period_end = attrs.get("period_end", "")
        if bool(period_start) != bool(period_end):
            raise serializers.ValidationError(
                _("Indique le premier et le dernier mois de loyer.")
            )
        if not period_start and not attrs["include_security_deposit"]:
            raise serializers.ValidationError(
                _("Sélectionne la caution ou une période de loyer.")
            )
        if period_start:
            start_year, start_month = period_start.split("-")
            end_year, end_month = period_end.split("-")
            attrs["period_start"] = date(int(start_year), int(start_month), 1)
            attrs["period_end"] = date(int(end_year), int(end_month), 1)
        else:
            attrs["period_start"] = None
            attrs["period_end"] = None
        return attrs
