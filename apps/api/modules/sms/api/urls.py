from django.urls import path

from .views import OrangeSmsDeliveryReceiptView

urlpatterns = [
    path(
        "webhooks/sms/orange/delivery-receipts/",
        OrangeSmsDeliveryReceiptView.as_view(),
        name="sms-orange-dr-webhook",
    ),
]
