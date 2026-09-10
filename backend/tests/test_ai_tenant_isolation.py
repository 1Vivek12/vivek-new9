"""Multi-tenant isolation and RBAC authorization tests for Phase 4 AI Research."""

import pytest

from app.core.security import create_access_token, hash_password
from app.db.models.membership import TenantMembership
from app.db.models.story import Story
from app.db.models.user import User


@pytest.mark.asyncio
async def test_cross_tenant_research_isolation(client, seeded_environment, db_session):
    """Verify Tenant B cannot read or access Tenant A research jobs, briefs, or outputs."""
    env = seeded_environment
    tenant_a_id = env["tenant_news9"].id
    tenant_b_id = env["tenant_secondary"].id
    user_a_id = env["user_news9"].id

    headers_tenant_a = {
        "Authorization": f"Bearer {env['token_news9']}",
        "X-Tenant-ID": tenant_a_id,
    }
    headers_tenant_b = {
        "Authorization": f"Bearer {env['token_secondary']}",
        "X-Tenant-ID": tenant_b_id,
    }

    # Create story in Tenant A
    story_a = Story(
        tenant_id=tenant_a_id,
        title="Tenant A Confidential Investigative Lead",
        slug="tenant-a-confidential",
        summary="Sensitive whistleblower documents.",
        created_by_user_id=user_a_id,
    )
    db_session.add(story_a)
    await db_session.commit()

    # Trigger research in Tenant A
    res = await client.post(f"/api/v1/stories/{story_a.id}/research", headers=headers_tenant_a)
    assert res.status_code == 201
    job_id = res.json()["id"]

    # 1. Tenant B attempts to read Tenant A research job -> 404
    job_leak = await client.get(f"/api/v1/research/{job_id}", headers=headers_tenant_b)
    assert job_leak.status_code == 404

    # 2. Tenant B attempts to read Tenant A evidence -> 404
    ev_leak = await client.get(f"/api/v1/research/{job_id}/evidence", headers=headers_tenant_b)
    assert ev_leak.status_code == 404

    # 3. Tenant B attempts to read Tenant A brief -> 404
    br_leak = await client.get(f"/api/v1/research/{job_id}/brief", headers=headers_tenant_b)
    assert br_leak.status_code == 404

    # Generate AI Output in Tenant A
    out_res = await client.post(f"/api/v1/stories/{story_a.id}/headlines", headers=headers_tenant_a)
    assert out_res.status_code == 201
    output_id = out_res.json()["id"]

    # 4. Tenant B attempts to read Tenant A AI output -> 404
    out_leak = await client.get(f"/api/v1/ai-outputs/{output_id}", headers=headers_tenant_b)
    assert out_leak.status_code == 404

    # 5. Tenant B attempts to accept Tenant A AI output -> 404
    act_leak = await client.post(f"/api/v1/ai-outputs/{output_id}/accept", headers=headers_tenant_b)
    assert act_leak.status_code == 404


@pytest.mark.asyncio
async def test_rbac_reporter_cannot_accept_ai_output(client, seeded_environment, db_session):
    """Verify strict human review gate: REPORTER role cannot accept or reject AI content (403)."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id

    # Create a reporter user in tenant_news9
    reporter = User(
        id="user-news9-reporter-id",
        email="reporter@news9.org",
        full_name="Junior News Reporter",
        hashed_password=hash_password("Pass123!"),
        is_active=True,
    )
    db_session.add(reporter)
    await db_session.flush()

    membership = TenantMembership(
        tenant_id=tenant_id,
        user_id=reporter.id,
        role="REPORTER",
    )
    db_session.add(membership)

    story = Story(
        tenant_id=tenant_id,
        title="Local Sports Ground Inauguration",
        slug="local-sports-ground",
        created_by_user_id=reporter.id,
    )
    db_session.add(story)
    await db_session.commit()

    reporter_token = create_access_token({"sub": reporter.id})
    reporter_headers = {
        "Authorization": f"Bearer {reporter_token}",
        "X-Tenant-ID": tenant_id,
    }

    # Reporter CAN trigger research and generate content plan
    gen_res = await client.post(
        f"/api/v1/stories/{story.id}/content-plan",
        headers=reporter_headers,
    )
    assert gen_res.status_code == 201

    output_id = gen_res.json()["id"]

    # Reporter CANNOT accept AI output -> 403 Forbidden
    acc_res = await client.post(f"/api/v1/ai-outputs/{output_id}/accept", headers=reporter_headers)
    assert acc_res.status_code == 403
    assert "REVIEW_AI_CONTENT" in acc_res.json()["detail"]

    # Reporter CANNOT reject AI output -> 403 Forbidden
    rej_res = await client.post(
        f"/api/v1/ai-outputs/{output_id}/reject",
        json={"action": "REJECT", "rejection_reason": "Not good"},
        headers=reporter_headers,
    )
    assert rej_res.status_code == 403
    assert "REVIEW_AI_CONTENT" in rej_res.json()["detail"]
