from django.contrib import admin

from .models import RentCharge


@admin.register(RentCharge)
class RentChargeAdmin(admin.ModelAdmin):
    list_display = (
        "charge_type",
        "lease",
        "period_start",
        "due_date",
        "amount_due",
        "amount_paid",
        "amount_released",
        "currency",
        "status",
    )
    list_filter = ("charge_type", "status", "currency", "period_start")
    search_fields = (
        "lease__property__name",
        "lease__tenant__full_name",
        "lease__tenant__phone",
    )
