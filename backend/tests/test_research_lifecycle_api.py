"""Integration and lifecycle tests for Phase 4 Research and AI Content APIs."""

import pytest

from app.db.models.story import Story


@pytest.mark.asyncio
async def test_research_job_trigger_and_brief_retrieval(client, seeded_environment, db_session):
    """Verify research job execution produces accessible evidence, claims, and brief."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    user_id = env["user_news9"].id
    headers = {
        "Authorization": f"Bearer {env['token_news9']}",
        "X-Tenant-ID": tenant_id,
    }

    # Create a test story
    story = Story(
        tenant_id=tenant_id,
        title="Gorakhpur Smart City Water Drainage Upgrade",
        slug="gorakhpur-drainage-upgrade",
        summary="District administration initiates comprehensive storm drainage overhaul.",
        created_by_user_id=user_id,
    )
    db_session.add(story)
    await db_session.commit()

    # 1. Trigger research
    res = await client.post(
        f"/api/v1/stories/{story.id}/research",
        json={"query_topic": "Gorakhpur storm water drainage overhaul"},
        headers=headers,
    )
    assert res.status_code == 201
    job_data = res.json()
    assert job_data["status"] == "COMPLETED"
    job_id = job_data["id"]

    # 2. Get evidence items
    ev_res = await client.get(f"/api/v1/research/{job_id}/evidence", headers=headers)
    assert ev_res.status_code == 200
    evidence = ev_res.json()
    assert len(evidence) > 0
    assert len(evidence[0]["evidence_snippet"]) <= 750

    # 3. Get claims
    cl_res = await client.get(f"/api/v1/research/{job_id}/claims", headers=headers)
    assert cl_res.status_code == 200
    claims = cl_res.json()
    assert len(claims) > 0

    # 4. Get 5W1H brief
    br_res = await client.get(f"/api/v1/research/{job_id}/brief", headers=headers)
    assert br_res.status_code == 200
    brief = br_res.json()
    assert brief["what_happened"] != ""
    assert len(brief["confirmed_facts"]) > 0


@pytest.mark.asyncio
async def test_ai_content_generations_and_human_review_gate(client, seeded_environment, db_session):
    """Verify AI output generation, versioning, accept, reject (with mandatory reason), and edit."""
    env = seeded_environment
    tenant_id = env["tenant_news9"].id
    user_id = env["user_news9"].id
    headers = {
        "Authorization": f"Bearer {env['token_news9']}",
        "X-Tenant-ID": tenant_id,
    }

    story = Story(
        tenant_id=tenant_id,
        title="Regional Solar Grid Expansion 2026",
        slug="regional-solar-grid-2026",
        summary="State awards 500MW solar contracts across eastern districts.",
        created_by_user_id=user_id,
    )
    db_session.add(story)
    await db_session.commit()

    # 1. Generate Content Plan
    cp_res = await client.post(
        f"/api/v1/stories/{story.id}/content-plan",
        json={"editorial_angle": "Renewable infrastructure economics"},
        headers=headers,
    )
    assert cp_res.status_code == 201
    cp_data = cp_res.json()
    assert cp_data["output_type"] == "CONTENT_PLAN"
    assert cp_data["version_number"] == 1
    assert cp_data["status"] == "GENERATED"
    output_id = cp_data["id"]

    # 2. Human Review: Accept
    acc_res = await client.post(f"/api/v1/ai-outputs/{output_id}/accept", headers=headers)
    assert acc_res.status_code == 200
    assert acc_res.json()["status"] == "ACCEPTED"

    # 3. Generate Headlines (Version 1)
    hl_res1 = await client.post(f"/api/v1/stories/{story.id}/headlines", headers=headers)
    assert hl_res1.status_code == 201
    assert hl_res1.json()["version_number"] == 1
    hl_id1 = hl_res1.json()["id"]

    # 4. Generate Headlines (Version 2 - append-only versioning check)
    hl_res2 = await client.post(f"/api/v1/stories/{story.id}/headlines", headers=headers)
    assert hl_res2.status_code == 201
    assert hl_res2.json()["version_number"] == 2

    # 5. Human Review: Reject without reason should fail with 422
    rej_fail = await client.post(
        f"/api/v1/ai-outputs/{hl_id1}/reject",
        json={"action": "REJECT", "rejection_reason": ""},
        headers=headers,
    )
    assert rej_fail.status_code == 422

    # 6. Human Review: Reject with valid reason
    rej_pass = await client.post(
        f"/api/v1/ai-outputs/{hl_id1}/reject",
        json={"action": "REJECT", "rejection_reason": "Tone is overly casual for broadcast desk"},
        headers=headers,
    )
    assert rej_pass.status_code == 200
    assert rej_pass.json()["status"] == "REJECTED"
    assert rej_pass.json()["rejection_reason"] == "Tone is overly casual for broadcast desk"

    # 7. Generate Broadcast Script
    sc_res = await client.post(
        f"/api/v1/stories/{story.id}/script",
        json={"script_format": "TV_NEWS_RUNDOWN", "target_duration_seconds": 60},
        headers=headers,
    )
    assert sc_res.status_code == 201
    sc_data = sc_res.json()
    assert sc_data["output_type"] == "SCRIPT"
    script_id = sc_data["id"]

    # 8. Human Review: In-place edit
    edited_content = sc_data["content"]
    edited_content["title"] = "News 9 Lead Story: Solar Expansion"
    edit_res = await client.post(
        f"/api/v1/ai-outputs/{script_id}/edit",
        json={"content": edited_content},
        headers=headers,
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["status"] == "EDITED"
    assert edit_res.json()["content"]["title"] == "News 9 Lead Story: Solar Expansion"
