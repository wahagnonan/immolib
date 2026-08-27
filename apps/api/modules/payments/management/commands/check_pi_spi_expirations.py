from django.core.management.base import BaseCommand

from modules.payments.services_pi_spi import expire_stale_pi_spi_requests


class Command(BaseCommand):
    help = "Expire les demandes PI-SPI en attente au-delà du TTL (idempotent)."

    def handle(self, *args, **options):
        count = expire_stale_pi_spi_requests()
        self.stdout.write(self.style.SUCCESS(f"{count} demande(s) PI-SPI expirée(s)."))
