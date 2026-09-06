"""
Vendors API endpoints (API spec section 3). Admin + agent can read/write;
only admin can (soft) delete.
"""
import os
from django.http import FileResponse
from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from common.permissions import IsAdmin, IsAdminOrAgent, IsAdminAgentOrAccountant, has_role

from .models import Document, PurchaseOrder, Vehicle, VehicleMedia, VehicleValuation, Vendor
from .serializers import (
    DocumentSerializer, PurchaseOrderCreateSerializer, PurchaseOrderSerializer, VehicleCreateSerializer,
    VehicleMediaSerializer, VehicleSerializer, VehicleValuationSerializer, VendorSerializer,
)

PO_TRANSITIONS = {
    "PENDING": {"RECEIVED"},
    "RECEIVED": {"CLOSED"},
    "CLOSED": set(),
    "CANCELLED": set(),
}


@extend_schema_view(
    get=extend_schema(tags=["Vendors"], summary="List vendors (?search=)"),
    post=extend_schema(tags=["Vendors"], summary="Create a vendor"),
)
class VendorListCreateView(generics.ListCreateAPIView):
    queryset = Vendor.objects.all().order_by("name")
    serializer_class = VendorSerializer
    permission_classes = [IsAdminOrAgent]

    def get_queryset(self):
        qs = Vendor.objects.all().order_by("name")
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(contact_person__icontains=search)
                | Q(email__icontains=search) | Q(phone__icontains=search)
            )
        is_active = self.request.query_params.get("is_active")
        if is_active is not None and is_active != "":
            qs = qs.filter(is_active=is_active.strip().lower() in {"1", "true", "yes"})
        return qs


@extend_schema_view(
    get=extend_schema(tags=["Vendors"], summary="Vendor detail"),
    patch=extend_schema(tags=["Vendors"], summary="Edit a vendor"),
    delete=extend_schema(tags=["Vendors"], summary="Soft-delete a vendor (admin only)"),
)
class VendorDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [IsAdminOrAgent]

    def destroy(self, request, *args, **kwargs):
        if not has_role(request.user, "admin"):
            return Response(
                {"error": {"code": "forbidden", "message": "Admins only.", "fields": {}}},
                status=status.HTTP_403_FORBIDDEN,
            )
        vendor = self.get_object()
        vendor.is_active = False
        vendor.save(update_fields=["is_active", "updated_at"])
        return Response(
            {"message": f"Vendor '{vendor.name}' deactivated."}, status=status.HTTP_200_OK,
        )


@extend_schema_view(
    get=extend_schema(tags=["Purchase Orders"], summary="List purchase orders (?vendor_id=&status=)"),
    post=extend_schema(tags=["Purchase Orders"], summary="Create a purchase order",
                       request=PurchaseOrderCreateSerializer, responses={201: PurchaseOrderSerializer}),
)
class PurchaseOrderListCreateView(generics.ListCreateAPIView):
    queryset = PurchaseOrder.objects.select_related("vendor").order_by("-created_at")
    permission_classes = [IsAdminOrAgent]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PurchaseOrderCreateSerializer
        return PurchaseOrderSerializer

    def get_queryset(self):
        qs = PurchaseOrder.objects.select_related("vendor").order_by("-created_at")
        params = self.request.query_params
        vendor_id = params.get("vendor_id")
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        po_status = params.get("status")
        if po_status:
            qs = qs.filter(status=po_status)
        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(po_number__icontains=search) | Q(vendor__name__icontains=search)
            )
        return qs

    def create(self, request, *args, **kwargs):
        serializer = PurchaseOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        po = serializer.save(created_by=request.user if request.user.is_authenticated else None)
        return Response(PurchaseOrderSerializer(po).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["Purchase Orders"], summary="Purchase order detail"),
    patch=extend_schema(tags=["Purchase Orders"], summary="Update PO (PENDING>RECEIVED>CLOSED)",
                        request=PurchaseOrderCreateSerializer, responses={200: PurchaseOrderSerializer}),
    delete=extend_schema(tags=["Purchase Orders"], summary="Cancel PO (admin, only before vehicles received)"),
)
class PurchaseOrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PurchaseOrder.objects.select_related("vendor")
    permission_classes = [IsAdminOrAgent]

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return PurchaseOrderSerializer
        return PurchaseOrderSerializer

    def update(self, request, *args, **kwargs):
        po = self.get_object()
        new_status = request.data.get("status")
        if new_status and new_status != po.status:
            if new_status not in PO_TRANSITIONS.get(po.status, set()):
                return Response(
                    {"error": {"code": "conflict",
                               "message": f"Cannot move PO from {po.status} to {new_status} "
                                          f"(allowed: {sorted(PO_TRANSITIONS.get(po.status, set()))}).",
                               "fields": {}}},
                    status=status.HTTP_409_CONFLICT,
                )
        serializer = PurchaseOrderSerializer(po, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PurchaseOrderSerializer(po).data)

    def destroy(self, request, *args, **kwargs):
        if not has_role(request.user, "admin"):
            return Response(
                {"error": {"code": "forbidden", "message": "Admins only.", "fields": {}}},
                status=status.HTTP_403_FORBIDDEN,
            )
        po = self.get_object()
        if po.status in ("CLOSED", "CANCELLED"):
            return Response(
                {"error": {"code": "conflict", "message": f"PO is already {po.status.lower()}.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        if po.has_received_vehicles():
            return Response(
                {"error": {"code": "conflict",
                           "message": "Cannot cancel this PO: vehicles have already been received against it.",
                           "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        po.status = "CANCELLED"
        po.save(update_fields=["status", "updated_at"])
        return Response({"message": f"PO {po.po_number} cancelled."}, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(tags=["Vehicles"], summary="List vehicles (?search=&status=&branch_id=)"),
    post=extend_schema(tags=["Vehicles"], summary="Vehicle intake / goods receipt",
                       request=VehicleCreateSerializer, responses={201: VehicleSerializer}),
)
class VehicleListCreateView(generics.ListCreateAPIView):
    queryset = Vehicle.objects.select_related("branch", "purchase_order").order_by("-created_at")
    serializer_class = VehicleSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAdminOrAgent()]
        return [IsAdminOrAgent()]

    def get_queryset(self):
        qs = Vehicle.objects.select_related("branch", "purchase_order").order_by("-created_at")
        params = self.request.query_params
        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(vin__icontains=search) | Q(make__icontains=search) | Q(model__icontains=search)
            )
        veh_status = params.get("status")
        if veh_status:
            qs = qs.filter(status=veh_status)
        branch_id = params.get("branch_id")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return qs

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VehicleCreateSerializer
        return VehicleSerializer

    def create(self, request, *args, **kwargs):
        serializer = VehicleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vehicle = serializer.save(
            created_by=request.user if request.user.is_authenticated else None,
        )
        return Response(VehicleSerializer(vehicle).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["Vehicles"], summary="Vehicle detail"),
    patch=extend_schema(tags=["Vehicles"], summary="Edit a vehicle",
                        request=VehicleSerializer, responses={200: VehicleSerializer}),
    delete=extend_schema(tags=["Vehicles"], summary="Delete vehicle (admin, blocked once sold)"),
)
class VehicleDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Vehicle.objects.select_related("branch", "purchase_order")
    serializer_class = VehicleSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAdminOrAgent()]
        return [IsAdminOrAgent()]

    def destroy(self, request, *args, **kwargs):
        if not has_role(request.user, "admin"):
            return Response(
                {"error": {"code": "forbidden", "message": "Admins only.", "fields": {}}},
                status=status.HTTP_403_FORBIDDEN,
            )
        vehicle = self.get_object()
        if vehicle.status in {"RESERVED", "SOLD"}:
            return Response(
                {"error": {"code": "conflict",
                           "message": "A reserved or sold vehicle cannot be deleted from inventory.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        vehicle.delete()
        return Response(
            {"message": f"Vehicle {vehicle.vin} deleted."}, status=status.HTTP_200_OK,
        )


@extend_schema_view(
    post=extend_schema(tags=["Vehicles"], summary="Upload vehicle photo/video (multipart)",
                       request=VehicleMediaSerializer, responses={201: VehicleMediaSerializer}),
)
class VehicleMediaCreateView(generics.CreateAPIView):
    """POST /vehicles/{pk}/media — multipart form: file, media_type, caption."""

    serializer_class = VehicleMediaSerializer
    permission_classes = [IsAdminOrAgent]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, pk, *args, **kwargs):
        vehicle = get_object_or_404(Vehicle, pk=pk)
        serializer = VehicleMediaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        media = serializer.save(vehicle=vehicle, uploaded_by=request.user)
        return Response(VehicleMediaSerializer(media).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    delete=extend_schema(tags=["Vehicles"], summary="Delete a vehicle media item"),
)
class VehicleMediaDeleteView(generics.DestroyAPIView):
    """DELETE /vehicles/{pk}/media/{media_id}"""

    queryset = VehicleMedia.objects.all()
    serializer_class = VehicleMediaSerializer
    permission_classes = [IsAdminOrAgent]

    def get_object(self):
        return get_object_or_404(
            VehicleMedia, pk=self.kwargs["media_id"], vehicle_id=self.kwargs["pk"],
        )

    def destroy(self, request, *args, **kwargs):
        media = self.get_object()
        media.delete()
        return Response({"message": "Media deleted."}, status=status.HTTP_200_OK)


@extend_schema_view(
    post=extend_schema(tags=["Vehicles"], summary="Record a vehicle valuation",
                       request=VehicleValuationSerializer, responses={201: VehicleValuationSerializer}),
)
class VehicleValuationCreateView(generics.CreateAPIView):
    """POST /vehicles/{pk}/valuation — body: value, source (default MANUAL), notes."""

    serializer_class = VehicleValuationSerializer
    permission_classes = [IsAdminOrAgent]

    def create(self, request, pk, *args, **kwargs):
        vehicle = get_object_or_404(Vehicle, pk=pk)
        serializer = VehicleValuationSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        valuation = serializer.save(vehicle=vehicle, appraised_by=request.user)
        return Response(VehicleValuationSerializer(valuation).data, status=status.HTTP_201_CREATED)


def _document_types_for(user):
    if has_role(user, "admin"):
        return {"VEHICLE", "CUSTOMER", "INVOICE"}
    if has_role(user, "agent"):
        return {"VEHICLE", "CUSTOMER"}
    if has_role(user, "accountant"):
        return {"INVOICE"}
    return set()


@extend_schema_view(
    get=extend_schema(tags=["Documents"], summary="List documents (?related_type=&related_id=)"),
    post=extend_schema(tags=["Documents"], summary="Upload a document (multipart)",
                       request=DocumentSerializer, responses={201: DocumentSerializer}),
)
class DocumentListCreateView(generics.ListCreateAPIView):
    queryset = Document.objects.select_related("uploaded_by").order_by("-created_at")
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        return [IsAdminAgentOrAccountant()]

    def get_queryset(self):
        qs = Document.objects.select_related("uploaded_by").filter(
            related_type__in=_document_types_for(self.request.user),
        ).order_by("-created_at")
        params = self.request.query_params
        related_type = params.get("related_type")
        if related_type:
            qs = qs.filter(related_type=related_type)
        related_id = params.get("related_id")
        if related_id:
            qs = qs.filter(related_id=related_id)
        return qs

    def create(self, request, *args, **kwargs):
        related_type = str(request.data.get("related_type", "")).upper()
        if related_type not in _document_types_for(request.user):
            raise PermissionDenied("You cannot manage documents for that record type.")
        uploaded = request.FILES.get("file")
        serializer = DocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save(
            uploaded_by=request.user,
            original_filename=os.path.basename(uploaded.name) if uploaded else "",
        )
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    delete=extend_schema(tags=["Documents"], summary="Delete a document"),
)
class DocumentDeleteView(generics.DestroyAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAdminAgentOrAccountant]

    def get_queryset(self):
        return Document.objects.filter(
            related_type__in=_document_types_for(self.request.user),
        )

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        document.file.delete(save=False)
        document.delete()
        return Response({"message": "Document deleted."}, status=status.HTTP_200_OK)


class DocumentDownloadView(generics.RetrieveAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [IsAdminAgentOrAccountant]

    def get_queryset(self):
        return Document.objects.filter(
            related_type__in=_document_types_for(self.request.user),
        )

    def get(self, request, *args, **kwargs):
        document = self.get_object()
        return FileResponse(
            document.file.open("rb"), as_attachment=True,
            filename=os.path.basename(document.original_filename or document.file.name),
        )
