"""The curated gate has to actually bite.

A validator nobody has seen fail is a validator nobody knows works. These tests
construct the exact mistake the rule exists to prevent - a plausible figure
typed onto a real programme - and assert that it is rejected.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from scripts.validate_curated import check_record

NOW = datetime.now(UTC)


def valid_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": "curated-example",
        "title": "A real programme",
        "organization": "A real institution",
        "category": "GRANT",
        "source_url": "https://example.org/programme",
        "last_verified_at": (NOW - timedelta(days=1)).isoformat(),
        "compensation_min_minor": None,
        "compensation_max_minor": None,
        "compensation_basis": "UNKNOWN",
        "compensation_period": "UNKNOWN",
        "compensation_verified": False,
    }
    record.update(overrides)
    return record


def test_a_record_with_no_published_figure_is_fine() -> None:
    """The common, correct case: the page states no amount, so neither do we."""
    assert check_record(valid_record(), "curated/example.json") == []


def test_an_invented_figure_is_rejected() -> None:
    """The failure this whole gate exists for."""
    problems = check_record(
        valid_record(
            compensation_min_minor=150_000,
            compensation_basis="PER_MONTH",
            compensation_period="PER_MONTH",
        ),
        "curated/example.json",
    )
    assert any("no source_excerpt" in problem for problem in problems)


def test_a_figure_absent_from_the_excerpt_is_rejected() -> None:
    """An excerpt that does not contain the number is not evidence for it."""
    problems = check_record(
        valid_record(
            compensation_min_minor=150_000,
            compensation_basis="PER_MONTH",
            compensation_period="PER_MONTH",
            source_excerpt="Die Foerderung betraegt bis zu 3.000 Euro monatlich.",
        ),
        "curated/example.json",
    )
    assert any("does not appear in source_excerpt" in problem for problem in problems)


def test_a_quoted_figure_is_accepted() -> None:
    """And the same figure, actually quoted, passes."""
    assert (
        check_record(
            valid_record(
                compensation_min_minor=300_000,
                compensation_basis="PER_MONTH",
                compensation_period="PER_MONTH",
                source_excerpt="Die Foerderung betraegt bis zu 3.000 Euro monatlich.",
            ),
            "curated/example.json",
        )
        == []
    )


def test_a_thousands_separator_does_not_defeat_the_check() -> None:
    """German pages write 1.500; the check must not care about separators."""
    assert (
        check_record(
            valid_record(
                compensation_min_minor=150_000,
                compensation_basis="PER_MONTH",
                compensation_period="PER_MONTH",
                source_excerpt="Das Stipendium betraegt 1.500 Euro pro Monat.",
            ),
            "curated/example.json",
        )
        == []
    )


def test_an_amount_with_unknown_basis_is_rejected() -> None:
    """An amount nothing can convert is worse than no amount."""
    problems = check_record(
        valid_record(
            compensation_min_minor=300_000,
            source_excerpt="Die Foerderung betraegt bis zu 3.000 Euro monatlich.",
        ),
        "curated/example.json",
    )
    assert any("compensation_basis is UNKNOWN" in problem for problem in problems)


def test_a_demo_record_cannot_hide_in_the_curated_directory() -> None:
    problems = check_record(valid_record(is_demo=True), "curated/example.json")
    assert any("do not belong in curated" in problem for problem in problems)


def test_verification_needs_a_date() -> None:
    problems = check_record(valid_record(last_verified_at=None), "curated/example.json")
    assert any("last_verified_at" in problem for problem in problems)


def test_a_future_verification_date_is_rejected() -> None:
    problems = check_record(
        valid_record(last_verified_at=(NOW + timedelta(days=2)).isoformat()),
        "curated/example.json",
    )
    assert any("in the future" in problem for problem in problems)


def test_compensation_verified_without_an_amount_is_rejected() -> None:
    problems = check_record(valid_record(compensation_verified=True), "curated/example.json")
    assert any("no amount is stated" in problem for problem in problems)
