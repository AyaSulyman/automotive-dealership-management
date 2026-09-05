"""
Vendors API endpoints (API spec section 3). Admin + agent can read/write;
only admin can (soft) delete.
"""
from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.response import Response

from common.permissions import IsAdmin, IsAdminOrAgent, has_role

from .models import Vendor
from .serializers import VendorSerializer


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