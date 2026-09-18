"""Reading a bank statement the user exported themselves.

**Why a file and not a connection.** Talking to Sparkasse directly means either
a BaFin AISP permission or a licensed aggregator, and it means holding somebody
else's banking credentials. `docs/ROADMAP.md` declines bank integration for
exactly that reason. An exported statement needs none of it: the user presses a
button in their own online banking, and the file arrives with no credential
ever reaching this product. It is also what the analysis actually calls for -
three to twelve months of history, which a live connection would not give you
any faster.

**Two formats, both produced by Sparkasse's own export.** CAMT.053 XML, which
is the ISO 20022 standard and unambiguous, and the CSV-CAMT variant, which is
what most people click. Both are parsed here into the same rows.

**Nothing is imported.** This module *proposes*. Every row comes back with the
amount exactly as the bank recorded it, a suggested category where a rule
matched, and the matched word as the reason - so a suggestion can be argued
with rather than merely accepted. The user confirms what is theirs, and the
default for anything unmatched is "do not import".

That default matters more than it looks. This product's expense categories are
*business* costs, incurred in order to earn. A personal statement is mostly
groceries and rent, and quietly filing those as business expenses would produce
a total the user would then have to defend to a Finanzamt. So the rules below
are deliberately narrow: they fire on things that are plausibly work-related
and stay silent otherwise.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ExpenseCategory

#: How much of a statement we will read in one go. Twelve months of a busy
#: account sits far below this; a file above it is not a statement.
MAX_ROWS = 5_000


class StatementRowError(ValueError):
    """The file is not a statement this module can read."""


class StatementRow(BaseModel):
    """One booked line, as the bank recorded it.

    Nothing here is computed. The amount is the bank's, the date is the bank's,
    and the text is the bank's.
    """

    model_config = ConfigDict(extra="forbid")

    booked_on: date
    #: Integer cents, negative for money leaving the account. The sign is the
    #: bank's statement of direction and is never flipped to make a total work.
    amount_minor: int
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    #: Counterparty, where the file names one.
    counterparty: str | None = None
    #: The reference line. This is what the category rules read.
    reference: str = ""

    @property
    def is_outgoing(self) -> bool:
        return self.amount_minor < 0


class SuggestedExpense(BaseModel):
    """A row with a proposal attached. Still not an expense.

    ``category`` is a suggestion and ``reason`` says what produced it, so the
    user can disagree with a specific word rather than with a black box.
    ``suggested`` is false for everything the rules did not recognise, which is
    most of a personal statement and is the correct default.
    """

    model_config = ConfigDict(extra="forbid")

    row: StatementRow
    suggested: bool = False
    category: ExpenseCategory | None = None
    #: The word that matched, quoted back. Empty when nothing matched.
    reason: str = ""


class StatementPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[SuggestedExpense] = Field(default_factory=list)
    #: Counts, so the user can see the shape of the file before reading it all.
    total_rows: int = 0
    outgoing_rows: int = 0
    suggested_rows: int = 0
    currency: str = "EUR"
    note: str = (
        "Nothing has been imported. These are the lines your bank recorded; "
        "amounts and dates are exactly as exported. A category is only ever "
        "suggested - most of a personal statement is not a business cost, and "
        "this product does not decide which lines are."
    )


# ------------------------------------------------------------- category rules

#: Deliberately narrow. Each entry is (category, words). A rule fires only on a
#: whole word, and only for money going *out*. Anything not listed here is left
#: for the user, which is the right answer for rent, groceries and everything
#: else on a personal account.
_RULES: tuple[tuple[ExpenseCategory, tuple[str, ...]], ...] = (
    (
        ExpenseCategory.SOFTWARE_AND_SUBSCRIPTIONS,
        ("github", "jetbrains", "adobe", "figma", "notion", "slack", "atlassian",
         "microsoft 365", "google workspace", "openai", "anthropic", "aws", "hetzner",
         "digitalocean", "netlify", "vercel"),
    ),
    (
        ExpenseCategory.WORKSPACE,
        ("coworking", "wework", "mindspace", "betahaus", "impact hub"),
    ),
    (
        ExpenseCategory.PROFESSIONAL_DEVELOPMENT,
        ("udemy", "coursera", "konferenz", "conference", "seminar", "weiterbildung",
         "fortbildung", "workshop"),
    ),
    (
        ExpenseCategory.PROFESSIONAL_SERVICES,
        ("steuerberat", "rechtsanwalt", "notar", "buchhaltung", "lexoffice", "sevdesk"),
    ),
    (
        ExpenseCategory.TRAVEL,
        ("deutsche bahn", "db vertrieb", "bahn.de", "flixbus", "lufthansa", "eurowings"),
    ),
    (
        ExpenseCategory.COMMUNICATION,
        ("telekom", "vodafone", "o2", "1und1", "1&1"),
    ),
    (
        ExpenseCategory.FEES_AND_CHARGES,
        ("kontofuehrung", "kontoführung", "kontogebuehr", "entgelt", "ihk", "handelskammer"),
    ),
)


def suggest_category(row: StatementRow) -> tuple[ExpenseCategory | None, str]:
    """A category and the word that produced it, or nothing at all.

    Money coming *in* is never suggested as a cost. Beyond that the rules only
    recognise names; they do not reason about what a payment was for.
    """
    if not row.is_outgoing:
        return None, ""

    haystack = f"{row.counterparty or ''} {row.reference}".lower()
    for category, words in _RULES:
        for word in words:
            if re.search(rf"(?<![\w&.]){re.escape(word)}(?![\w&])", haystack):
                return category, word
    return None, ""


# ----------------------------------------------------------------- parsing


def _money_to_minor(raw: str) -> int:
    """German decimal notation into integer cents.

    "1.234,56" is one thousand two hundred, not one point two. Getting this
    backwards would be a silent factor-of-a-thousand error in somebody's
    records, so the separators are handled explicitly rather than by float().
    """
    cleaned = raw.strip().replace("\xa0", "").replace(" ", "")
    if not cleaned:
        raise StatementRowError("empty amount")
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return int((Decimal(cleaned) * 100).to_integral_value())
    except (InvalidOperation, ValueError) as error:
        raise StatementRowError(f"cannot read the amount {raw!r}") from error


def _parse_date(raw: str) -> date:
    """Sparkasse writes DD.MM.YY or DD.MM.YYYY."""
    text = raw.strip()
    for pattern in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise StatementRowError(f"cannot read the date {raw!r}")


def _decode(data: bytes) -> str:
    """Sparkasse exports are usually Windows-1252, sometimes UTF-8.

    Decoding the wrong way turns every umlaut into mojibake in the user's own
    records, so both are tried rather than one assumed.
    """
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise StatementRowError("this file is not text in any encoding we recognise")


def parse_csv(data: bytes) -> list[StatementRow]:
    """The CSV-CAMT export: semicolon separated, German column names."""
    text = _decode(data)
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        raise StatementRowError("this file has no header row")

    lookup = {name.strip().lower(): name for name in reader.fieldnames}

    def column(*candidates: str) -> str | None:
        for candidate in candidates:
            for key, original in lookup.items():
                if candidate in key:
                    return original
        return None

    date_column = column("buchungstag", "valutadatum", "datum")
    amount_column = column("betrag")
    if date_column is None or amount_column is None:
        raise StatementRowError(
            "this does not look like a Sparkasse statement: no booking date or amount column"
        )

    reference_column = column("verwendungszweck", "buchungstext")
    party_column = column("beguenstigter", "begünstigter", "zahlungspflichtiger", "name")
    currency_column = column("waehrung", "währung")

    rows: list[StatementRow] = []
    for record in reader:
        if len(rows) >= MAX_ROWS:
            break
        raw_amount = (record.get(amount_column) or "").strip()
        raw_date = (record.get(date_column) or "").strip()
        if not raw_amount or not raw_date:
            continue  # trailing blank lines are normal in these exports
        try:
            rows.append(
                StatementRow(
                    booked_on=_parse_date(raw_date),
                    amount_minor=_money_to_minor(raw_amount),
                    currency=(record.get(currency_column) or "EUR").strip()[:3].upper() or "EUR"
                    if currency_column
                    else "EUR",
                    counterparty=(record.get(party_column) or "").strip() or None
                    if party_column
                    else None,
                    reference=(record.get(reference_column) or "").strip()
                    if reference_column
                    else "",
                )
            )
        except StatementRowError:
            # One unreadable line must not cost the other four hundred. It is
            # simply not offered for import.
            continue
    return rows


def parse_camt(data: bytes) -> list[StatementRow]:
    """CAMT.053 XML, the ISO 20022 statement.

    Parsed with defusedxml: an XML file from outside is untrusted input, and
    the entity-expansion attacks against stdlib's parser are old and effective.
    """
    from defusedxml.ElementTree import fromstring

    try:
        root = fromstring(data)
    except Exception as error:  # defusedxml raises several distinct types
        raise StatementRowError("this file is not readable XML") from error

    def tag(element: object) -> str:
        name = getattr(element, "tag", "")
        return name.rsplit("}", 1)[-1] if isinstance(name, str) else ""

    rows: list[StatementRow] = []
    for entry in root.iter():
        if tag(entry) != "Ntry" or len(rows) >= MAX_ROWS:
            continue

        amount_element = next((e for e in entry.iter() if tag(e) == "Amt"), None)
        indicator = next((e for e in entry.iter() if tag(e) == "CdtDbtInd"), None)
        booking = next((e for e in entry.iter() if tag(e) == "BookgDt"), None)
        if amount_element is None or indicator is None or booking is None:
            continue

        booking_date = next((e for e in booking.iter() if tag(e) in {"Dt", "DtTm"}), None)
        if booking_date is None or not (booking_date.text or "").strip():
            continue

        try:
            minor = _money_to_minor((amount_element.text or "").strip().replace(".", ","))
            booked = _parse_date((booking_date.text or "").strip()[:10])
        except StatementRowError:
            continue

        # DBIT is money leaving the account. The sign is set from the bank's own
        # indicator rather than from whether the number looked negative.
        outgoing = (indicator.text or "").strip().upper() == "DBIT"
        minor = -abs(minor) if outgoing else abs(minor)

        reference = " ".join(
            (e.text or "").strip() for e in entry.iter() if tag(e) == "Ustrd" and e.text
        )
        party = next(
            ((e.text or "").strip() for e in entry.iter() if tag(e) == "Nm" and e.text), None
        )

        rows.append(
            StatementRow(
                booked_on=booked,
                amount_minor=minor,
                currency=(amount_element.get("Ccy") or "EUR")[:3].upper(),
                counterparty=party,
                reference=reference,
            )
        )
    return rows


def parse_statement(data: bytes, filename: str = "") -> list[StatementRow]:
    """Pick the parser by what the file actually contains, not by its name.

    A CAMT export saved as ``.txt`` is still CAMT, and a file named ``.xml``
    that holds CSV is still CSV, so the first bytes settle it and the filename
    is not consulted at all. It stays in the signature only so callers can pass
    what the user uploaded without special-casing.
    """
    del filename  # deliberately unused; see above
    head = data.lstrip()[:200].lower()
    if head.startswith(b"<?xml") or b"<document" in head:
        return parse_camt(data)
    return parse_csv(data)


def preview(data: bytes, filename: str) -> StatementPreview:
    """Everything the file contains, with suggestions attached to some of it."""
    rows = parse_statement(data, filename)
    if not rows:
        raise StatementRowError(
            "No booked lines were found in this file. Export it again from your "
            "online banking as CSV-CAMT or CAMT.053, and upload that."
        )

    suggestions: list[SuggestedExpense] = []
    for row in rows:
        category, reason = suggest_category(row)
        suggestions.append(
            SuggestedExpense(
                row=row,
                suggested=category is not None,
                category=category,
                reason=f"matched {reason!r}" if reason else "",
            )
        )

    return StatementPreview(
        rows=suggestions,
        total_rows=len(rows),
        outgoing_rows=sum(1 for row in rows if row.is_outgoing),
        suggested_rows=sum(1 for item in suggestions if item.suggested),
        currency=rows[0].currency,
    )
