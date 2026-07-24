from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from modules.documents.models import NotificationDelivery
from modules.documents.notifications import (
    SimulatedNotificationAdapter,
    load_configured_adapters,
    process_notification_batch,
)


class Command(BaseCommand):
    help = "Traite les notifications push, email, WhatsApp et SMS placées en file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Nombre maximal de messages a reclamer (50 par defaut).",
        )
        parser.add_argument(
            "--simulate",
            action="store_true",
            help="Simule les envois sans contacter de fournisseur.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit < 1:
            raise CommandError("--limit doit etre superieur a zero.")

        if options["simulate"]:
            adapter = SimulatedNotificationAdapter()
            adapters = {
                channel: adapter for channel, _label in NotificationDelivery.Channel.choices
            }
            self.stdout.write(
                self.style.WARNING(
                    "Mode simulation: aucune notification push, email, WhatsApp ou SMS réelle ne sera envoyée."
                )
            )
        else:
            try:
                adapters = load_configured_adapters()
            except (ImportError, ImproperlyConfigured) as exc:
                raise CommandError(str(exc)) from exc
            if not adapters:
                raise CommandError(
                    "Aucun adaptateur configure. Utilise --simulate ou renseigne "
                    "IMMOLIB_*_NOTIFICATION_ADAPTER."
                )

        summary = process_notification_batch(adapters=adapters, limit=limit)
        self.stdout.write(
            self.style.SUCCESS(
                f"Reclamees: {summary.claimed}; envoyees: {summary.sent}; "
                f"reprogrammees: {summary.requeued}; echecs definitifs: "
                f"{summary.failed}; sans adaptateur: {summary.unavailable}; "
                f"traitements repris: {summary.recovered}."
            )
        )
