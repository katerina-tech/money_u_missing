"""The gate on the curated dataset.

The product's central promise is that a real opportunity never carries an
invented figure. Up to now that promise was kept by care alone. This turns it
into a rule that fails the build.

Every record under ``backend/curated/`` must satisfy all of the following, and
the reasoning for each is the reason it is checked rather than trusted:

1. **A source URL.** A record with no URL cannot be checked by anyone, which
   makes it indistinguishable from something we made up.
2. **A retrieval date, in the past.** "Verified" with no date is a claim about
   nothing; a date in the future is a clerical error that would make a stale
   record look fresh forever.
3. **No demo flag.** ``curated/`` is the real dataset. A demo record here would
   inherit the trust of the real ones.
4. **Compensation must be quoted.** If any compensation field is non-null, the
   record must carry ``source_excerpt`` - the text from the page - and the
   digits of the figure must appear in it. This is the rule that matters: it
   makes it impossible to type a plausible salary into a real programme without
   also producing the sentence that says so.
5. **A basis and period whenever there is an amount.** An amount with
   ``UNKNOWN`` basis cannot be compared with anything, and the Money Map would
   have to guess how to convert it.
6. **Unique ids**, so two records cannot silently overwrite each other.

Run with:  python -m scripts.validate_curated
Exit code 1 on any failure. Wired into `check`.
"""

# A validator talks to a person at a terminal; printing is the interface.

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent
CURATED_DIR = BACKEND / "curated"

REQUIRED_FIELDS = ("id", "title", "organization", "category", "source_url")

COMPENSATION_FIELDS = ("compensation_min_minor", "compensation_max_minor")


def _digits(minor: int) -> list[str]:
    """The ways a minor-unit amount could legibly appear on a page.

    ``150000`` minor is 1500 euro, which a page may print as "1500", "1.500"
    or "1 500". All three collapse to the same digit run once separators are
    stripped, so the excerpt is compared with separators removed.
    """
    whole, remainder = divmod(abs(minor), 100)
    forms = [str(whole)]
    if remainder:
        forms.append(f"{whole}{remainder:02d}")
    return forms


def _normalise(text: str) -> str:
    """Strip thousands separators so "1.500" and "1500" compare equal."""
    # The escape rather than the literal character: German pages use a
    # non-breaking space as a thousands separator, and a literal one here is
    # invisible to the next reader.
    return re.sub(r"[.\s\u00a0',]", "", text)


def check_record(record: dict[str, Any], where: str) -> list[str]:
    problems: list[str] = []

    def fail(message: str) -> None:
        problems.append(f"{where}: {message}")

    for field in REQUIRED_FIELDS:
        if not record.get(field):
            fail(f"missing required field {field!r}")

    if record.get("is_demo"):
        fail("is_demo is true - demo records do not belong in curated/")

    url = record.get("source_url") or ""
    if url and not url.startswith("https://"):
        fail(f"source_url is not https: {url!r}")

    raw_verified = record.get("last_verified_at")
    if not raw_verified:
        fail("missing last_verified_at - a verified record must say when")
    else:
        try:
            verified = datetime.fromisoformat(str(raw_verified))
        except ValueError:
            fail(f"last_verified_at is not an ISO timestamp: {raw_verified!r}")
        else:
            if verified.tzinfo is None:
                verified = verified.replace(tzinfo=UTC)
            if verified > datetime.now(UTC):
                fail("last_verified_at is in the future")

    # --------------------------------------------- the rule that matters
    amounts = [record.get(field) for field in COMPENSATION_FIELDS]
    stated = [value for value in amounts if value is not None]

    if stated:
        excerpt = record.get("source_excerpt")
        if not excerpt:
            fail(
                "states compensation but carries no source_excerpt. A figure on a "
                "real opportunity must be quoted from the page that published it."
            )
        else:
            haystack = _normalise(str(excerpt))
            for field, value in zip(COMPENSATION_FIELDS, amounts, strict=True):
                if value is None:
                    continue
                if not any(form in haystack for form in _digits(int(value))):
                    fail(
                        f"{field} is {int(value) / 100:.2f} but that figure does not "
                        f"appear in source_excerpt. Either it was not published, in "
                        f"which case the field must be null, or the excerpt is wrong."
                    )

        if record.get("compensation_basis", "UNKNOWN") == "UNKNOWN":
            fail("states an amount but compensation_basis is UNKNOWN - nothing can compare it")
        if record.get("compensation_period", "UNKNOWN") == "UNKNOWN":
            fail("states an amount but compensation_period is UNKNOWN")

    elif record.get("compensation_verified"):
        fail("compensation_verified is true but no amount is stated")

    return problems


def main() -> int:
    if not CURATED_DIR.is_dir():
        print(f"  No curated directory at {CURATED_DIR}. Nothing to check.")
        return 0

    paths = sorted(CURATED_DIR.glob("*.json"))
    if not paths:
        print(f"  No curated records in {CURATED_DIR}.")
        return 0

    problems: list[str] = []
    seen: dict[str, str] = {}

    for path in paths:
        where = f"curated/{path.name}"
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            problems.append(f"{where}: not valid JSON - {error}")
            continue
        if not isinstance(record, dict):
            problems.append(f"{where}: expected an object, found {type(record).__name__}")
            continue

        problems.extend(check_record(record, where))

        identifier = str(record.get("id", ""))
        if identifier:
            if identifier in seen:
                problems.append(f"{where}: id {identifier!r} already used by {seen[identifier]}")
            else:
                seen[identifier] = where

    if problems:
        print(f"\n  {len(problems)} problem(s) in the curated dataset:\n", file=sys.stderr)
        for problem in problems:
            print(f"    - {problem}", file=sys.stderr)
        print(file=sys.stderr)
        return 1

    quoted = sum(1 for path in paths if "source_excerpt" in path.read_text(encoding="utf-8"))
    print(f"  {len(paths)} curated record(s) valid. {quoted} carry a quoted source excerpt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
