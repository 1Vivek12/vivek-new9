"""Comprehensive Multi-Tenant Authorization & Security Isolation Test Suite.

Verifies strict enforcement of tenant boundaries:
1. Authenticated user accessing own tenant -> 200 OK
2. Authenticated user attempting another tenant -> 403 Forbidden
3. Platform admin access -> 200 OK
4. Missing tenant context / missing auth -> 401 Unauthorized
5. Forged X-Tenant-ID header -> 403 Forbidden
6. Tenant membership mismatch -> 403 Forbidden
7. Cross-tenant data isolation in queries -> Zero data leakage
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_authenticated_user_accesses_own_tenant(
    client: AsyncClient, seeded_environment: dict
):
    """Case 1: Authenticated user accessing their own authorized tenant succeeds."""
    token = seeded_environment["token_news9"]
    tenant_news9 = seeded_environment["tenant_news9"]

    response = await client.get(
        "/api/v1/tenants/current",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == tenant_news9.id
    assert data["slug"] == "news9"
    assert data["name"] == "News 9"
    assert data["role"] == "EDITOR"


@pytest.mark.asyncio
async def test_authenticated_user_attempting_cross_tenant_access_is_blocked(
    client: AsyncClient, seeded_environment: dict
):
    """Case 2: Authenticated user attempting another tenant via forged header is rejected."""
    token = seeded_environment["token_news9"]  # Member of News 9 only
    tenant_secondary = seeded_environment["tenant_secondary"]

    response = await client.get(
        "/api/v1/tenants/current",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": tenant_secondary.id,  # Attempting to access secondary tenant
        },
    )
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


@pytest.mark.asyncio
async def test_platform_admin_can_access_tenant_under_oversight(
    client: AsyncClient, seeded_environment: dict
):
    """Case 3: Platform admin can inspect any tenant context with elevated status."""
    token = seeded_environment["token_admin"]
    tenant_secondary = seeded_environment["tenant_secondary"]

    response = await client.get(
        "/api/v1/tenants/current",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": tenant_secondary.id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == tenant_secondary.id
    assert data["is_platform_admin"] is True
    assert data["role"] == "PLATFORM_ADMIN"


@pytest.mark.asyncio
async def test_missing_authentication_token_is_rejected(client: AsyncClient):
    """Case 4: Missing tenant context / unauthenticated request fails with 401."""
    response = await client.get("/api/v1/tenants/current")
    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_forged_tenant_header_never_overrides_authentication(
    client: AsyncClient, seeded_environment: dict
):
    """Case 5: Forged X-Tenant-ID header alone cannot authorize access."""
    tenant_news9 = seeded_environment["tenant_news9"]

    # Request with arbitrary X-Tenant-ID header and NO auth token
    response = await client.get(
        "/api/v1/tenants/current",
        headers={"X-Tenant-ID": tenant_news9.id},
    )
    assert response.status_code == 401

    # Request with forged header from an unauthorized user
    token_secondary = seeded_environment["token_secondary"]
    forged_response = await client.get(
        "/api/v1/tenants/current",
        headers={
            "Authorization": f"Bearer {token_secondary}",
            "X-Tenant-ID": tenant_news9.id,  # Forging News 9 context
        },
    )
    assert forged_response.status_code == 403


@pytest.mark.asyncio
async def test_user_with_no_tenant_membership_is_denied(
    client: AsyncClient, seeded_environment: dict
):
    """Case 6: Valid user account but with zero memberships is denied tenant access."""
    token_unaffiliated = seeded_environment["token_unaffiliated"]

    response = await client.get(
        "/api/v1/tenants/current",
        headers={"Authorization": f"Bearer {token_unaffiliated}"},
    )
    assert response.status_code == 403
    assert "does not belong to any tenant" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cross_tenant_data_isolation_in_audit_logs(
    client: AsyncClient, seeded_environment: dict
):
    """Case 7: Strict data isolation: Caller never sees audit records of other tenants."""
    token_news9 = seeded_environment["token_news9"]
    token_secondary = seeded_environment["token_secondary"]

    # 1. News 9 user fetches audit logs
    res_news9 = await client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {token_news9}"},
    )
    assert res_news9.status_code == 200
    news9_logs = res_news9.json()
    assert len(news9_logs) >= 1
    for log in news9_logs:
        assert log["tenant_id"] == seeded_environment["tenant_news9"].id
        assert "Secondary Client Private Notes" not in str(log["metadata"])

    # 2. Secondary tenant user fetches audit logs
    res_sec = await client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {token_secondary}"},
    )
    assert res_sec.status_code == 200
    sec_logs = res_sec.json()
    assert len(sec_logs) >= 1
    for log in sec_logs:
        assert log["tenant_id"] == seeded_environment["tenant_secondary"].id
        assert "Gorakhpur Infrastructure Update" not in str(log["metadata"])
