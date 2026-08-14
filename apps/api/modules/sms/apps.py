from django.apps import AppConfig


class SmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.sms"
    label = "sms"
    verbose_name = "SMS"
