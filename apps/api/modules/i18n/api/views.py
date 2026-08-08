from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AccountPreferencesSerializer, LocalizationOptionsSerializer


class AccountPreferencesView(APIView):
    """Lecture et mise a jour des preferences de localisation du compte."""

    def get(self, request):
        options = LocalizationOptionsSerializer(request.user).data
        preferences = {
            field: getattr(request.user, field)
            for field in (
                "preferred_language",
                "preferred_timezone",
                "preferred_currency",
                "preferred_date_format",
                "preferred_number_format",
            )
        }
        return Response(
            {
                "preferences": preferences,
                "available": options,
            }
        )

    def patch(self, request):
        serializer = AccountPreferencesSerializer(
            data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.update(request.user, serializer.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)
