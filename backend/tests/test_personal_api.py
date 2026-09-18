"""The personal page over the wire.

The interesting assertions are the ones about what the API refuses to return:
no combined income total, no tax effect, no inferred household. Those are the
promises that would be cheapest to break by accident.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/demo/session")
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def fresh_headers(client: TestClient, email: str) -> dict[str, str]:
    """A real, empty account.

    The demo session is deliberately seeded with a money picture so the
    personal page demonstrates something. Tests about empty-state behaviour
    need an account that is actually empty, which is what signing up gives.
    """
    response = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "a-sufficiently-long-password",
            "accept_privacy": True,
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# --------------------------------------------------------------- access


def test_the_personal_page_needs_an_account(client: TestClient) -> None:
    for path in ("/api/personal/overview", "/api/personal/income", "/api/personal/expenses"):
        assert client.get(path).status_code == 401


def test_one_account_cannot_delete_another_accounts_record(client: TestClient) -> None:
    mine = auth_headers(client)
    created = client.post(
        "/api/personal/income",
        headers=mine,
        json={"label": "Salary", "amount_minor": 300_000, "basis": "NET"},
    )
    assert created.status_code == 201

    theirs = auth_headers(client)
    response = client.delete(f"/api/personal/income/{created.json()['id']}", headers=theirs)
    # 404 rather than 403: whether an id exists is not something to leak.
    assert response.status_code == 404


# ------------------------------------------------------ baseline income


def test_a_recorded_income_keeps_the_basis_it_was_given(client: TestClient) -> None:
    headers = auth_headers(client)
    response = client.post(
        "/api/personal/income",
        headers=headers,
        json={"label": "Main job", "amount_minor": 285_000, "basis": "NET"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["basis"] == "NET"
    assert body["amount_minor"] == 285_000
    assert body["monthly_minor"] == 285_000


def test_gross_and_net_are_reported_separately_and_never_summed(client: TestClient) -> None:
    headers = fresh_headers(client, "grossnet@example.com")
    client.post(
        "/api/personal/income",
        headers=headers,
        json={"label": "Salary", "amount_minor": 300_000, "basis": "NET"},
    )
    client.post(
        "/api/personal/income",
        headers=headers,
        json={"label": "Retainer", "amount_minor": 100_000, "basis": "GROSS"},
    )

    baseline = client.get("/api/personal/overview", headers=headers).json()["baseline"]
    assert baseline["net_monthly_minor"] == 300_000
    assert baseline["gross_monthly_minor"] == 100_000
    # No combined figure exists on the wire, because no honest one exists.
    assert "total_monthly_minor" not in baseline
    assert any("not added together" in note for note in baseline["notes"])


def test_a_one_off_payment_stays_out_of_the_monthly_totals(client: TestClient) -> None:
    headers = fresh_headers(client, "oneoff@example.com")
    client.post(
        "/api/personal/income",
        headers=headers,
        json={
            "label": "Bonus",
            "amount_minor": 200_000,
            "basis": "NET",
            "period": "ONE_TIME",
        },
    )
    baseline = client.get("/api/personal/overview", headers=headers).json()["baseline"]
    assert baseline["net_monthly_minor"] == 0
    assert baseline["one_off_minor"] == 200_000
    assert baseline["entries"][0]["monthly_minor"] is None


def test_only_one_income_can_be_primary(client: TestClient) -> None:
    headers = auth_headers(client)
    client.post(
        "/api/personal/income",
        headers=headers,
        json={"label": "First", "amount_minor": 100_000, "is_primary": True},
    )
    client.post(
        "/api/personal/income",
        headers=headers,
        json={"label": "Second", "amount_minor": 200_000, "is_primary": True},
    )
    entries = client.get("/api/personal/income", headers=headers).json()
    assert sum(1 for entry in entries if entry["is_primary"]) == 1


# ------------------------------------------------------------- expenses


def test_expenses_are_totalled_without_any_tax_effect(client: TestClient) -> None:
    headers = fresh_headers(client, "expenses@example.com")
    for amount, category in ((12_000, "EQUIPMENT"), (3_500, "TRAVEL")):
        response = client.post(
            "/api/personal/expenses",
            headers=headers,
            json={
                "label": "A cost",
                "amount_minor": amount,
                "category": category,
                "incurred_on": "2026-02-10",
            },
        )
        assert response.status_code == 201

    summary = client.get("/api/personal/overview", headers=headers).json()["expenses"]
    assert summary["total_minor"] == 15_500
    assert summary["count"] == 2
    # The boundary, checked on the wire rather than only in the type.
    for forbidden in ("tax_saved_minor", "tax_rate", "deductible_minor", "refund_minor"):
        assert forbidden not in summary
    assert "not Steuerberatung" in summary["disclaimer"]


def test_recorded_costs_produce_questions_not_verdicts(client: TestClient) -> None:
    headers = auth_headers(client)
    client.post(
        "/api/personal/expenses",
        headers=headers,
        json={
            "label": "Laptop",
            "amount_minor": 150_000,
            "category": "EQUIPMENT",
            "incurred_on": "2026-02-10",
            "partly_private": "YES",
        },
    )
    summary = client.get("/api/personal/overview", headers=headers).json()["expenses"]
    asked = " ".join(summary["questions_to_check"])
    assert "private share" in asked
    # A percentage would be the product deciding the split, which it does not.
    assert "%" not in asked
    assert "deductible" not in asked.lower()


def test_an_expense_cannot_belong_to_two_parents(client: TestClient) -> None:
    headers = auth_headers(client)
    response = client.post(
        "/api/personal/expenses",
        headers=headers,
        json={
            "label": "Ambiguous",
            "amount_minor": 1_000,
            "incurred_on": "2026-02-10",
            "income_stream_id": "a",
            "application_id": "b",
        },
    )
    assert response.status_code == 422


# ------------------------------------------------------------ household


def test_the_household_is_unknown_until_the_user_says_otherwise(client: TestClient) -> None:
    headers = auth_headers(client)
    household = client.get("/api/personal/overview", headers=headers).json()["household"]
    assert household["has_children"] == "UNKNOWN"
    assert household["disclosed"] is False
    assert household["children"] == []


def test_disclosing_children_adds_the_questions_it_raises(seeded_client: TestClient) -> None:
    client = seeded_client
    headers = auth_headers(client)
    response = client.put(
        "/api/personal/household",
        headers=headers,
        json={
            "has_children": "YES",
            "children": [{"label": "Eldest", "age_years": 9}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["disclosed"] is True

    overview = client.get("/api/personal/overview", headers=headers).json()
    asked = " ".join(overview["questions_to_check"]).lower()
    assert "child" in asked
    # § 32 EStG is quoted, and no entitlement is computed from it.
    assert any(fact["id"] == "de_kinderfreibetrag" for fact in overview["facts"])
    for forbidden in ("you will receive", "you are entitled", "your allowance is"):
        assert forbidden not in asked


def test_a_child_cannot_be_recorded_alongside_no_children(client: TestClient) -> None:
    headers = auth_headers(client)
    response = client.put(
        "/api/personal/household",
        headers=headers,
        json={"has_children": "NO", "children": [{"label": "Eldest", "age_years": 9}]},
    )
    assert response.status_code == 422


def test_every_cited_fact_carries_a_source_and_a_status(seeded_client: TestClient) -> None:
    client = seeded_client
    headers = auth_headers(client)
    client.put("/api/personal/household", headers=headers, json={"has_children": "YES"})
    for fact in client.get("/api/personal/overview", headers=headers).json()["facts"]:
        assert fact["source_url"]
        assert fact["status"]
        assert fact["last_verified_at"]


# ------------------------------------------------------------- overview


def test_the_uplift_is_none_without_a_baseline(client: TestClient) -> None:
    headers = fresh_headers(client, "uplift@example.com")
    assert client.get("/api/personal/overview", headers=headers).json()["uplift_ratio"] is None


def test_the_overview_never_states_a_tax_position(client: TestClient) -> None:
    headers = auth_headers(client)
    body = client.get("/api/personal/overview", headers=headers).json()
    for forbidden in ("tax_owed_minor", "tax_saved_minor", "net_after_tax_minor", "refund_minor"):
        assert forbidden not in body
    assert "does not calculate tax" in body["disclaimer"]


def test_with_no_corpus_nothing_is_cited_and_nothing_is_invented(client: TestClient) -> None:
    """The designed degradation: an empty corpus removes claims, not the page."""
    headers = auth_headers(client)
    client.put("/api/personal/household", headers=headers, json={"has_children": "YES"})
    overview = client.get("/api/personal/overview", headers=headers).json()

    assert overview["facts"] == []
    # The question survives without the citation, because asking it costs
    # nothing and answering it from memory would cost everything.
    assert any("children" in question.lower() for question in overview["questions_to_check"])


# ------------------------------------------- money you may be losing


def test_the_leaks_endpoint_needs_an_account(client: TestClient) -> None:
    assert client.get("/api/personal/leaks").status_code == 401


def test_a_fresh_account_is_told_only_what_it_can_act_on(
    seeded_client: TestClient,
) -> None:
    """No filler. A demo profile has a benefit status of unknown, so the one
    finding it gets is the prompt to say - not a list of generic tax tips."""
    client = seeded_client
    headers = auth_headers(client)
    body = client.get("/api/personal/leaks", headers=headers).json()

    assert body["total"] == len(body["leaks"])
    for leak in body["leaks"]:
        # Every finding says what in the user's data triggered it.
        assert leak["why_this_applies"]
        assert leak["what_to_check"]
    # No euro total, ever.
    assert "total_minor" not in body
    assert "saving_minor" not in body
    assert "Steuerberatung" in body["disclaimer"]
    assert "money is owed to you" in body["disclaimer"]


def test_recording_income_raises_the_missing_costs_finding(
    seeded_client: TestClient,
) -> None:
    client = seeded_client
    headers = fresh_headers(client, "costs@example.com")
    client.post(
        "/api/personal/income",
        headers=headers,
        json={"label": "Main job", "amount_minor": 285_000, "basis": "NET"},
    )
    ids = {leak["id"] for leak in client.get("/api/personal/leaks", headers=headers).json()["leaks"]}
    assert "no_costs_recorded" in ids


def test_a_quoted_ceiling_is_labelled_as_the_statutes_figure(
    seeded_client: TestClient,
) -> None:
    client = seeded_client
    headers = auth_headers(client)
    client.put("/api/personal/household", headers=headers, json={"has_children": "YES"})
    body = client.get("/api/personal/leaks", headers=headers).json()

    for leak in body["leaks"]:
        if leak["stated_amount_minor"] is not None:
            # A figure may only appear alongside a note saying whose figure it
            # is, and a source backing it.
            assert leak["amount_note"]
            assert leak["fact_ids"]


# ------------------------------------------------------- A and B


def test_the_band_starts_from_the_profile(client: TestClient) -> None:
    headers = auth_headers(client)
    body = client.get("/api/personal/targets", headers=headers).json()
    # The demo profile earns 2,850 net and wants 1,500 more.
    assert body["current_monthly_minor"] == 285_000
    assert body["target_monthly_minor"] == 435_000
    assert body["additional_needed_minor"] == 150_000
    assert body["target_reached"] is False


def test_raising_what_you_earn_leaves_the_target_alone(client: TestClient) -> None:
    """The reason A and B are sent as a pair.

    Someone who gets a pay rise has not thereby raised their ambition, and the
    band must not decide that they have.
    """
    headers = auth_headers(client)
    client.put(
        "/api/personal/targets",
        headers=headers,
        json={"current_monthly_minor": 200_000, "target_monthly_minor": 400_000},
    )
    body = client.put(
        "/api/personal/targets",
        headers=headers,
        json={"current_monthly_minor": 250_000, "target_monthly_minor": 400_000},
    ).json()

    assert body["target_monthly_minor"] == 400_000
    assert body["additional_needed_minor"] == 150_000


def test_a_target_below_the_current_income_is_kept_not_rewritten(
    client: TestClient,
) -> None:
    """The bug this pair of fields exists to prevent.

    Setting a target you have already passed used to silently move the target
    up to match the income. The product does not restate a user's own figure.
    """
    headers = auth_headers(client)
    body = client.put(
        "/api/personal/targets",
        headers=headers,
        json={"current_monthly_minor": 285_000, "target_monthly_minor": 200_000},
    ).json()

    assert body["target_monthly_minor"] == 200_000
    # Nothing to find, but the product does not ask anyone to earn less.
    assert body["additional_needed_minor"] == 0
    assert body["target_reached"] is True

    # And it survives a reload rather than being derived away.
    reread = client.get("/api/personal/targets", headers=headers).json()
    assert reread["target_monthly_minor"] == 200_000


def test_setting_the_band_creates_a_baseline_entry_you_can_recognise(
    client: TestClient,
) -> None:
    headers = auth_headers(client)
    client.delete(
        f"/api/personal/income/{client.get('/api/personal/income', headers=headers).json()[0]['id']}",
        headers=headers,
    )
    client.put(
        "/api/personal/targets",
        headers=headers,
        json={"current_monthly_minor": 180_000, "target_monthly_minor": 300_000},
    )
    entries = client.get("/api/personal/income", headers=headers).json()
    assert len(entries) == 1
    assert entries[0]["amount_minor"] == 180_000
    # Named, not a mystery row on the personal page.
    assert entries[0]["label"] == "Current income"


# --------------------------------------------- bank statement import

SPARKASSE_CSV = (
    "Auftragskonto;Buchungstag;Valutadatum;Buchungstext;Verwendungszweck;"
    "Beguenstigter/Zahlungspflichtiger;Kontonummer/IBAN;BIC (SWIFT-Code);Betrag;Waehrung;Info\n"
    "DE12;04.09.2026;04.09.2026;LASTSCHRIFT;Monatsbeitrag;GitHub Inc;DE99;XX;-8,00;EUR;Umsatz\n"
    "DE12;05.09.2026;05.09.2026;LASTSCHRIFT;Wocheneinkauf;REWE Markt;DE98;XX;-62,45;EUR;Umsatz\n"
    "DE12;06.09.2026;06.09.2026;GUTSCHRIFT;Honorar;Hansa Logistik;DE97;XX;1.250,00;EUR;Umsatz\n"
)


def upload(client: TestClient, headers: dict[str, str], name: str, body: bytes):
    return client.post(
        "/api/personal/statements/preview",
        headers=headers,
        files={"file": (name, body, "text/csv")},
    )


def test_previewing_a_statement_imports_nothing(client: TestClient) -> None:
    headers = fresh_headers(client, "statement@example.com")
    before = client.get("/api/personal/expenses", headers=headers).json()

    body = upload(client, headers, "umsaetze.csv", SPARKASSE_CSV.encode("utf-8")).json()
    assert body["total_rows"] == 3
    assert body["outgoing_rows"] == 2
    assert body["suggested_rows"] == 1
    assert "Nothing has been imported" in body["note"]

    after = client.get("/api/personal/expenses", headers=headers).json()
    assert after == before


def test_private_spending_is_offered_but_not_suggested(client: TestClient) -> None:
    """The line that keeps this from filing groceries as a business cost."""
    headers = fresh_headers(client, "groceries@example.com")
    rows = upload(client, headers, "umsaetze.csv", SPARKASSE_CSV.encode("utf-8")).json()["rows"]

    groceries = next(r for r in rows if r["row"]["counterparty"] == "REWE Markt")
    assert groceries["suggested"] is False
    assert groceries["category"] is None

    software = next(r for r in rows if r["row"]["counterparty"] == "GitHub Inc")
    assert software["suggested"] is True
    assert software["category"] == "SOFTWARE_AND_SUBSCRIPTIONS"
    # A suggestion states what produced it, so it can be argued with.
    assert "github" in software["reason"]


def test_an_unsupported_file_is_refused_with_a_reason(client: TestClient) -> None:
    headers = fresh_headers(client, "pdfstatement@example.com")
    response = upload(client, headers, "screenshot.png", b"not a statement")
    assert response.status_code == 400
    assert "checked against a balance" in response.json()["detail"]


def test_an_unreadable_pdf_fails_rather_than_returning_nothing(
    client: TestClient,
) -> None:
    """A PDF is accepted now, but one that yields no lines is still an error."""
    headers = fresh_headers(client, "badpdf@example.com")
    response = upload(client, headers, "auszug.pdf", b"%PDF-1.7 not really a pdf")
    assert response.status_code == 400


def test_only_the_selected_lines_are_recorded(client: TestClient) -> None:
    headers = fresh_headers(client, "import@example.com")
    response = client.post(
        "/api/personal/statements/import",
        headers=headers,
        json={
            "items": [
                {
                    "label": "GitHub Inc",
                    "amount_minor": 800,
                    "category": "SOFTWARE_AND_SUBSCRIPTIONS",
                    "incurred_on": "2026-09-04",
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 1

    expenses = client.get("/api/personal/expenses", headers=headers).json()
    assert len(expenses) == 1
    assert expenses[0]["amount_minor"] == 800
    # A bank line proves payment, not that an invoice exists, so the receipt
    # question stays open rather than being answered by the import.
    assert expenses[0]["has_receipt"] == "UNKNOWN"


def test_importing_needs_an_account(client: TestClient) -> None:
    assert client.post("/api/personal/statements/import", json={"items": []}).status_code == 401
