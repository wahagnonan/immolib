from decimal import Decimal

from django.db import migrations
from django.db.models import Sum


def backfill_primary_percentages(apps, schema_editor):
    Property = apps.get_model("properties", "Property")
    for house in Property.objects.all().iterator():
        ownerships = house.ownerships.all()
        primary = ownerships.filter(role="PRIMARY").first()
        if primary is None:
            continue
        coowners = ownerships.filter(role="CO_OWNER")
        if coowners.filter(ownership_percentage__isnull=True).exists():
            percentage = None
        else:
            total = coowners.aggregate(total=Sum("ownership_percentage"))["total"]
            remaining = Decimal("100") - (total or Decimal("0"))
            percentage = remaining if remaining > 0 else None
        primary.ownership_percentage = percentage
        primary.save(update_fields=["ownership_percentage"])


class Migration(migrations.Migration):
    dependencies = [
        ("properties", "0003_coownerinvitation"),
    ]

    operations = [
        migrations.RunPython(backfill_primary_percentages, migrations.RunPython.noop),
    ]
