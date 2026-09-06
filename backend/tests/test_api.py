"""End-to-end API behaviour: the accelerator demo path, and authorisation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/demo/session")
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def signup(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/signup",
        json={"email": email, "password": "a-sufficiently-long-password", "accept_privacy": True},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ============================================================ liveness


def test_health_and_capabilities_need_no_authentication(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    capabilities = client.get("/api/capabilities").json()
    assert capabilities["database"] == "sqlite"
    # With no keys configured, the degradations must be reported honestly.
    assert capabilities["llm_available"] is False
    assert any("language model" in d for d in capabilities["degradations"])


def test_security_headers_are_present_on_every_response(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Request-ID"]


# ====================================================== the demo journey


def test_the_full_demo_journey(seeded_client: TestClient) -> None:
    """The ninety-second accelerator story, executed."""
    client = seeded_client
    headers = auth_headers(client)

    # 1. A pre-filled fictional profile.
    profile = client.get("/api/profile", headers=headers).json()
    assert profile["confirmed"] is True
    assert profile["skills"]

    # 2. The Money Map appears.
    money_map = client.post("/api/money-map/refresh", headers=headers).json()
    assert money_map["opportunities"]
    assert money_map["best_next_move"] is not None
    assert money_map["goal_progress_ratio"] == 0.0, "no committed money yet"

    # 3. Opportunities span several categories.
    categories = {o["category"] for o in money_map["opportunities"]}
    assert len(categories) >= 5

    # 4. Transparent matching on one of them.
    opportunity_id = money_map["opportunities"][0]["id"]
    detail = client.get(f"/api/opportunities/{opportunity_id}", headers=headers).json()
    assert detail["match"]["components"]
    assert detail["what_we_dont_know"], "every card must state what it does not know"

    # 5. The Germany Check, with citations.
    assert detail["germany_check"]["considerations"]
    assert detail["germany_check"]["questions_to_check"]
    assert detail["germany_check"]["official_sources"]

    # 6. Save, then track through to won.
    application = client.post(
        f"/api/opportunities/{opportunity_id}/save", headers=headers
    ).json()
    assert application["status"] == "SAVED"
    assert application["checklist"]

    for target in ("APPLIED", "OFFERED"):
        response = client.post(
            f"/api/applications/{application['id']}/status",
            headers=headers,
            json={"status": target},
        )
        assert response.status_code == 200, response.text

    won = client.post(
        f"/api/applications/{application['id']}/status",
        headers=headers,
        json={
            "status": "WON",
            "outcome": {"amount_minor": 90_000, "period": "ONE_TIME", "hours_spent": 4},
        },
    )
    assert won.status_code == 200

    # 7. Money moves from potential to secured, and only then.
    after = client.get("/api/money-map", headers=headers).json()
    assert after["summary"]["secured_one_time_minor"] == 90_000
    assert after["summary"]["secured_count"] == 1

    # 8. Connect it to a goal.
    goal = client.post(
        "/api/goals",
        headers=headers,
        json={
            "goal_type": "EMERGENCY_FUND",
            "name": "Emergency fund",
            "target_minor": 600_000,
            "current_minor": 90_000,
            "monthly_contribution_minor": 20_000,
        },
    )
    assert goal.status_code == 201
    assert goal.json()["progress_ratio"] == pytest.approx(0.15)


def test_recording_a_win_requires_the_real_figure(seeded_client: TestClient) -> None:
    client = seeded_client
    headers = auth_headers(client)
    money_map = client.post("/api/money-map/refresh", headers=headers).json()
    opportunity_id = money_map["opportunities"][0]["id"]
    application = client.post(
        f"/api/opportunities/{opportunity_id}/save", headers=headers
    ).json()
    client.post(
        f"/api/applications/{application['id']}/status", headers=headers, json={"status": "APPLIED"}
    )
    response = client.post(
        f"/api/applications/{application['id']}/status", headers=headers, json={"status": "WON"}
    )
    assert response.status_code == 400
    assert "actually paid" in response.json()["detail"]


def test_an_illegal_transition_is_refused_with_the_legal_ones(
    seeded_client: TestClient,
) -> None:
    client = seeded_client
    headers = auth_headers(client)
    money_map = client.post("/api/money-map/refresh", headers=headers).json()
    application = client.post(
        f"/api/opportunities/{money_map['opportunities'][0]['id']}/save", headers=headers
    ).json()
    response = client.post(
        f"/api/applications/{application['id']}/status", headers=headers, json={"status": "WON"}
    )
    assert response.status_code == 409
    assert "Allowed from here" in response.json()["detail"]


# ============================================================ trust labels


def test_every_demo_opportunity_is_badged_and_unverified(
    seeded_client: TestClient,
) -> None:
    client = seeded_client
    headers = auth_headers(client)
    money_map = client.post("/api/money-map/refresh", headers=headers).json()
    demos = [o for o in money_map["opportunities"] if o["is_demo"]]
    assert demos
    for opportunity in demos:
        assert opportunity["trust"] == "DEMO"
        assert opportunity["compensation"]["verified"] is False


def test_curated_opportunities_state_unknown_compensation_honestly(
    seeded_client: TestClient,
) -> None:
    client = seeded_client
    headers = auth_headers(client)
    money_map = client.post("/api/money-map/refresh", headers=headers).json()
    curated = [o for o in money_map["opportunities"] if not o["is_demo"]]
    assert curated, "the curated dataset should produce at least one record"
    for opportunity in curated:
        assert opportunity["trust"] in {"SOURCE_BACKED", "VERIFIED"}
        if not opportunity["compensation"]["minor_min"]:
            assert opportunity["compensation"]["unknown_note"]


def test_diagnostics_account_for_what_was_dropped(seeded_client: TestClient) -> None:
    client = seeded_client
    headers = auth_headers(client)
    diagnostics = client.post("/api/money-map/refresh", headers=headers).json()["diagnostics"]
    assert diagnostics["considered"] >= diagnostics["returned"]
    assert diagnostics["live_search_used"] is False
    assert any("curated" in notice for notice in diagnostics["notices"])


# ========================================================== authorisation


def test_one_user_cannot_read_another_users_application(client: TestClient) -> None:
    alice = signup(client, "alice@example.com")
    bob = signup(client, "bob@example.com")

    # Alice needs a confirmed profile before she can discover anything.
    profile = client.get("/api/profile", headers=alice).json()
    profile.update(
        {
            "skills": [{"name": "Python", "level": "ADVANCED", "confirmed": True}],
            "hours_per_week": 5,
            "desired_additional_monthly_minor": 100_000,
        }
    )
    assert client.put("/api/profile", headers=alice, json=profile).status_code == 200
    assert client.post("/api/profile/confirm", headers=alice).status_code == 200

    money_map = client.post("/api/money-map/refresh", headers=alice).json()
    application = client.post(
        f"/api/opportunities/{money_map['opportunities'][0]['id']}/save", headers=alice
    ).json()

    assert client.get(f"/api/applications/{application['id']}", headers=alice).status_code == 200
    # Bob gets 404, not 403: the existence of the row is not his business.
    assert client.get(f"/api/applications/{application['id']}", headers=bob).status_code == 404


def test_protected_endpoints_refuse_anonymous_callers(client: TestClient) -> None:
    for method, path in (
        ("get", "/api/profile"),
        ("get", "/api/money-map"),
        ("post", "/api/money-map/refresh"),
        ("get", "/api/applications"),
        ("get", "/api/auth/export"),
        ("delete", "/api/auth/account"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 401, f"{method} {path}"


def test_a_forged_token_is_refused(client: TestClient) -> None:
    response = client.get("/api/profile", headers={"Authorization": "Bearer not.a.token"})
    assert response.status_code == 401


def test_discovery_refuses_an_unconfirmed_profile(client: TestClient) -> None:
    headers = signup(client, "unconfirmed@example.com")
    response = client.post("/api/money-map/refresh", headers=headers)
    assert response.status_code == 409
    assert "confirm your profile" in response.json()["detail"]


# ================================================================ privacy


def test_signup_requires_explicit_consent_and_records_it(client: TestClient) -> None:
    refused = client.post(
        "/api/auth/signup",
        json={"email": "n@example.com", "password": "long-enough-password", "accept_privacy": False},
    )
    assert refused.status_code == 400

    headers = signup(client, "consenting@example.com")
    consents = client.get("/api/profile/consents", headers=headers).json()
    assert any(c["purpose"] == "privacy_notice" for c in consents)


def test_signup_does_not_reveal_whether_an_email_is_registered(client: TestClient) -> None:
    signup(client, "taken@example.com")
    duplicate = client.post(
        "/api/auth/signup",
        json={"email": "taken@example.com", "password": "long-enough-password", "accept_privacy": True},
    )
    assert duplicate.status_code == 400
    assert "already" not in duplicate.json()["detail"].lower()
    assert "exists" not in duplicate.json()["detail"].lower()


def test_export_returns_real_data_and_never_a_credential(client: TestClient) -> None:
    headers = signup(client, "export@example.com")
    export = client.get("/api/auth/export", headers=headers).json()
    assert export["account"]["email"] == "export@example.com"
    assert "password_hash" not in export["account"]
    serialised = str(export)
    assert "argon2" not in serialised


def test_account_deletion_removes_every_personal_row(client: TestClient) -> None:
    from sqlalchemy import func, select

    from app.db.base import session_scope
    from app.db.models import AnalyticsEvent, AuditEvent, ConsentRecord, Profile, User

    headers = signup(client, "deleteme@example.com")
    user_id = client.get("/api/auth/me", headers=headers).json()["user_id"]

    assert client.delete("/api/auth/account", headers=headers).status_code == 204

    with session_scope() as session:
        assert session.get(User, user_id) is None
        for model in (Profile, ConsentRecord, AnalyticsEvent):
            count = session.execute(
                select(func.count()).select_from(model).where(model.user_id == user_id)
            ).scalar()
            assert count == 0, f"{model.__tablename__} still holds rows"
        # The audit record of the deletion deliberately survives, keyed by hash.
        audits = session.execute(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "account_deleted")
        ).scalar()
        assert audits == 1


def test_logout_revokes_the_refresh_token(client: TestClient) -> None:
    response = client.post(
        "/api/auth/signup",
        json={"email": "logout@example.com", "password": "long-enough-password", "accept_privacy": True},
    )
    tokens = response.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    refreshed = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 401


def test_a_refresh_token_cannot_be_reused(client: TestClient) -> None:
    response = client.post(
        "/api/auth/signup",
        json={"email": "rotate@example.com", "password": "long-enough-password", "accept_privacy": True},
    )
    original = response.json()["refresh_token"]
    assert client.post("/api/auth/refresh", json={"refresh_token": original}).status_code == 200
    assert client.post("/api/auth/refresh", json={"refresh_token": original}).status_code == 401


# =============================================================== KEEP/GROW


def test_a_tax_question_is_answered_with_citations_or_declined(
    seeded_client: TestClient,
) -> None:
    client = seeded_client
    headers = auth_headers(client)
    response = client.post(
        "/api/tax/ask", headers=headers, json={"question": "Do I need to register a Gewerbe?"}
    )
    body = response.json()
    if body["answered"]:
        assert body["citations"]
    else:
        assert body["refusal"]
    assert "Steuerberatung" in body["disclaimer"]


def test_the_legal_fact_list_shows_the_gaps(seeded_client: TestClient) -> None:
    facts = seeded_client.get("/api/tax/facts").json()
    assert facts
    unknown = [f for f in facts if f["status"] == "UNKNOWN"]
    assert unknown, "registry entries we could not populate must remain visible"


def test_the_projection_endpoint_labels_its_output_illustrative(client: TestClient) -> None:
    response = client.post(
        "/api/grow/project",
        json={
            "initial_minor": 0,
            "monthly_contribution_minor": 20_000,
            "annual_return": 0.05,
            "months": 60,
        },
    )
    assert "not a forecast" in response.json()["disclaimer"]


def test_an_absurd_return_assumption_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/grow/project",
        json={
            "initial_minor": 0,
            "monthly_contribution_minor": 100,
            "annual_return": 0.95,
            "months": 12,
        },
    )
    assert response.status_code == 422


def test_the_ownership_card_recommends_nothing(client: TestClient) -> None:
    assert client.get("/api/family/ownership").json()["recommended"] is None


# ============================================================= provenance


def test_provenance_lists_disabled_sources_too(client: TestClient) -> None:
    rows = client.get("/api/provenance").json()
    assert any(row["enabled"] is False for row in rows)
    for row in rows:
        assert row["access_basis"], f"{row['id']} has no recorded access basis"


def test_validation_errors_do_not_echo_the_submitted_value(client: TestClient) -> None:
    """The inputs here include CV text and tax questions."""
    canary = "SENSITIVE-CANARY-VALUE"
    response = client.post(
        "/api/auth/signup",
        json={"email": canary, "password": "x", "accept_privacy": True},
    )
    assert response.status_code == 422
    assert canary not in response.text
