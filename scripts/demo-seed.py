#!/usr/bin/env python3
"""Meatapivot Demo Data Seeder

一键生成演示数据，用于本地开发联调和功能演示。

Usage:
    python scripts/demo-seed.py
    python scripts/demo-seed.py --base-url http://localhost:8000/api/v1
    python scripts/demo-seed.py --token eyJhbGciOiJIUzI1NiIs...
"""

import argparse
import sys
import uuid
from typing import Optional

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: pip install httpx")
    sys.exit(1)


DEMO_USERNAME = "demo-seed"
DEMO_PASSWORD = "demo123"
DEMO_TENANT = "tenant-default"

OBJECT_TYPES = [
    {
        "name": "Customer",
        "display_name": "客户",
        "description": "企业客户实体",
        "icon": "user",
        "properties": [
            {"name": "name", "type": "string", "required": True},
            {"name": "email", "type": "string", "required": True},
            {"name": "phone", "type": "string", "required": False},
            {"name": "vip_level", "type": "int", "required": False},
            {"name": "registered_at", "type": "date", "required": False},
        ],
    },
    {
        "name": "Product",
        "display_name": "产品",
        "description": "销售产品实体",
        "icon": "box",
        "properties": [
            {"name": "sku", "type": "string", "required": True},
            {"name": "name", "type": "string", "required": True},
            {"name": "price", "type": "float", "required": True},
            {"name": "category", "type": "string", "required": False},
            {"name": "in_stock", "type": "boolean", "required": False},
        ],
    },
    {
        "name": "Order",
        "display_name": "订单",
        "description": "客户订单实体",
        "icon": "file-text",
        "properties": [
            {"name": "order_no", "type": "string", "required": True},
            {"name": "total_amount", "type": "float", "required": True},
            {"name": "status", "type": "string", "required": True},
            {"name": "placed_at", "type": "date", "required": False},
        ],
    },
]

CUSTOMERS = [
    {"object_key": "CUST-001", "properties": {"name": "张三", "email": "zhangsan@example.com", "phone": "13800138001", "vip_level": 3, "registered_at": "2023-01-15"}},
    {"object_key": "CUST-002", "properties": {"name": "李四", "email": "lisi@example.com", "phone": "13800138002", "vip_level": 1, "registered_at": "2023-03-20"}},
    {"object_key": "CUST-003", "properties": {"name": "王五", "email": "wangwu@example.com", "phone": "13800138003", "vip_level": 2, "registered_at": "2023-06-10"}},
]

PRODUCTS = [
    {"object_key": "PROD-001", "properties": {"sku": "SKU-A001", "name": "智能手表 Pro", "price": 2999.0, "category": "电子产品", "in_stock": True}},
    {"object_key": "PROD-002", "properties": {"sku": "SKU-B002", "name": "无线耳机 Air", "price": 899.0, "category": "电子产品", "in_stock": True}},
    {"object_key": "PROD-003", "properties": {"sku": "SKU-C003", "name": "机械键盘", "price": 599.0, "category": "办公设备", "in_stock": False}},
]

ORDERS = [
    {"object_key": "ORD-2024-001", "properties": {"order_no": "ORD-2024-001", "total_amount": 3898.0, "status": "completed", "placed_at": "2024-01-15"}},
    {"object_key": "ORD-2024-002", "properties": {"order_no": "ORD-2024-002", "total_amount": 899.0, "status": "shipped", "placed_at": "2024-01-16"}},
]


def get_token(base_url: str, username: str, password: str) -> str:
    resp = httpx.post(
        f"{base_url}/auth/login",
        data={"username": username, "password": password},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def ensure_user(base_url: str, token: Optional[str] = None) -> str:
    """Register demo user if not exists, then login and return token."""
    try:
        return get_token(base_url, DEMO_USERNAME, DEMO_PASSWORD)
    except httpx.HTTPStatusError:
        # User probably doesn't exist, register first
        register_resp = httpx.post(
            f"{base_url}/auth/register",
            json={
                "username": DEMO_USERNAME,
                "email": f"{DEMO_USERNAME}@example.com",
                "password": DEMO_PASSWORD,
                "tenant_id": DEMO_TENANT,
            },
            timeout=10,
        )
        if register_resp.status_code not in (200, 201):
            print(f"Registration failed: {register_resp.text}")
            sys.exit(1)
        return get_token(base_url, DEMO_USERNAME, DEMO_PASSWORD)


def create_object_type(client: httpx.Client, ot_data: dict) -> str:
    resp = client.post("/ontology/object-types", json=ot_data)
    if resp.status_code == 409:
        # Already exists, find by name
        list_resp = client.get("/ontology/object-types")
        list_resp.raise_for_status()
        for item in list_resp.json().get("items", []):
            if item["name"] == ot_data["name"]:
                print(f"  ObjectType '{ot_data['name']}' already exists (id={item['id']})")
                return item["id"]
    resp.raise_for_status()
    data = resp.json()
    print(f"  Created ObjectType '{ot_data['name']}' (id={data['id']})")
    return data["id"]


def create_object(client: httpx.Client, type_id: str, obj_data: dict) -> str:
    resp = client.post(f"/ontology/object-types/{type_id}/objects", json=obj_data)
    resp.raise_for_status()
    data = resp.json()
    print(f"    Created Object {obj_data['object_key']} (id={data['id']})")
    return data["id"]


def create_link_type(client: httpx.Client, lt_data: dict) -> str:
    resp = client.post("/ontology/link-types", json=lt_data)
    if resp.status_code == 409:
        list_resp = client.get("/ontology/link-types")
        list_resp.raise_for_status()
        for item in list_resp.json().get("items", []):
            if item["name"] == lt_data["name"]:
                print(f"  LinkType '{lt_data['name']}' already exists (id={item['id']})")
                return item["id"]
    resp.raise_for_status()
    data = resp.json()
    print(f"  Created LinkType '{lt_data['name']}' (id={data['id']})")
    return data["id"]


def create_link(client: httpx.Client, lt_id: str, source_id: str, target_id: str) -> str:
    resp = client.post(
        "/ontology/links",
        json={"link_type_id": lt_id, "source_object_id": source_id, "target_object_id": target_id, "properties": {}},
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"    Created Link {source_id[:8]}... -> {target_id[:8]}... (id={data['id']})")
    return data["id"]


def main():
    parser = argparse.ArgumentParser(description="Meatapivot Demo Data Seeder")
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1", help="Backend API base URL")
    parser.add_argument("--token", default=None, help="JWT access token (optional, will auto-login if not provided)")
    parser.add_argument("--tenant-id", default=DEMO_TENANT, help="Tenant ID")
    args = parser.parse_args()

    print(f"=== Meatapivot Demo Seeder ===")
    print(f"Base URL: {args.base_url}")

    # Authenticate
    if args.token:
        token = args.token
        print("Using provided token")
    else:
        print("Authenticating demo user...")
        token = ensure_user(args.base_url)
        print("Authenticated successfully")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    with httpx.Client(base_url=args.base_url, headers=headers, timeout=30) as client:
        # 1. Create Object Types
        print("\n[1/4] Creating ObjectTypes...")
        ot_ids = {}
        for ot in OBJECT_TYPES:
            ot_ids[ot["name"]] = create_object_type(client, ot)

        # 2. Create Objects
        print("\n[2/4] Creating Objects...")
        object_ids = {}
        for obj in CUSTOMERS:
            oid = create_object(client, ot_ids["Customer"], obj)
            object_ids[obj["object_key"]] = oid
        for obj in PRODUCTS:
            oid = create_object(client, ot_ids["Product"], obj)
            object_ids[obj["object_key"]] = oid
        for obj in ORDERS:
            oid = create_object(client, ot_ids["Order"], obj)
            object_ids[obj["object_key"]] = oid

        # 3. Create Link Types
        print("\n[3/4] Creating LinkTypes...")
        lt_placed_by = create_link_type(client, {
            "name": "placed_by",
            "display_name": "由...下单",
            "source_object_type_id": ot_ids["Order"],
            "target_object_type_id": ot_ids["Customer"],
            "cardinality": "MANY_TO_ONE",
            "status": "active",
        })
        lt_contains = create_link_type(client, {
            "name": "contains",
            "display_name": "包含",
            "source_object_type_id": ot_ids["Order"],
            "target_object_type_id": ot_ids["Product"],
            "cardinality": "MANY_TO_MANY",
            "status": "active",
        })

        # 4. Create Links
        print("\n[4/4] Creating Links...")
        create_link(client, lt_placed_by, object_ids["ORD-2024-001"], object_ids["CUST-001"])
        create_link(client, lt_placed_by, object_ids["ORD-2024-002"], object_ids["CUST-002"])
        create_link(client, lt_contains, object_ids["ORD-2024-001"], object_ids["PROD-001"])
        create_link(client, lt_contains, object_ids["ORD-2024-001"], object_ids["PROD-002"])
        create_link(client, lt_contains, object_ids["ORD-2024-002"], object_ids["PROD-002"])

    print("\n=== Demo seed completed successfully ===")
    print("Open http://localhost:3000 and navigate to ObjectTypeList to see the data.")


if __name__ == "__main__":
    main()
