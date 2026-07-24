from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from modules.billing.services import (
    default_generation_period,
    generate_monthly_charges_for_all,
    refresh_temporal_statuses,
)
from modules.documents.reminders import queue_rent_reminders


class Command(BaseCommand):
    help = "Genere les echeances et actualise leurs statuts temporels."

    def add_arguments(self, parser):
        parser.add_argument(
            "--period",
            help="Mois cible au format AAAA-MM. Le mois est choisi automatiquement si omis.",
        )
        parser.add_argument(
            "--today",
            help="Date de reference AAAA-MM-JJ, utile pour les tests et reprises.",
        )

    def handle(self, *args, **options):
        today = self._parse_date(options.get("today")) if options.get("today") else timezone.localdate()
        period = (
            self._parse_period(options["period"])
            if options.get("period")
            else default_generation_period(today)
        )
        summary = generate_monthly_charges_for_all(
            period_start=period,
            today=today,
        )
        updated = refresh_temporal_statuses(today=today)
        reminders = queue_rent_reminders(today=today)
        self.stdout.write(
            self.style.SUCCESS(
                f"Periode {period:%Y-%m}: {summary.created} creee(s), "
                f"{summary.existing} existante(s), {updated} statut(s) actualise(s), "
                f"{reminders.created} rappel(s) cree(s), "
                f"{reminders.existing} rappel(s) deja present(s)."
            )
        )

    def _parse_period(self, value: str) -> date:
        try:
            return date.fromisoformat(f"{value}-01")
        except ValueError as exc:
            raise CommandError("La periode doit utiliser le format AAAA-MM.") from exc

    def _parse_date(self, value: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CommandError("La date doit utiliser le format AAAA-MM-JJ.") from exc
