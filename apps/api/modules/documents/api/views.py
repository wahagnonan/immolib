from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from modules.payments.services import (
    confirm_payment_by_tenant,
    dispute_payment_by_tenant,
)
from config.pagination import LargeListPagination

from ..models import NotificationDelivery, RentalDocument
from ..pdfs import build_rental_document_pdf, rental_document_pdf_filename
from ..selectors import (
    visible_documents_for,
    visible_notification_deliveries_for,
)
from ..services import (
    request_document_otp,
    prepare_manual_share,
    resolve_document_grant,
    share_document,
    tenant_for_document,
    verify_document_otp,
)
from ..throttles import (
    DocumentGrantThrottle,
    DocumentOtpRequestThrottle,
    DocumentOtpVerifyThrottle,
    PublicDocumentIpThrottle,
)
from .serializers import (
    GrantSerializer,
    ManualShareSerializer,
    PaymentResponseSerializer,
    PublicPaymentStatusSerializer,
    PublicDocumentVerificationSerializer,
    NotificationDeliverySerializer,
    RentalDocumentSerializer,
    RequestOtpSerializer,
    ShareDocumentSerializer,
    VerifyOtpSerializer,
)


class PublicReferenceVerificationThrottle(AnonRateThrottle):
    rate = "30/minute"


def _raise_api_validation_error(exc: DjangoValidationError) -> None:
    if hasattr(exc, "message_dict"):
        raise ValidationError(exc.message_dict) from exc
    raise ValidationError(exc.messages) from exc


def _date_filter(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({field: "Utilisez le format AAAA-MM-JJ."}) from exc


def _pdf_response(document: RentalDocument) -> HttpResponse:
    content = build_rental_document_pdf(document)
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{rental_document_pdf_filename(document)}"'
    )
    response["Content-Length"] = str(len(content))
    response["Cache-Control"] = "private, no-store"
    return response


class RentalDocumentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)
    pagination_class = LargeListPagination

    def get_queryset(self):
        queryset = visible_documents_for(self.request.user).select_related(
            "payment", "rent_charge__lease__property", "rent_charge__lease__tenant"
        )
        document_type = self.request.query_params.get("document_type")
        status_filter = self.request.query_params.get("status")
        issued_from = self.request.query_params.get("issued_from")
        issued_to = self.request.query_params.get("issued_to")
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if issued_from:
            queryset = queryset.filter(
                issued_at__date__gte=_date_filter(issued_from, "issued_from")
            )
        if issued_to:
            queryset = queryset.filter(
                issued_at__date__lte=_date_filter(issued_to, "issued_to")
            )
        return queryset

    def get_serializer_class(self):
        if self.action == "share":
            return ShareDocumentSerializer
        if self.action == "manual_share":
            return ManualShareSerializer
        return RentalDocumentSerializer

    @action(detail=True, methods=["post"])
    def share(self, request: Request, pk=None) -> Response:
        document = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            result = share_document(
                actor=request.user,
                document=document,
                channels=input_serializer.validated_data["channels"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(
            {
                "access_link_id": str(result.access_link.id),
                "secure_url": result.secure_url,
                "expires_at": result.access_link.expires_at,
                "deliveries": [
                    {"channel": item.channel, "status": item.status}
                    for item in result.deliveries
                ],
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="manual-share")
    def manual_share(self, request: Request, pk=None) -> Response:
        document = self.get_object()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            result = prepare_manual_share(
                actor=request.user,
                document=document,
                channel=input_serializer.validated_data["channel"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(
            {
                "event_id": str(result.event.id),
                "access_link_id": str(result.access_link.id),
                "secure_url": result.secure_url,
                "expires_at": result.access_link.expires_at,
                "subject": result.subject,
                "message": result.message,
                "action_url": result.action_url,
                "channel": result.event.channel,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request: Request, pk=None) -> HttpResponse:
        return _pdf_response(self.get_object())


class NotificationDeliveryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationDeliverySerializer
    pagination_class = LargeListPagination

    def get_queryset(self):
        queryset = visible_notification_deliveries_for(
            self.request.user
        ).select_related(
            "access_link__document",
            "otp_challenge",
            "rent_charge__lease__tenant",
            "rent_charge__lease__property",
            "tenant_invitation__tenant__property",
        )
        document_id = self.request.query_params.get("document_id")
        rent_charge_id = self.request.query_params.get("rent_charge_id")
        status_filter = self.request.query_params.get("status")
        kind = self.request.query_params.get("kind")
        if document_id:
            queryset = queryset.filter(access_link__document_id=document_id)
        if rent_charge_id:
            queryset = queryset.filter(rent_charge_id=rent_charge_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if kind:
            queryset = queryset.filter(kind=kind)
        return queryset.order_by("-created_at")


class PublicDocumentAccessViewSet(viewsets.GenericViewSet):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get_serializer_class(self):
        return {
            "request_otp": RequestOtpSerializer,
            "verify_otp": VerifyOtpSerializer,
            "view_document": GrantSerializer,
            "download_document": GrantSerializer,
            "payment_response": PaymentResponseSerializer,
        }.get(self.action, GrantSerializer)

    @action(
        detail=False,
        methods=["get"],
        url_path="verify-reference",
        throttle_classes=(PublicReferenceVerificationThrottle,),
    )
    def verify_reference(self, request: Request) -> Response:
        reference = request.query_params.get("reference", "").strip().upper()
        if not reference:
            raise ValidationError(
                {"reference": "Saisissez le numéro du document."}
            )
        document = RentalDocument.objects.filter(reference__iexact=reference).first()
        if document is None:
            raise NotFound(
                "Aucun document ImmoLib ne correspond à cette référence."
            )
        return Response(PublicDocumentVerificationSerializer(document).data)

    @action(
        detail=False,
        methods=["post"],
        url_path="request-otp",
        throttle_classes=(PublicDocumentIpThrottle, DocumentOtpRequestThrottle),
    )
    def request_otp(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = request_document_otp(
                access_token=serializer.validated_data["access_token"],
                channel=serializer.validated_data["channel"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        response = {
            "challenge_id": str(result.challenge.id),
            "masked_destination": result.masked_destination,
            "expires_at": result.challenge.expires_at,
        }
        if settings.EXPOSE_TEST_OTP:
            response["otp_code"] = result.code
        response_status = (
            status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        )
        return Response(response, status=response_status)

    @action(
        detail=False,
        methods=["post"],
        url_path="verify-otp",
        throttle_classes=(PublicDocumentIpThrottle, DocumentOtpVerifyThrottle),
    )
    def verify_otp(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            grant_token = verify_document_otp(
                challenge_id=serializer.validated_data["challenge_id"],
                code=serializer.validated_data["code"],
            )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response({"grant_token": grant_token}, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path="view-document",
        throttle_classes=(PublicDocumentIpThrottle, DocumentGrantThrottle),
    )
    def view_document(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = resolve_document_grant(serializer.validated_data["grant_token"])
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(RentalDocumentSerializer(document).data)

    @action(
        detail=False,
        methods=["post"],
        url_path="download-document",
        throttle_classes=(PublicDocumentIpThrottle, DocumentGrantThrottle),
    )
    def download_document(self, request: Request) -> HttpResponse:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = resolve_document_grant(serializer.validated_data["grant_token"])
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return _pdf_response(document)

    @action(
        detail=False,
        methods=["post"],
        url_path="payment-response",
        throttle_classes=(PublicDocumentIpThrottle, DocumentGrantThrottle),
    )
    def payment_response(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = resolve_document_grant(serializer.validated_data["grant_token"])
            if document.document_type != RentalDocument.Type.PAYMENT_RECEIPT:
                raise DjangoValidationError(
                    "La reponse concerne uniquement un recu de paiement."
                )
            tenant = tenant_for_document(document)
            if serializer.validated_data["action"] == "CONFIRM":
                payment = confirm_payment_by_tenant(
                    tenant=tenant, payment=document.payment
                )
            else:
                payment = dispute_payment_by_tenant(
                    tenant=tenant,
                    payment=document.payment,
                    reason=serializer.validated_data["reason"],
                )
        except DjangoValidationError as exc:
            _raise_api_validation_error(exc)
        return Response(PublicPaymentStatusSerializer(payment).data)
