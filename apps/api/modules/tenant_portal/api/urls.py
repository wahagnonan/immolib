from django.urls import path

from modules.maintenance.api.views import (
    TenantMaintenanceCommentView,
    TenantMaintenanceIncidentListCreateView,
    TenantMaintenanceResponseView,
)

from .views import (
    TenantPortalChargeListView,
    TenantPortalDocumentListView,
    TenantPortalDocumentPdfView,
    TenantPortalLeaseListView,
    TenantPortalOverviewView,
    TenantPortalPaymentConfirmView,
    TenantPortalPaymentDisputeView,
    TenantPortalPaymentListView,
)


urlpatterns = [
    path("overview/", TenantPortalOverviewView.as_view(), name="tenant-overview"),
    path("leases/", TenantPortalLeaseListView.as_view(), name="tenant-leases"),
    path("charges/", TenantPortalChargeListView.as_view(), name="tenant-charges"),
    path("payments/", TenantPortalPaymentListView.as_view(), name="tenant-payments"),
    path(
        "payments/<uuid:payment_id>/confirm/",
        TenantPortalPaymentConfirmView.as_view(),
        name="tenant-payment-confirm",
    ),
    path(
        "payments/<uuid:payment_id>/dispute/",
        TenantPortalPaymentDisputeView.as_view(),
        name="tenant-payment-dispute",
    ),
    path(
        "documents/",
        TenantPortalDocumentListView.as_view(),
        name="tenant-documents",
    ),
    path(
        "documents/<uuid:document_id>/pdf/",
        TenantPortalDocumentPdfView.as_view(),
        name="tenant-document-pdf",
    ),
    path(
        "incidents/",
        TenantMaintenanceIncidentListCreateView.as_view(),
        name="tenant-incidents",
    ),
    path(
        "incidents/<uuid:incident_id>/comment/",
        TenantMaintenanceCommentView.as_view(),
        name="tenant-incident-comment",
    ),
    path(
        "incidents/<uuid:incident_id>/respond/",
        TenantMaintenanceResponseView.as_view(),
        name="tenant-incident-response",
    ),
]
