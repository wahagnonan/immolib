from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class LeasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.leases"
    label = "leases"
    verbose_name = _("Locataires et baux")
