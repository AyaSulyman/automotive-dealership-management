from django.utils.crypto import get_random_string
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdminOrAgent

from .models import TradeIn
from .serializers import ApplyCreditSerializer, TradeInSerializer


class TradeInListCreateView(generics.ListCreateAPIView):
    """
    POST /trade-ins        Capture appraisal.
    """
    queryset = TradeIn.objects.all()
    serializer_class = TradeInSerializer
    permission_classes = [IsAdminOrAgent]
    filterset_fields = ["customer_id"]

    def perform_create(self, serializer):
        serializer.save(appraised_by=self.request.user)


class TradeInDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   /trade-ins/{id}     Trade-in detail.
    PATCH /trade-ins/{id}     Edit appraisal before it's credited.
    """
    queryset = TradeIn.objects.all()
    serializer_class = TradeInSerializer
    permission_classes = [IsAdminOrAgent]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_credited:
            return Response(
                {"error": {"code": "conflict", "message": "This trade-in has already been credited to an invoice and can no longer be edited.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)


class TradeInApplyCreditView(APIView):
    """
    POST /trade-ins/{id}/apply-credit
    Body: {"invoice_id": <int>}
    Sets credited_invoice_id and returns a generated reference code
    (e.g. "TRD-993-A2") matching the "Credited Invoice ID (Generated)"
    field shown on the Sales & Trade-Ins screen.
    """
    permission_classes = [IsAdminOrAgent]

    def post(self, request, pk):
        trade_in = generics.get_object_or_404(TradeIn, pk=pk)
        if trade_in.is_credited:
            return Response(
                {"error": {"code": "conflict", "message": "Trade-in is already credited to an invoice.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ApplyCreditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reference = f"TRD-{trade_in.pk:03d}-{get_random_string(2, allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZ23456789')}"
        trade_in.credited_invoice_id = serializer.validated_data["invoice_id"]
        trade_in.credited_reference = reference
        trade_in.save(update_fields=["credited_invoice_id", "credited_reference", "updated_at"])

        return Response(TradeInSerializer(trade_in).data, status=status.HTTP_200_OK)
