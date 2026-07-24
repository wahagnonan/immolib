from django.apps import AppConfig


class TenantPortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.tenant_portal"
    verbose_name = "Portail locataire"
