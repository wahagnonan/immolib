from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from modules.billing.api.views import LeaseObligationViewSet, RentChargeViewSet
from modules.billing.api.dashboard_views import DashboardOverviewView
from modules.documents.api.views import (
    NotificationDeliveryViewSet,
    PublicDocumentAccessViewSet,
    RentalDocumentViewSet,
)
from modules.leases.api.views import (
    LeaseViewSet,
    PublicTenantInvitationViewSet,
    TenantInvitationViewSet,
    TenantViewSet,
)
from modules.maintenance.api.views import MaintenanceIncidentViewSet
from modules.payments.api.views import (
    PaymentMethodAccountViewSet,
    PaymentRequestViewSet,
    PaymentViewSet,
    SecurityDepositViewSet,
)
from modules.notifications.api.ses_webhook import SesBounceComplaintWebhookView
from modules.payments.api.webhook_views import MobileMoneyWebhookView
from modules.properties.api.views import (
    CoOwnerInvitationViewSet,
    CoOwnerViewSet,
    HouseViewSet,
)
from modules.whatsapp.api.views import WhatsAppWebhookView


def health_check(request):
    return JsonResponse({"status": "ok", "service": "immolib-api"})


router = DefaultRouter()
router.register("houses", HouseViewSet, basename="house")
router.register("co-owners", CoOwnerViewSet, basename="co-owner")
router.register(
    "co-owner-invitations",
    CoOwnerInvitationViewSet,
    basename="co-owner-invitation",
)
router.register("tenants", TenantViewSet, basename="tenant")
router.register(
    "tenant-invitations",
    TenantInvitationViewSet,
    basename="tenant-invitation",
)
router.register(
    "public-tenant-invitations",
    PublicTenantInvitationViewSet,
    basename="public-tenant-invitation",
)
router.register("leases", LeaseViewSet, basename="lease")
router.register("rent-charges", RentChargeViewSet, basename="rent-charge")
router.register(
    "lease-obligations",
    LeaseObligationViewSet,
    basename="lease-obligation",
)
router.register("payments", PaymentViewSet, basename="payment")
router.register(
    "payment-requests",
    PaymentRequestViewSet,
    basename="payment-request",
)
router.register(
    "payment-methods",
    PaymentMethodAccountViewSet,
    basename="payment-method",
)
router.register(
    "security-deposits",
    SecurityDepositViewSet,
    basename="security-deposit",
)
router.register(
    "incidents",
    MaintenanceIncidentViewSet,
    basename="maintenance-incident",
)
router.register("documents", RentalDocumentViewSet, basename="document")
router.register(
    "notification-deliveries",
    NotificationDeliveryViewSet,
    basename="notification-delivery",
)
router.register("public-access", PublicDocumentAccessViewSet, basename="public-access")


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path(
        "api/v1/webhooks/mobile-money/",
        MobileMoneyWebhookView.as_view(),
        name="mobile-money-webhook",
    ),
    path("api/v1/", include("modules.sms.api.urls")),
    path(
        "api/v1/webhooks/whatsapp/",
        WhatsAppWebhookView.as_view(),
        name="whatsapp-webhook",
    ),
    path(
        "api/v1/webhooks/email/ses/",
        SesBounceComplaintWebhookView.as_view(),
        name="ses-bounce-complaint-webhook",
    ),
    path(
        "api/v1/dashboard/overview/",
        DashboardOverviewView.as_view(),
        name="dashboard-overview",
    ),
    path("api/v1/auth/", include("modules.accounts.api.urls")),
    path("api/v1/profile/", include("modules.i18n.api.urls")),
    path("api/v1/", include("modules.notifications.api.urls")),
    path("api/v1/tenant-portal/", include("modules.tenant_portal.api.urls")),
    path("api/v1/", include("modules.subscriptions.api.urls")),
    path("api/v1/admin/", include("modules.admin_panel.api.urls")),
    path("api/v1/", include(router.urls)),
    path("admin/", admin.site.urls),
]
