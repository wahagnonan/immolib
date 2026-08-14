from django.apps import AppConfig


class LeasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.leases"
    label = "leases"
    verbose_name = _("Locataires et baux")
