"""Critical tenant-isolation and role-authorization tests."""

from __future__ import annotations

import pytest

from apps.api.models.base import UserRole


@pytest.mark.asyncio
async def test_org_a_cannot_see_org_b_drugs(test_client, test_org_factory, test_user_factory, test_drug_factory, auth_header) -> None:
    org_a = await test_org_factory(name="Org A", slug="org-a")
    org_b = await test_org_factory(name="Org B", slug="org-b")
    user_a = await test_user_factory(organization=org_a, role=UserRole.VIEWER, email="viewer-a@example.com")
    await test_drug_factory(organization=org_b, name="Org B Secret Drug")

    response = await test_client.get("/drugs", headers=auth_header(user_a))
    assert response.status_code == 200
    assert response.json()["data"]["items"] == []


@pytest.mark.asyncio
async def test_org_a_cannot_access_org_b_drug_by_id(test_client, test_org_factory, test_user_factory, test_drug_factory, auth_header) -> None:
    org_a = await test_org_factory(name="Org A2", slug="org-a2")
    org_b = await test_org_factory(name="Org B2", slug="org-b2")
    user_a = await test_user_factory(organization=org_a, role=UserRole.VIEWER, email="viewer-a2@example.com")
    drug_b = await test_drug_factory(organization=org_b, name="Org B2 Drug")

    response = await test_client.get(f"/drugs/{drug_b.id}", headers=auth_header(user_a))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_org_a_cannot_trigger_analysis_for_org_b_drug(test_client, test_org_factory, test_user_factory, test_drug_factory, auth_header) -> None:
    org_a = await test_org_factory(name="Org A3", slug="org-a3")
    org_b = await test_org_factory(name="Org B3", slug="org-b3")
    analyst_a = await test_user_factory(organization=org_a, role=UserRole.ANALYST, email="analyst-a@example.com")
    drug_b = await test_drug_factory(organization=org_b, name="Org B3 Drug")

    response = await test_client.post(f"/drugs/{drug_b.id}/analyze", headers=auth_header(analyst_a))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_role_viewer_cannot_create_drug(test_client, test_user_factory, auth_header) -> None:
    viewer = await test_user_factory(role=UserRole.VIEWER, email="viewer-create@example.com")

    response = await test_client.post(
        "/drugs",
        headers=auth_header(viewer),
        json={"name": "Unauthorized Viewer Drug", "indication": "Cardiology", "manufacturer": "RWE"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_role_analyst_cannot_delete_drug(test_client, test_user_factory, test_drug_factory, auth_header) -> None:
    analyst = await test_user_factory(role=UserRole.ANALYST, email="analyst-delete@example.com")
    drug = await test_drug_factory(name="Delete Guard Drug")

    response = await test_client.delete(f"/drugs/{drug.id}", headers=auth_header(analyst))
    assert response.status_code == 403
