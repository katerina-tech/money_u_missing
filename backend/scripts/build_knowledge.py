"""Writes the German knowledge corpus and the legal-fact registry.

Every document and every fact below was retrieved from the named authority on
the ``RETRIEVED`` date. Nothing here is written from model memory: where a value
is not stated by the authority - the Minijob euro figure is the clearest case,
because the statute gives a formula and delegates the number to a Bundesanzeiger
publication - the fact is recorded as unavailable and the answer layer refuses
to quote it rather than filling in a plausible figure.

Re-running this script is safe. It is the single place the corpus is defined, so
"where did this number come from?" has exactly one answer.

Run with:  python -m scripts.build_knowledge
"""

from __future__ import annotations

import json
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
KNOWLEDGE = BACKEND / "data" / "knowledge"

#: The date every document below was retrieved from its authority. Facts are
#: reported as NEEDS_REVIEW once they are older than
#: ``MYM_LEGAL_FACT_MAX_AGE_DAYS`` (default 365) measured from here.
RETRIEVED = "2026-09-04T00:00:00+00:00"

GESETZE = "Gesetze im Internet (Bundesministerium der Justiz)"


def doc(
    *,
    slug: str,
    title: str,
    topic: str,
    source_url: str,
    source_name: str,
    effective_year: int | None,
    body: str,
) -> None:
    front = [
        "---",
        f'title: "{title}"',
        f'source_name: "{source_name}"',
        f"source_url: {source_url}",
        f"topic: {topic}",
        f"retrieved_at: {RETRIEVED}",
    ]
    if effective_year:
        front.append(f"effective_year: {effective_year}")
    front.append("---")
    KNOWLEDGE.mkdir(parents=True, exist_ok=True)
    (KNOWLEDGE / f"{slug}.md").write_text(
        "\n".join(front) + "\n\n" + body.strip() + "\n", encoding="utf-8"
    )


DOCUMENTS: list[dict] = [
    {
        "slug": "kleinunternehmerregelung",
        "title": "Kleinunternehmerregelung (§ 19 UStG)",
        "topic": "VAT",
        "source_url": "https://www.gesetze-im-internet.de/ustg_1980/__19.html",
        "source_name": GESETZE,
        "effective_year": 2026,
        "body": """
# Kleinunternehmerregelung

## What the statute says

§ 19 Absatz 1 UStG makes turnover exempt from Umsatzsteuer where, in the words
of the statute, the total turnover under Absatz 2 "im vorangegangenen
Kalenderjahr 25 000 Euro nicht überschritten hat und im laufenden Kalenderjahr
100 000 Euro nicht überschreitet."

Two separate thresholds therefore apply, and they work differently:

- **25,000 EUR** relates to the **previous** calendar year. It is tested
  retrospectively.
- **100,000 EUR** relates to the **current** calendar year. It is a limit that
  must not be exceeded as the year runs.

## Entrepreneurs established elsewhere in the EU

§ 19 Absatz 4 UStG applies a different test to entrepreneurs resident in
another EU member state: an annual turnover calculated in accordance with
Directive 2006/112/EC of not more than 100,000 EUR in both the previous and the
current calendar year.

## What this does not tell you

The statute states the thresholds. It does not tell you:

- whether your own total turnover is calculated the way you assume, since
  § 19 Absatz 2 defines what counts;
- what happens operationally in the month you cross the current-year limit;
- whether opting out of the regulation is better for you, which depends on
  whether your customers can deduct input tax.

Those are questions for a Steuerberater or your Finanzamt.
""",
    },
    {
        "slug": "freiberuflich-oder-gewerbe",
        "title": "Freiberufliche Tätigkeit (§ 18 EStG) und Gewerbeanmeldung (§ 14 GewO)",
        "topic": "TRADE_REGISTRATION",
        "source_url": "https://www.gesetze-im-internet.de/estg/__18.html",
        "source_name": GESETZE,
        "effective_year": 2026,
        "body": """
# Freiberuflich or Gewerbe

This distinction decides whether you must register a Gewerbe, whether
Gewerbesteuer can arise, and which chamber you may be required to join. It is
one of the most consequential and most contested questions for someone starting
additional professional income in Germany.

## The catalogue of freie Berufe

§ 18 Absatz 1 Nr. 1 EStG names the professions that constitute selbständige
Arbeit. The statute lists:

"Ärzte, Zahnärzte, Tierärzte, Rechtsanwälte, Notare, Patentanwälte,
Vermessungsingenieure, Ingenieure, Architekten, Handelschemiker,
Wirtschaftsprüfer, Steuerberater, beratenden Volks- und Betriebswirte,
vereidigten Buchprüfer, Steuerbevollmächtigten, Heilpraktiker, Dentisten,
Krankengymnasten, Journalisten, Bildberichterstatter, Dolmetscher, Übersetzer,
Lotsen und ähnlicher Berufe"

The same provision also covers independently exercised scientific, artistic,
literary, teaching and educational activity ("wissenschaftliche, künstlerische,
schriftstellerische, unterrichtende oder erzieherische Tätigkeit").

The phrase "und ähnlicher Berufe" - and similar professions - is why this is
contested. Whether a particular modern occupation is "similar" to a listed one
is decided on the facts, and IT and data work in particular has produced
divergent decisions.

## Gewerbeanmeldung

§ 14 Absatz 1 Satz 1 GewO states: "Wer den selbständigen Betrieb eines
stehenden Gewerbes, einer Zweigniederlassung oder einer unselbständigen
Zweigstelle anfängt, muss dies der zuständigen Behörde gleichzeitig anzeigen."

Notification is to the competent authority and is due at the same time as the
activity begins. § 14 GewO also requires notification when the business moves,
when its scope changes or extends to goods or services not previously covered,
when the proprietor's name changes, and when the business ceases.

## What this does not tell you

Whether *your* activity is freiberuflich or gewerblich. That depends on what
you actually do, how the engagement is structured, and how your Finanzamt
assesses it. This product does not make that classification, and you should not
treat any tool's opinion on it as settled.
""",
    },
    {
        "slug": "steuerliche-erfassung",
        "title": (
            "Anzeige der Erwerbstätigkeit und Fragebogen zur steuerlichen "
            "Erfassung (§ 138 AO)"
        ),
        "topic": "SELF_EMPLOYMENT",
        "source_url": "https://www.gesetze-im-internet.de/ao_1977/__138.html",
        "source_name": GESETZE,
        "effective_year": 2026,
        "body": """
# Registering an activity with the tax office

## The obligation

§ 138 AO requires anyone taking up a business or self-employed activity to
notify the tax authorities.

For freelance activity the statute is direct: "Wer eine freiberufliche
Tätigkeit aufnimmt, hat dies dem nach § 19 zuständigen Finanzamt mitzuteilen."

For a Gewerbe, notification goes to the municipality where the business opens,
which then informs the Finanzamt - or directly to the Finanzamt where the
municipality is not competent.

## Deadline

Notifications are due "innerhalb eines Monats nach dem meldepflichtigen
Ereignis" - within one month of the event that triggers them.

## Form

§ 138 Absatz 1b AO requires the further information to be provided "nach
amtlich vorgeschriebenem Datensatz über die amtlich bestimmte Schnittstelle" -
that is, electronically in the officially prescribed format, which in practice
means ELSTER. The Finanzamt may permit an official paper form
("amtlich vorgeschriebenem Vordruck") to avoid undue hardship.

This is the Fragebogen zur steuerlichen Erfassung. Completing it is normally
what produces your Steuernummer, and you generally need that before you can
issue a compliant invoice.

## What this does not tell you

Which answers to give on the questionnaire. Several of its fields - expected
turnover, expected profit, whether you opt out of the Kleinunternehmerregelung -
have lasting consequences and are worth discussing with a Steuerberater before
you submit.
""",
    },
    {
        "slug": "rechnung-pflichtangaben",
        "title": "Pflichtangaben in einer Rechnung (§ 14 UStG)",
        "topic": "INVOICING",
        "source_url": "https://www.gesetze-im-internet.de/ustg_1980/__14.html",
        "source_name": GESETZE,
        "effective_year": 2026,
        "body": """
# What an invoice must contain

§ 14 Absatz 4 UStG lists the mandatory content of an invoice:

1. "den vollständigen Namen und die vollständige Anschrift des leistenden
   Unternehmers und des Leistungsempfängers"
2. "die dem leistenden Unternehmer vom Finanzamt erteilte Steuernummer oder die
   ihm vom Bundeszentralamt für Steuern erteilte
   Umsatzsteuer-Identifikationsnummer"
3. "das Ausstellungsdatum"
4. "eine fortlaufende Nummer mit einer oder mehreren Zahlenreihen, die zur
   Identifizierung der Rechnung vom Rechnungsaussteller einmalig vergeben wird"
5. "die Menge und die Art (handelsübliche Bezeichnung) der gelieferten
   Gegenstände oder den Umfang und die Art der sonstigen Leistung"
6. "den Zeitpunkt der Lieferung oder sonstigen Leistung"
7. "das nach Steuersätzen und einzelnen Steuerbefreiungen aufgeschlüsselte
   Entgelt"
8. "den anzuwendenden Steuersatz sowie den auf das Entgelt entfallenden
   Steuerbetrag"
9. "in den Fällen des § 14b Abs. 1 Satz 5 einen Hinweis auf die
   Aufbewahrungspflicht"
10. where the recipient issues the invoice, the word "Gutschrift"

## Practical consequence

Point 2 is why registration usually comes before invoicing: without a
Steuernummer or USt-IdNr you cannot issue a compliant invoice.

If you apply the Kleinunternehmerregelung you do not show a Steuersatz or a
Steuerbetrag, and you are expected to state the reason. The exact wording to
use is a question for your Steuerberater.
""",
    },
    {
        "slug": "euer-und-betriebsausgaben",
        "title": "Einnahmenüberschussrechnung und Betriebsausgaben (§ 4 EStG)",
        "topic": "ACCOUNTING",
        "source_url": "https://www.gesetze-im-internet.de/estg/__4.html",
        "source_name": GESETZE,
        "effective_year": 2026,
        "body": """
# EÜR and business expenses

## Who may use an EÜR

§ 4 Absatz 3 Satz 1 EStG: "Steuerpflichtige, die nicht auf Grund gesetzlicher
Vorschriften verpflichtet sind, Bücher zu führen und regelmäßig Abschlüsse zu
machen, und die auch keine Bücher führen und keine Abschlüsse machen, können
als Gewinn den Überschuss der Betriebseinnahmen über die Betriebsausgaben
ansetzen."

Two conditions, both required: you are not legally obliged to keep books, and
you do not in fact keep them. Most people starting professional side income
meet both, which is why the EÜR is the usual method.

Profit is simply business income minus business expenses. Pass-through items
are excluded, and certain assets must be recorded with their acquisition cost
and date.

## Betriebsausgaben

§ 4 Absatz 4 EStG defines them in one line: "Betriebsausgaben sind die
Aufwendungen, die durch den Betrieb veranlasst sind."

Expenditure caused by the business. The brevity is deceptive - whether a
particular cost is "veranlasst" by the business is exactly where disputes
arise, especially for equipment and rooms used both privately and for work.

## What this does not tell you

Which of your specific costs are deductible, or in what proportion. Nothing in
this product calculates your profit or your tax.
""",
    },
    {
        "slug": "arbeitslosengeld-nebentaetigkeit",
        "title": "Nebentätigkeit während des Arbeitslosengeldbezugs (§§ 138, 155 SGB III)",
        "topic": "BENEFITS",
        "source_url": "https://www.gesetze-im-internet.de/sgb_3/__138.html",
        "source_name": GESETZE,
        "effective_year": 2026,
        "body": """
# Additional work while receiving Arbeitslosengeld

This section applies only if you receive unemployment-related benefits. Getting
it wrong can mean repayment demands, so the underlying provisions are quoted
directly.

## The 15-hour rule

§ 138 SGB III provides that a secondary activity does not remove the status of
being without employment where "die Arbeits- oder Tätigkeitszeit (Arbeitszeit)
weniger als 15 Stunden wöchentlich umfasst" - fewer than 15 hours per week.

Hours across all activities are added together. The statute disregards
occasional minor deviations from the limit.

Reaching 15 hours per week is therefore not "earning too much" - it can end the
status on which the benefit depends, regardless of what you are paid.

## The 165 EUR allowance

§ 155 SGB III provides for "eines Freibetrags in Höhe von 165 Euro in dem
Kalendermonat der Ausübung".

Income above that allowance, after tax, social insurance contributions and
business expenses, is set against the benefit in the month it is earned. For
self-employed activity, business expenses are calculated as a flat 30% of gross
income unless you evidence more.

A higher allowance applies where the secondary activity was already held for at
least 12 months alongside the main job during the 18 months before
unemployment; it is then based on the average monthly income from that period,
and never less than 165 EUR.

## What you must do

Report the activity to the Agentur für Arbeit. The obligation arises when you
take the work on, not when you are paid for it. Ask them directly how your
specific case is treated before you start.
""",
    },
    {
        "slug": "minijob-grenze",
        "title": "Geringfügige Beschäftigung / Minijob (§ 8 SGB IV)",
        "topic": "MINIJOB",
        "source_url": "https://www.gesetze-im-internet.de/sgb_4/__8.html",
        "source_name": GESETZE,
        "effective_year": 2026,
        "body": """
# Minijob: the threshold is a formula, not a fixed figure

§ 8 Absatz 1 SGB IV defines geringfügige Beschäftigung in two alternatives:

1. earnings that regularly do not exceed the Geringfügigkeitsgrenze
   ("das Arbeitsentgelt aus dieser Beschäftigung regelmäßig die
   Geringfügigkeitsgrenze nicht übersteigt"); or
2. work limited by its nature or by contract to a maximum of three months or 70
   working days in a calendar year.

## How the limit is calculated

§ 8 Absatz 1a SGB IV does not state a euro amount. It states a calculation: the
minimum wage multiplied by 130, divided by three, and rounded up to whole euros.
The construction corresponds to ten hours a week at the statutory minimum wage.

The resulting figure is published by the Bundesministerium für Arbeit und
Soziales in the Bundesanzeiger. It therefore changes whenever the minimum wage
changes.

**This product does not state the current euro figure**, because the statute
does not contain it and we have not recorded it from the Bundesanzeiger
publication. Check the current Geringfügigkeitsgrenze at the Minijob-Zentrale or
in the Bundesanzeiger before relying on a number.

## Why this matters for additional income

A Minijob alongside a main employment has its own tax and social-insurance
treatment, and holding more than one can change it. If you already have a main
job, ask how a second employment affects your Steuerklasse and your
contributions before accepting it.
""",
    },
    {
        "slug": "einkommensteuer-grundfreibetrag",
        "title": "Einkommensteuertarif und Grundfreibetrag (§ 32a EStG)",
        "topic": "INCOME_TAX",
        "source_url": "https://www.gesetze-im-internet.de/estg/__32a.html",
        "source_name": GESETZE,
        "effective_year": 2026,
        "body": """
# Grundfreibetrag

§ 32a Absatz 1 EStG sets the income tax tariff. The first zone - the
Grundfreibetrag, on which the tax is zero - is **12,348 EUR**, stated to apply
"ab dem Veranlagungszeitraum 2026".

## What this means for additional income

Additional income is added to your other income and taxed at your personal
rate. It is not taxed separately or at a flat rate. Because Germany's tariff is
progressive, an extra euro of side income is taxed at your *marginal* rate,
which is higher than your average rate - so an estimate based on your average
tax burden will understate what the additional income costs you.

The Grundfreibetrag is not an allowance that applies again to side income. If
your main income already exceeds it, it has been used.

## What this does not tell you

Your tax liability. This product does not calculate it, and the difference
between a rough estimate and your actual assessment can be substantial once
Solidaritätszuschlag, Kirchensteuer, deductible expenses and any joint
assessment are taken into account.
""",
    },
    {
        "slug": "sparer-pauschbetrag",
        "title": "Sparer-Pauschbetrag (§ 20 Abs. 9 EStG)",
        "topic": "CAPITAL_INCOME",
        "source_url": "https://www.gesetze-im-internet.de/estg/__20.html",
        "source_name": GESETZE,
        "effective_year": 2026,
        "body": """
# Sparer-Pauschbetrag

§ 20 Absatz 9 EStG provides that in determining income from capital assets, "als
Werbungskosten ein Betrag von 1 000 Euro abzuziehen (Sparer-Pauschbetrag)".

For jointly assessed spouses: "Ehegatten, die zusammen veranlagt werden, wird
ein gemeinsamer Sparer-Pauschbetrag von 2 000 Euro gewährt."

- Single person: **1,000 EUR**
- Jointly assessed spouses: **2,000 EUR**

## Why this appears in a product about earning more

Two reasons, both practical rather than advisory.

First, the allowance is per person. That is one of the factual differences
between saving in a parent's name and in a child's name, which is why the family
comparison in this product mentions it - as a difference, not as a
recommendation.

Second, the allowance is only applied automatically if you have given your bank
a Freistellungsauftrag. Investment income below the allowance can still be taxed
at source if you have not.

## What this does not tell you

Whether any particular investment or account structure suits you. This product
does not give investment advice and does not recommend financial instruments -
see docs/REGULATORY_BOUNDARIES.md.
""",
    },
    {
        "slug": "nebentaetigkeit-arbeitsvertrag",
        "title": "Nebentätigkeit alongside employment - what to check",
        "topic": "EMPLOYMENT",
        "source_url": "https://www.gesetze-im-internet.de/gg/art_12.html",
        "source_name": GESETZE,
        "effective_year": 2026,
        "body": """
# Additional work alongside an employment contract

## The starting point

Article 12 Absatz 1 GG guarantees free choice of occupation and place of work
("Alle Deutschen haben das Recht, Beruf, Arbeitsplatz und Ausbildungsstätte
frei zu wählen"). An employer cannot simply forbid all secondary activity.

## What is nevertheless commonly agreed

Employment contracts in Germany very often contain a Nebentätigkeitsklausel
requiring you to notify the employer, or to obtain approval, before taking on
additional work. Such clauses are widespread and are frequently enforceable in
the narrower forms - notification duties and restrictions on working for
competitors.

## What to check before you accept additional work

1. Does your contract contain a Nebentätigkeitsklausel, and does it require
   notification or approval?
2. Would the work be for a competitor of your employer?
3. Would it use your employer's equipment, materials or confidential
   information?
4. Would the combined working time exceed the limits in the
   Arbeitszeitgesetz?
5. Does it fall in a period of holiday, sick leave or parental leave, where
   separate rules apply?

## What this does not tell you

Whether a particular clause in your contract is enforceable. That is a legal
question about your specific contract, and this product does not answer legal
questions about individual documents.
""",
    },
]


FACTS: list[dict] = [
    {
        "id": "de_kleinunternehmer_thresholds",
        "category": "VAT",
        "title": "Kleinunternehmerregelung turnover thresholds",
        "summary": (
            "Umsatzsteuer is not levied where total turnover did not exceed 25,000 EUR "
            "in the previous calendar year and does not exceed 100,000 EUR in the "
            "current calendar year (§ 19 Abs. 1 UStG)."
        ),
        "structured_value": {
            "previous_year_eur": 25000,
            "current_year_eur": 100000,
            "eu_established_eur": 100000,
            "statute": "§ 19 UStG",
        },
        "effective_from": "2025-01-01",
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/ustg_1980/__19.html",
        "verification_status": "VERIFIED",
    },
    {
        "id": "de_grundfreibetrag",
        "category": "INCOME_TAX",
        "title": "Grundfreibetrag",
        "summary": (
            "The first tariff zone of the income tax scale, on which tax is zero, is "
            "12,348 EUR from Veranlagungszeitraum 2026 (§ 32a Abs. 1 EStG)."
        ),
        "structured_value": {
            "amount_eur": 12348,
            "assessment_year_from": 2026,
            "statute": "§ 32a Abs. 1 EStG",
        },
        "effective_from": "2026-01-01",
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/estg/__32a.html",
        "verification_status": "VERIFIED",
    },
    {
        "id": "de_sparer_pauschbetrag",
        "category": "CAPITAL_INCOME",
        "title": "Sparer-Pauschbetrag",
        "summary": (
            "1,000 EUR is deducted as Werbungskosten from income from capital assets; "
            "2,000 EUR for jointly assessed spouses (§ 20 Abs. 9 EStG)."
        ),
        "structured_value": {
            "single_eur": 1000,
            "joint_eur": 2000,
            "statute": "§ 20 Abs. 9 EStG",
        },
        "effective_from": "2023-01-01",
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/estg/__20.html",
        "verification_status": "VERIFIED",
    },
    {
        "id": "de_minijob_threshold",
        "category": "MINIJOB",
        "title": "Geringfügigkeitsgrenze (Minijob earnings limit)",
        "summary": (
            "The statute states a formula, not an amount: the minimum wage multiplied by "
            "130, divided by three, rounded up to whole euros (§ 8 Abs. 1a SGB IV). The "
            "resulting figure is published in the Bundesanzeiger and changes with the "
            "minimum wage. We have not recorded the current euro figure, so this product "
            "does not state one."
        ),
        "structured_value": {
            "formula": "ceil(minimum_wage * 130 / 3)",
            "amount_eur": None,
            "published_in": "Bundesanzeiger, by the Bundesministerium fuer Arbeit und Soziales",
            "statute": "§ 8 Abs. 1a SGB IV",
        },
        "effective_from": "2022-10-01",
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/sgb_4/__8.html",
        # The formula is verified; the euro figure is not available to us, and
        # content_available=False keeps the answer layer from quoting a number.
        "verification_status": "NEEDS_REVIEW",
        "content_available": False,
    },
    {
        "id": "de_alg_hours_limit",
        "category": "BENEFITS",
        "title": "15-hour weekly limit while receiving Arbeitslosengeld",
        "summary": (
            "A secondary activity does not end Beschäftigungslosigkeit where working time "
            "is fewer than 15 hours per week; hours across all activities are combined "
            "(§ 138 SGB III)."
        ),
        "structured_value": {"hours_per_week_limit": 15, "statute": "§ 138 SGB III"},
        "effective_from": "2012-04-01",
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/sgb_3/__138.html",
        "verification_status": "VERIFIED",
    },
    {
        "id": "de_alg_nebeneinkommen_freibetrag",
        "category": "BENEFITS",
        "title": "165 EUR monthly allowance for secondary income during Arbeitslosengeld",
        "summary": (
            "165 EUR per calendar month of the activity is disregarded; income above that, "
            "after tax, contributions and expenses, is set against the benefit. Self-"
            "employed expenses are taken as a flat 30% of gross unless more is evidenced "
            "(§ 155 SGB III)."
        ),
        "structured_value": {
            "allowance_eur_per_month": 165,
            "self_employed_expense_flat_rate": 0.30,
            "statute": "§ 155 SGB III",
        },
        "effective_from": "2012-04-01",
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/sgb_3/__155.html",
        "verification_status": "VERIFIED",
    },
    {
        "id": "de_tax_registration_deadline",
        "category": "SELF_EMPLOYMENT",
        "title": "One-month deadline to notify the tax office of a new activity",
        "summary": (
            "Taking up a freelance or business activity must be notified within one month "
            "of the reportable event, electronically in the officially prescribed format "
            "(§ 138 AO). This is the Fragebogen zur steuerlichen Erfassung."
        ),
        "structured_value": {
            "deadline_months": 1,
            "channel": (
                "electronic (officially prescribed interface); "
                "paper only on hardship exception"
            ),
            "statute": "§ 138 AO",
        },
        "effective_from": "2021-01-01",
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/ao_1977/__138.html",
        "verification_status": "VERIFIED",
    },
    {
        "id": "de_gewerbeanmeldung",
        "category": "TRADE_REGISTRATION",
        "title": "Gewerbeanmeldung obligation",
        "summary": (
            "Anyone beginning the independent operation of a stehendes Gewerbe must notify "
            "the competent authority at the same time as starting (§ 14 Abs. 1 GewO)."
        ),
        "structured_value": {
            "timing": "simultaneously with commencement",
            "authority": "competent municipal authority",
            "statute": "§ 14 GewO",
        },
        "effective_from": "2009-01-01",
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/gewo/__14.html",
        "verification_status": "VERIFIED",
    },
    {
        "id": "de_invoice_requirements",
        "category": "INVOICING",
        "title": "Mandatory invoice content",
        "summary": (
            "§ 14 Abs. 4 UStG lists ten mandatory elements, including the full names and "
            "addresses of both parties, the issuer's Steuernummer or USt-IdNr, the issue "
            "date, a unique sequential number, the quantity and nature of the supply, the "
            "date of supply, the consideration broken down by tax rate, and the rate and "
            "amount of tax."
        ),
        "structured_value": {"element_count": 10, "statute": "§ 14 Abs. 4 UStG"},
        "effective_from": "2004-01-01",
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/ustg_1980/__14.html",
        "verification_status": "VERIFIED",
    },
    {
        "id": "de_euer_eligibility",
        "category": "ACCOUNTING",
        "title": "Who may use an Einnahmenüberschussrechnung",
        "summary": (
            "Taxpayers who are not legally obliged to keep books and prepare regular "
            "accounts, and who in fact do neither, may take profit as the surplus of "
            "business income over business expenses (§ 4 Abs. 3 EStG). Betriebsausgaben "
            "are expenses caused by the business (§ 4 Abs. 4 EStG)."
        ),
        "structured_value": {"statute": "§ 4 Abs. 3 und 4 EStG"},
        "effective_from": "2009-01-01",
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/estg/__4.html",
        "verification_status": "VERIFIED",
    },
    {
        "id": "de_freiberuflich_catalogue",
        "category": "TRADE_REGISTRATION",
        "title": "Catalogue of freie Berufe",
        "summary": (
            "§ 18 Abs. 1 Nr. 1 EStG names the Katalogberufe and extends to 'ähnliche "
            "Berufe', plus independently exercised scientific, artistic, literary, "
            "teaching and educational activity. Whether a modern occupation is 'similar' "
            "to a listed profession is decided on the facts and is frequently disputed."
        ),
        "structured_value": {"statute": "§ 18 Abs. 1 Nr. 1 EStG"},
        "effective_from": "2009-01-01",
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/estg/__18.html",
        "verification_status": "VERIFIED",
    },
    # ---- Registry entries we could not populate. Present, listed, never quoted.
    {
        "id": "de_kuenstlersozialkasse",
        "category": "SOCIAL_INSURANCE",
        "title": "Künstlersozialkasse membership for self-employed creative work",
        "summary": (
            "NOT YET VERIFIED. Self-employed artists, writers and journalists may be "
            "required to be insured through the Künstlersozialkasse, which affects "
            "contributions on side income. We have not recorded the current conditions "
            "from the authority, so this product does not state them."
        ),
        "structured_value": {},
        "source_name": "Künstlersozialkasse",
        "source_url": "https://www.kuenstlersozialkasse.de/",
        "verification_status": "UNKNOWN",
        "content_available": False,
    },
    {
        "id": "de_uebungsleiterfreibetrag",
        "category": "INCOME_TAX",
        "title": "Übungsleiterfreibetrag and Ehrenamtspauschale",
        "summary": (
            "NOT YET VERIFIED. Tax allowances exist for certain teaching, training and "
            "voluntary activity carried out for non-profit or public bodies (§ 3 Nr. 26 "
            "and Nr. 26a EStG). We have not recorded the current amounts, so this product "
            "does not state them."
        ),
        "structured_value": {"statute": "§ 3 Nr. 26, Nr. 26a EStG"},
        "source_name": GESETZE,
        "source_url": "https://www.gesetze-im-internet.de/estg/__3.html",
        "verification_status": "UNKNOWN",
        "content_available": False,
    },
]


def main() -> None:
    for spec in DOCUMENTS:
        doc(**spec)

    facts_path = BACKEND / "data" / "legal_facts.json"
    facts_path.write_text(
        json.dumps(
            {
                "retrieved_at": RETRIEVED,
                "note": (
                    "Every value here was read from the source_url on retrieved_at. "
                    "Entries with content_available=false are registry placeholders: "
                    "they are listed so the gap is visible, and are never quoted."
                ),
                "facts": [
                    {"jurisdiction": "DE", "retrieved_at": RETRIEVED,
                     "last_verified_at": RETRIEVED, "content_available": True, **fact}
                    for fact in FACTS
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(DOCUMENTS)} knowledge documents to {KNOWLEDGE}")
    print(f"wrote {len(FACTS)} legal facts to {facts_path}")


if __name__ == "__main__":
    main()
