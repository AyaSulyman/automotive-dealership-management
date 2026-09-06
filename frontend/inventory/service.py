from services.api_client import get_all, request_binary, request_json


def get_vehicles(access_token, *, search="", status="", page=1, page_size=10):
    return request_json(
        "GET",
        "/vehicles",
        access_token=access_token,
        params={
            "search": search,
            "status": status,
            "page": page,
            "page_size": page_size,
        },
    )


def get_vehicle(access_token, vehicle_id):
    return request_json(
        "GET", f"/vehicles/{vehicle_id}", access_token=access_token
    )


def create_vehicle(access_token, vehicle):
    return request_json(
        "POST", "/vehicles", access_token=access_token, payload=vehicle
    )


def update_vehicle(access_token, vehicle_id, vehicle):
    return request_json(
        "PATCH",
        f"/vehicles/{vehicle_id}",
        access_token=access_token,
        payload=vehicle,
    )


def delete_vehicle(access_token, vehicle_id):
    return request_json(
        "DELETE", f"/vehicles/{vehicle_id}", access_token=access_token
    )


def get_vendors(
    access_token, *, search="", status="", page=1, page_size=10
):
    is_active = ""
    if status.lower() in {"active", "inactive"}:
        is_active = status.lower() == "active"
    return request_json(
        "GET",
        "/vendors",
        access_token=access_token,
        params={
            "search": search,
            "is_active": is_active,
            "page": page,
            "page_size": page_size,
        },
    )


def get_vendor(access_token, vendor_id):
    return request_json(
        "GET", f"/vendors/{vendor_id}", access_token=access_token
    )


def create_vendor(access_token, vendor):
    return request_json(
        "POST", "/vendors", access_token=access_token, payload=vendor
    )


def update_vendor(access_token, vendor_id, vendor):
    return request_json(
        "PATCH",
        f"/vendors/{vendor_id}",
        access_token=access_token,
        payload=vendor,
    )


def get_purchase_orders(
    access_token, *, search="", status="", page=1, page_size=10
):
    return request_json(
        "GET",
        "/purchase-orders",
        access_token=access_token,
        params={
            "search": search,
            "status": status,
            "page": page,
            "page_size": page_size,
        },
    )


def get_purchase_order(access_token, purchase_order_id):
    return request_json(
        "GET",
        f"/purchase-orders/{purchase_order_id}",
        access_token=access_token,
    )


def update_purchase_order_status(access_token, purchase_order_id, status):
    return request_json(
        "PATCH",
        f"/purchase-orders/{purchase_order_id}",
        access_token=access_token,
        payload={"status": status},
    )


def get_documents(access_token, related_type, related_id):
    return get_all(
        "/documents", access_token=access_token,
        params={"related_type": related_type, "related_id": related_id},
    )


def upload_document(access_token, related_type, related_id, doc_type, uploaded):
    return request_json(
        "POST", "/documents", access_token=access_token,
        payload={"related_type": related_type, "related_id": related_id, "doc_type": doc_type},
        files={"file": (uploaded.name, uploaded.file, uploaded.content_type)},
    )


def delete_document(access_token, document_id):
    return request_json("DELETE", f"/documents/{document_id}", access_token=access_token)


def download_document(access_token, document_id):
    return request_binary(f"/documents/{document_id}/download", access_token=access_token)
