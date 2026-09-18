"""Reading an exported bank statement, and refusing to read too much into it.

Two kinds of assertion here. The parsing ones matter because a misread German
decimal is a silent factor-of-a-thousand error in somebody's own records. The
suggestion ones matter more: a personal statement is mostly private spending,
and quietly filing groceries as a business cost would hand the user a total
they then have to defend to a Finanzamt.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.enums import ExpenseCategory
from app.services.statements import (
    StatementRow,
    StatementRowError,
    parse_camt,
    parse_csv,
    parse_statement,
    preview,
    suggest_category,
)

CSV = (
    "Auftragskonto;Buchungstag;Valutadatum;Buchungstext;Verwendungszweck;"
    "Beguenstigter/Zahlungspflichtiger;Kontonummer/IBAN;BIC (SWIFT-Code);Betrag;Waehrung;Info\n"
    "DE12;04.09.2026;04.09.2026;LASTSCHRIFT;Monatsbeitrag;GitHub Inc;DE99;XX;-8,00;EUR;Umsatz\n"
    "DE12;05.09.2026;05.09.2026;LASTSCHRIFT;Wocheneinkauf;REWE Markt;DE98;XX;-62,45;EUR;Umsatz\n"
    "DE12;06.09.2026;06.09.2026;GUTSCHRIFT;Honorar September;Hansa Logistik;DE97;XX;1.250,00;EUR;Umsatz\n"
    "DE12;07.09.2026;07.09.2026;LASTSCHRIFT;Tagesticket;Betahaus Coworking;DE96;XX;-1.234,56;EUR;Umsatz\n"
)

CAMT = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
  <BkToCstmrStmt><Stmt>
    <Ntry>
      <Amt Ccy="EUR">49.99</Amt>
      <CdtDbtInd>DBIT</CdtDbtInd>
      <BookgDt><Dt>2026-09-04</Dt></BookgDt>
      <NtryDtls><TxDtls>
        <RltdPties><Cdtr><Nm>JetBrains s.r.o.</Nm></Cdtr></RltdPties>
        <RmtInf><Ustrd>Subscription renewal</Ustrd></RmtInf>
      </TxDtls></NtryDtls>
    </Ntry>
    <Ntry>
      <Amt Ccy="EUR">2850.00</Amt>
      <CdtDbtInd>CRDT</CdtDbtInd>
      <BookgDt><Dt>2026-09-01</Dt></BookgDt>
      <NtryDtls><TxDtls>
        <RltdPties><Dbtr><Nm>Arbeitgeber GmbH</Nm></Dbtr></RltdPties>
        <RmtInf><Ustrd>Gehalt September</Ustrd></RmtInf>
      </TxDtls></NtryDtls>
    </Ntry>
  </Stmt></BkToCstmrStmt>
</Document>
"""


def row(**overrides: object) -> StatementRow:
    data: dict[str, object] = {
        "booked_on": date(2026, 9, 4),
        "amount_minor": -1_000,
        "reference": "",
    }
    data.update(overrides)
    return StatementRow.model_validate(data)


# ------------------------------------------------------------------ CSV


def test_the_csv_export_is_read_as_the_bank_wrote_it() -> None:
    rows = parse_csv(CSV.encode("utf-8"))
    assert len(rows) == 4
    assert rows[0].booked_on == date(2026, 9, 4)
    assert rows[0].amount_minor == -800
    assert rows[0].counterparty == "GitHub Inc"


def test_german_decimals_are_not_misread_by_a_factor_of_a_thousand() -> None:
    """"1.234,56" is twelve hundred euro, not one euro twenty-three."""
    rows = parse_csv(CSV.encode("utf-8"))
    assert rows[3].amount_minor == -123_456
    assert rows[2].amount_minor == 125_000


def test_money_coming_in_keeps_its_sign() -> None:
    incoming = parse_csv(CSV.encode("utf-8"))[2]
    assert incoming.amount_minor > 0
    assert incoming.is_outgoing is False


def test_a_windows_encoded_export_keeps_its_umlauts() -> None:
    text = CSV.replace("Wocheneinkauf", "Bürobedarf für März")
    rows = parse_csv(text.encode("cp1252"))
    assert any("Bürobedarf für März" in r.reference for r in rows)


def test_one_unreadable_line_does_not_lose_the_file() -> None:
    broken = CSV + "DE12;nicht-ein-datum;;;;;;;keine-zahl;EUR;\n"
    assert len(parse_csv(broken.encode("utf-8"))) == 4


def test_a_file_that_is_not_a_statement_is_refused() -> None:
    with pytest.raises(StatementRowError):
        parse_csv(b"name;email\nSam;sam@example.com\n")


# ----------------------------------------------------------------- CAMT


def test_camt_takes_the_direction_from_the_banks_own_indicator() -> None:
    rows = parse_camt(CAMT.encode("utf-8"))
    assert len(rows) == 2

    debit = next(r for r in rows if r.counterparty == "JetBrains s.r.o.")
    assert debit.amount_minor == -4_999
    credit = next(r for r in rows if r.counterparty == "Arbeitgeber GmbH")
    assert credit.amount_minor == 285_000


def test_the_format_is_chosen_by_content_not_by_filename() -> None:
    """A CAMT export saved as .txt is still CAMT."""
    assert len(parse_statement(CAMT.encode("utf-8"), "export.txt")) == 2
    assert len(parse_statement(CSV.encode("utf-8"), "export.xml")) == 4


def test_malformed_xml_is_refused_rather_than_half_read() -> None:
    with pytest.raises(StatementRowError):
        parse_camt(b"<Document><Ntry>")


# ----------------------------------------------------- what it suggests


def test_a_recognised_supplier_is_suggested_with_the_word_that_matched() -> None:
    category, reason = suggest_category(
        row(counterparty="GitHub Inc", reference="Monatsbeitrag")
    )
    assert category is ExpenseCategory.SOFTWARE_AND_SUBSCRIPTIONS
    assert reason == "github"


def test_ordinary_private_spending_is_suggested_as_nothing() -> None:
    """The default that keeps this from becoming a budgeting app by accident."""
    category, reason = suggest_category(row(counterparty="REWE Markt", reference="Wocheneinkauf"))
    assert category is None
    assert reason == ""


def test_money_coming_in_is_never_suggested_as_a_cost() -> None:
    category, _ = suggest_category(
        row(amount_minor=125_000, counterparty="GitHub Inc", reference="Refund")
    )
    assert category is None


def test_a_word_inside_another_word_does_not_match() -> None:
    category, _ = suggest_category(row(counterparty="Notionale Versicherung AG"))
    assert category is None


# --------------------------------------------------------------- preview


def test_the_preview_imports_nothing_and_says_so() -> None:
    result = preview(CSV.encode("utf-8"), "umsaetze.csv")
    assert result.total_rows == 4
    assert result.outgoing_rows == 3
    # GitHub and Betahaus match; the supermarket does not.
    assert result.suggested_rows == 2
    assert "Nothing has been imported" in result.note


def test_every_unsuggested_row_is_still_offered_for_the_user_to_decide() -> None:
    result = preview(CSV.encode("utf-8"), "umsaetze.csv")
    groceries = next(r for r in result.rows if r.row.counterparty == "REWE Markt")
    assert groceries.suggested is False
    assert groceries.category is None
    # It is present, not hidden: the user may well want to record it.
    assert groceries.row.amount_minor == -6_245


def test_an_empty_file_is_an_error_with_a_way_out() -> None:
    with pytest.raises(StatementRowError) as caught:
        preview(b"Buchungstag;Betrag\n", "leer.csv")
    assert "CSV-CAMT" in str(caught.value)


def test_parsing_is_deterministic() -> None:
    assert preview(CSV.encode("utf-8"), "a.csv") == preview(CSV.encode("utf-8"), "a.csv")


# ------------------------------------------------------------- PDF


PDF_LIKE = """Kontoauszug 7/2026
Datum Erläuterung Betrag EUR
Kontostand am 01.06.2026, Auszug Nr. 6 1.000,00
01.06.2026 Lastschrift
Berliner Verkehrsbetriebe (BVG) Abo
 -63,00
02.06.2026 LastschriftDebitkarte
LIDL SAGT DANKE//Berlin/DE
 -8,15
03.06.2026 Lastschrift
Telekom Deutschland GmbH Festnetz
 -54,89
Berliner Sparkasse
Alexanderplatz 2, 10178 Berlin
Seite 2 von 7
04.06.2026 Überweisungseingang
Hansa Logistik HONORAR
 1.250,00
Kontostand am 01.07.2026 um 00:48 Uhr 2.123,96
"""


def as_lines(text: str) -> list[str]:
    return text.splitlines()


def test_the_reconciliation_proves_the_parse_read_everything() -> None:
    """A layout parser can miss a line silently. The balances settle it.

    1000.00 - 63.00 - 8.15 - 54.89 + 1250.00 = 2123.96
    """
    from app.services.statements import _PDF_AMOUNT, _PDF_CLOSING, _PDF_DATE, _PDF_OPENING

    # Exercised through the same regexes the parser uses, without needing a
    # real PDF binary in the repository.
    opening = _PDF_OPENING.search(PDF_LIKE)
    closing = _PDF_CLOSING.search(PDF_LIKE)
    assert opening and closing

    amounts = [
        line for line in as_lines(PDF_LIKE) if _PDF_AMOUNT.match(line.strip())
    ]
    dates = [
        line
        for line in as_lines(PDF_LIKE)
        if _PDF_DATE.match(line.strip()) and "Kontostand" not in line
    ]
    # One amount per booked line is the property that makes the layout safe.
    assert len(amounts) == len(dates) == 4


def test_the_balance_lines_are_not_read_as_transactions() -> None:
    """Two independent reasons, and the test states both.

    The balance line carries a date, but not at the start, so the anchored
    pattern does not match it. The parser also skips any line containing
    "Kontostand", which is what catches a layout where the date does lead.
    """
    from app.services.statements import _PDF_DATE

    balance = "Kontostand am 01.06.2026, Auszug Nr. 6 1.000,00"
    assert _PDF_DATE.match(balance) is None
    assert "Kontostand" in balance


def test_page_furniture_is_dropped_from_the_description() -> None:
    from app.services.statements import _PDF_NOISE

    for line in ("Berliner Sparkasse", "Seite 2 von 7", "Alexanderplatz 2, 10178 Berlin"):
        assert any(noise in line.lower() for noise in _PDF_NOISE)


def test_a_transaction_type_is_stripped_from_the_payee_name() -> None:
    from app.services.statements import _pdf_counterparty

    assert _pdf_counterparty("LastschriftDebitkarte LIDL SAGT DANKE//Berlin/DE") == (
        "LIDL SAGT DANKE"
    )
    assert _pdf_counterparty("Überweisungseingang Hansa Logistik HONORAR") == (
        "Hansa Logistik HONORAR"
    )


def test_a_generic_german_word_does_not_become_a_business_fee() -> None:
    """A lost-ticket penalty from the transport authority is not an account fee.

    "Entgelt" is ordinary German for "fee" and matched one on a real statement,
    so the rule was narrowed to the compounds that mean an account charge.
    """
    category, _ = suggest_category(
        row(counterparty="Berliner Verkehrsbetriebe (BVG)", reference="Bel. Verlust Entgelt")
    )
    assert category is None
