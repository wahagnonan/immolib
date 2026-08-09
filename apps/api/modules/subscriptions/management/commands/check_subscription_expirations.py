from django.core.management.base import BaseCommand

from modules.subscriptions.services import check_subscription_expirations


class Command(BaseCommand):
    help = "Expire les abonnements arrivés à terme (aucune donnée supprimée)."

    def handle(self, *args, **options):
        count = check_subscription_expirations()
        self.stdout.write(
            self.style.SUCCESS(f"{count} abonnement(s) arrivé(s) à expiration.")
        )
