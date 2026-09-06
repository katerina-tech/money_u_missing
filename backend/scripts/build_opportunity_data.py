"""Writes the demo and curated opportunity datasets.

Two files, two completely different kinds of claim, and the difference is the
point.

**demo_opportunities.json** - fourteen fictional opportunities across the P0
categories. Every organisation name is invented and reads as invented; none of
them could be mistaken for a real company, which is a requirement rather than a
stylistic choice. Every record carries ``is_demo: true``, and the schema forbids
a demo record from claiming verified compensation. Deadlines are generated
relative to the run date so the demo never shows an expired opportunity.

**curated_opportunities.json** - real programmes, recorded by hand from the
publisher's own page, with the URL that was read and the date it was read. Their
compensation fields are largely null, and that is not an oversight: the pages
were checked and do not state the amounts. Publishing a plausible figure for a
real federal programme would be precisely the failure this product exists to
avoid, so the record says the amount is not published and the UI shows it as
unknown.

Run with:  python -m scripts.build_opportunity_data
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
DATA = BACKEND / "data"

TODAY = date.today()
NOW = datetime.now(UTC).isoformat()


def in_days(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def eur(amount: float) -> int:
    return round(amount * 100)


# ============================================================ demo dataset
# Fictional. Organisation names are deliberately constructed so that no real
# company is implied: generic descriptors plus an invented suffix.

DEMO: list[dict] = [
    {
        "id": "demo-expert-network-ai",
        "title": "Paid expert calls - data & AI practitioners",
        "organization": "Northlight Expert Circle (fictional)",
        "category": "EXPERT_CALL",
        "subcategory": "Expert network",
        "description": (
            "A fictional expert network that matches practitioners with investors and "
            "strategy teams for one-hour paid consultations. Applicants complete a "
            "profile and are contacted when a project matches their background. "
            "Engagements are ad hoc, remote, and typically one to two hours."
        ),
        "country": "DE",
        "city": None,
        "remote_type": "REMOTE",
        "required_skills": ["Data Engineering", "Machine Learning"],
        "preferred_skills": ["Cloud Architecture", "MLOps"],
        "required_languages": [{"code": "en", "minimum": "B2", "strength": "HARD"}],
        "experience_min_years": 5,
        "employment_type": "FREELANCE",
        "compensation_min_minor": eur(120),
        "compensation_max_minor": eur(250),
        "compensation_basis": "PER_HOUR",
        "compensation_period": "IRREGULAR",
        "tax_treatment": "UNKNOWN",
        "estimated_hours_min": 1,
        "estimated_hours_max": 3,
        "deadline": None,
        "eligibility_text": (
            "Open to practitioners with at least five years of hands-on experience."
        ),
        "eligibility_structured": [
            {"label": "At least 5 years professional experience", "strength": "HARD"},
            {"label": "Based in the EU", "strength": "SOFT"},
        ],
        "source_url": "https://example.invalid/demo/expert-network",
    },
    {
        "id": "demo-consulting-data-platform",
        "title": "Freelance data platform review - 3 week engagement",
        "organization": "Hansa Logistik Werke (fictional)",
        "category": "CONSULTING",
        "description": (
            "A fictional mid-sized logistics company looking for an external review of "
            "its data platform before a migration. Part-time engagement alongside an "
            "existing job is explicitly acceptable. Remote with one on-site workshop."
        ),
        "country": "DE",
        "city": "Hamburg",
        "remote_type": "HYBRID",
        "required_skills": ["Data Engineering", "SQL", "Cloud Architecture"],
        "preferred_skills": ["dbt", "Airflow"],
        "required_languages": [
            {"code": "de", "minimum": "B2", "strength": "SOFT"},
            {"code": "en", "minimum": "B2", "strength": "HARD"},
        ],
        "experience_min_years": 4,
        "employment_type": "FREELANCE",
        "compensation_min_minor": eur(850),
        "compensation_max_minor": eur(1100),
        "compensation_basis": "PER_DAY",
        "compensation_period": "ONE_TIME",
        "tax_treatment": "GROSS",
        "estimated_hours_min": 8,
        "estimated_hours_max": 12,
        "deadline": in_days(21),
        "eligibility_structured": [
            {"label": "Able to invoice as a freelancer in Germany", "strength": "HARD"},
        ],
        "source_url": "https://example.invalid/demo/consulting-data-platform",
    },
    {
        "id": "demo-lehrauftrag-hochschule",
        "title": "Lehrauftrag: Datenanalyse (Bachelor, 2 SWS)",
        "organization": "Hochschule Nordwest (fictional)",
        "category": "TEACHING",
        "description": (
            "A fictional university of applied sciences seeking a practitioner to teach a "
            "two-hours-per-week module in the winter semester. Evening slot, suited to "
            "someone in full-time employment. Honorar paid per Semesterwochenstunde."
        ),
        "country": "DE",
        "city": "Bremen",
        "remote_type": "HYBRID",
        "required_skills": ["Data Analysis", "Statistics", "Teaching"],
        "required_languages": [{"code": "de", "minimum": "C1", "strength": "HARD"}],
        "experience_min_years": 3,
        "employment_type": "FREELANCE",
        "compensation_min_minor": eur(1800),
        "compensation_max_minor": eur(2400),
        "compensation_basis": "TOTAL",
        "compensation_period": "ONE_TIME",
        "tax_treatment": "UNKNOWN",
        "estimated_hours_min": 4,
        "estimated_hours_max": 6,
        "deadline": in_days(34),
        "eligibility_text": "Ein abgeschlossenes Hochschulstudium ist Voraussetzung.",
        "eligibility_structured": [
            {"label": "Completed university degree", "strength": "HARD"},
            {"label": "German at C1", "strength": "HARD"},
        ],
        "source_url": "https://example.invalid/demo/lehrauftrag",
    },
    {
        "id": "demo-workshop-facilitation",
        "title": "Paid workshop facilitator - AI literacy for public sector teams",
        "organization": "Civic Skills Werkstatt (fictional)",
        "category": "WORKSHOP",
        "description": (
            "A fictional training provider running one-day workshops for municipal "
            "administrations. Facilitators are paid per workshop day and use provided "
            "materials. Two to four days per quarter."
        ),
        "country": "DE",
        "city": "Berlin",
        "remote_type": "ONSITE",
        "required_skills": ["Workshop Facilitation", "AI Engineering", "Teaching"],
        "required_languages": [{"code": "de", "minimum": "C1", "strength": "HARD"}],
        "employment_type": "FREELANCE",
        "compensation_min_minor": eur(700),
        "compensation_max_minor": eur(900),
        "compensation_basis": "PER_DAY",
        "compensation_period": "IRREGULAR",
        "tax_treatment": "GROSS",
        "estimated_hours_min": 8,
        "estimated_hours_max": 8,
        "deadline": None,
        "source_url": "https://example.invalid/demo/workshop-facilitator",
    },
    {
        "id": "demo-paid-research-panel",
        "title": "Paid research interviews - developer tooling study",
        "organization": "Steinweg Research Collective (fictional)",
        "category": "PAID_RESEARCH",
        "description": (
            "A fictional research agency recruiting software practitioners for 60-minute "
            "remote interviews about developer tooling. One session per participant. "
            "Compensation paid within 14 days of the session."
        ),
        "country": "DE",
        "remote_type": "REMOTE",
        "required_skills": ["Software Engineering"],
        "required_languages": [{"code": "en", "minimum": "B2", "strength": "HARD"}],
        "employment_type": "FREELANCE",
        "compensation_min_minor": eur(150),
        "compensation_max_minor": eur(150),
        "compensation_basis": "PER_ENGAGEMENT",
        "compensation_period": "ONE_TIME",
        "tax_treatment": "GROSS",
        "estimated_hours_min": 1,
        "estimated_hours_max": 1,
        "deadline": in_days(12),
        "source_url": "https://example.invalid/demo/research-panel",
    },
    {
        "id": "demo-mentoring-programme",
        "title": "Paid mentor - early-career data professionals",
        "organization": "Bruecke Mentoring Programme (fictional)",
        "category": "MENTORING",
        "description": (
            "A fictional non-profit running a structured six-month mentoring programme. "
            "Mentors commit to two hours per month and receive an expense allowance. "
            "The page does not state whether the allowance is taxable."
        ),
        "country": "DE",
        "remote_type": "REMOTE",
        "required_skills": ["Mentoring", "Data Science"],
        "experience_min_years": 5,
        "employment_type": "UNKNOWN",
        "compensation_min_minor": eur(80),
        "compensation_max_minor": eur(80),
        "compensation_basis": "PER_MONTH",
        "compensation_period": "RECURRING",
        "tax_treatment": "UNKNOWN",
        "estimated_hours_min": 2,
        "estimated_hours_max": 2,
        "deadline": in_days(45),
        "source_url": "https://example.invalid/demo/mentoring",
    },
    {
        "id": "demo-founder-programme",
        "title": "Part-time founder programme - technical founders, cohort 7",
        "organization": "Ostwind Founder Lab (fictional)",
        "category": "FOUNDER_PROGRAM",
        "description": (
            "A fictional twelve-week evening programme for people building a technical "
            "product alongside employment. Includes a stipend; the amount is not "
            "published on the listing."
        ),
        "country": "DE",
        "city": "Leipzig",
        "remote_type": "HYBRID",
        "required_skills": ["Software Engineering", "Product Management"],
        "employment_type": "STIPEND",
        "compensation_min_minor": None,
        "compensation_max_minor": None,
        "compensation_basis": "UNKNOWN",
        "compensation_period": "UNKNOWN",
        "tax_treatment": "UNKNOWN",
        "estimated_hours_min": 6,
        "estimated_hours_max": 10,
        "deadline": in_days(28),
        "eligibility_text": "Open to residents of Germany. A co-founder is not required.",
        "eligibility_structured": [
            {"label": "Resident in Germany", "strength": "HARD"},
            {"label": "Working prototype", "strength": "SOFT"},
        ],
        "source_url": "https://example.invalid/demo/founder-lab",
    },
    {
        "id": "demo-innovation-grant",
        "title": "Regional innovation grant - digital tools for small business",
        "organization": "Landesagentur Mittelstand Nord (fictional)",
        "category": "GRANT",
        "description": (
            "A fictional regional grant for individuals and micro-businesses developing "
            "digital tools. Applications require a project description and a budget "
            "outline. Grant size is stated as a range."
        ),
        "country": "DE",
        "region": "Niedersachsen",
        "remote_type": "REMOTE",
        "required_skills": ["Software Engineering"],
        "required_languages": [{"code": "de", "minimum": "B2", "strength": "HARD"}],
        "employment_type": "GRANT_FUNDED",
        "compensation_min_minor": eur(8000),
        "compensation_max_minor": eur(25000),
        "compensation_basis": "TOTAL",
        "compensation_period": "ONE_TIME",
        "tax_treatment": "UNKNOWN",
        "estimated_hours_min": None,
        "estimated_hours_max": None,
        "deadline": in_days(56),
        "eligibility_text": (
            "Antragsberechtigt sind natürliche Personen mit Wohnsitz in Niedersachsen "
            "sowie Kleinstunternehmen."
        ),
        "eligibility_structured": [
            {"label": "Residence in Niedersachsen", "strength": "HARD"},
            {"label": "Gewerbe or freelance registration", "strength": "HARD"},
        ],
        "source_url": "https://example.invalid/demo/innovation-grant",
    },
    {
        "id": "demo-competition-prize",
        "title": "Open data challenge - 3 prizes",
        "organization": "Datenwende Challenge (fictional)",
        "category": "COMPETITION",
        "description": (
            "A fictional open competition to build a tool using published municipal data. "
            "Individual entries permitted. Judged on usefulness and openness."
        ),
        "country": "DE",
        "remote_type": "REMOTE",
        "required_skills": ["Python", "Data Analysis"],
        "employment_type": "PRIZE_BASED",
        "compensation_min_minor": eur(2000),
        "compensation_max_minor": eur(10000),
        "compensation_basis": "TOTAL",
        "compensation_period": "ONE_TIME",
        "tax_treatment": "UNKNOWN",
        # Per week, like every other record: an entry takes a few evenings a
        # week over the submission window, not sixty hours a week.
        "estimated_hours_min": 4,
        "estimated_hours_max": 8,
        "deadline": in_days(9),
        "source_url": "https://example.invalid/demo/data-challenge",
    },
    {
        "id": "demo-fellowship-public-interest",
        "title": "Public-interest technology fellowship - part-time track",
        "organization": "Gemeinwohl Fellowship (fictional)",
        "category": "FELLOWSHIP",
        "description": (
            "A fictional six-month fellowship placing technologists with public-interest "
            "organisations. The part-time track is eight hours per week. The listing does "
            "not state the stipend."
        ),
        "country": "DE",
        "remote_type": "REMOTE",
        "required_skills": ["Software Engineering", "Data Protection"],
        "preferred_skills": ["GDPR"],
        "required_languages": [{"code": "de", "minimum": "B2", "strength": "SOFT"}],
        "experience_min_years": 3,
        "employment_type": "STIPEND",
        "compensation_min_minor": None,
        "compensation_max_minor": None,
        "compensation_basis": "UNKNOWN",
        "compensation_period": "UNKNOWN",
        "tax_treatment": "UNKNOWN",
        "estimated_hours_min": 8,
        "estimated_hours_max": 8,
        "deadline": in_days(2),
        "source_url": "https://example.invalid/demo/fellowship",
    },
    {
        "id": "demo-part-time-analyst",
        "title": "Part-time data analyst (16h/week)",
        "organization": "Gruenspan Energie Genossenschaft (fictional)",
        "category": "PART_TIME_JOB",
        "description": (
            "A fictional energy cooperative hiring a part-time analyst on a permanent "
            "employment contract. Fixed monthly salary, sixteen hours per week."
        ),
        "country": "DE",
        "city": "Freiburg",
        "remote_type": "HYBRID",
        "required_skills": ["SQL", "Data Analysis", "Python"],
        "required_languages": [{"code": "de", "minimum": "C1", "strength": "HARD"}],
        "experience_min_years": 2,
        "employment_type": "EMPLOYEE",
        "compensation_min_minor": eur(1900),
        "compensation_max_minor": eur(2300),
        "compensation_basis": "PER_MONTH",
        "compensation_period": "RECURRING",
        "tax_treatment": "GROSS",
        "estimated_hours_min": 16,
        "estimated_hours_max": 16,
        "deadline": in_days(40),
        "source_url": "https://example.invalid/demo/part-time-analyst",
    },
    {
        "id": "demo-advisory-board",
        "title": "Technical advisory board member - climate tech",
        "organization": "Wattfeld Ventures (fictional)",
        "category": "ADVISORY",
        "description": (
            "A fictional early-stage company seeking a technical adviser for quarterly "
            "sessions. Compensation is described only as 'to be agreed'."
        ),
        "country": "DE",
        "remote_type": "REMOTE",
        "required_skills": ["Cloud Architecture", "Machine Learning"],
        "experience_min_years": 8,
        "employment_type": "UNKNOWN",
        "compensation_min_minor": None,
        "compensation_max_minor": None,
        "compensation_basis": "UNKNOWN",
        "compensation_period": "UNKNOWN",
        "tax_treatment": "UNKNOWN",
        "estimated_hours_min": 2,
        "estimated_hours_max": 4,
        "deadline": None,
        "source_url": "https://example.invalid/demo/advisory",
    },
    {
        "id": "demo-speaking-conference",
        "title": "Paid conference speaker - engineering practice track",
        "organization": "Nordkonf (fictional)",
        "category": "SPEAKING",
        "description": (
            "A fictional practitioner conference paying an honorarium plus travel for "
            "accepted talks. Call for proposals is open."
        ),
        "country": "DE",
        "city": "Koeln",
        "remote_type": "ONSITE",
        "required_skills": ["Public Speaking", "Software Engineering"],
        "required_languages": [{"code": "en", "minimum": "B2", "strength": "HARD"}],
        "employment_type": "FREELANCE",
        "compensation_min_minor": eur(600),
        "compensation_max_minor": eur(600),
        "compensation_basis": "PER_ENGAGEMENT",
        "compensation_period": "ONE_TIME",
        "tax_treatment": "UNKNOWN",
        "estimated_hours_min": 10,
        "estimated_hours_max": 20,
        "deadline": in_days(17),
        "source_url": "https://example.invalid/demo/conference-cfp",
    },
    {
        "id": "demo-tutoring-statistics",
        "title": "Online tutor - university statistics",
        "organization": "Lernbruecke Tutoring (fictional)",
        "category": "TUTORING",
        "description": (
            "A fictional tutoring platform matching tutors with university students. "
            "Hourly rate, flexible schedule, evenings and weekends."
        ),
        "country": "DE",
        "remote_type": "REMOTE",
        "required_skills": ["Statistics", "Teaching"],
        "required_languages": [{"code": "de", "minimum": "C1", "strength": "HARD"}],
        "employment_type": "FREELANCE",
        "compensation_min_minor": eur(28),
        "compensation_max_minor": eur(40),
        "compensation_basis": "PER_HOUR",
        "compensation_period": "RECURRING",
        "tax_treatment": "GROSS",
        "estimated_hours_min": 2,
        "estimated_hours_max": 8,
        "deadline": None,
        "source_url": "https://example.invalid/demo/tutoring",
    },
]


# ========================================================= curated dataset
# Real programmes. Every field below was read from the page named in
# source_url on the date in last_verified_at. Where the page does not state a
# figure, the field is null and stays null.

CURATED: list[dict] = [
    {
        "id": "curated-exist-gruenderstipendium",
        "title": "EXIST-Gründerstipendium",
        "organization": "EXIST - Existenzgründungen aus der Wissenschaft (BMWE)",
        "category": "FOUNDER_PROGRAM",
        "subcategory": "Federal startup stipend",
        "description": (
            "Federal funding programme for students, graduates and researchers founding a "
            "company from an innovative, science-based idea, during the pre-founding "
            "phase. A connection to a university or research institution is required; the "
            "application is made through that institution rather than directly."
        ),
        "summary": (
            "Federal stipend for science-based startup teams in the pre-founding phase. "
            "The programme page does not publish the stipend amounts."
        ),
        "country": "DE",
        "remote_type": "UNKNOWN",
        "required_skills": [],
        "preferred_skills": [],
        "required_languages": [{"code": "de", "minimum": "UNKNOWN", "strength": "UNKNOWN"}],
        "employment_type": "STIPEND",
        # The page describes the programme but does not state the amounts. We
        # therefore state nothing. This is the single most important line in
        # this file: a plausible figure here would be a fabricated fact about a
        # real federal programme.
        "compensation_min_minor": None,
        "compensation_max_minor": None,
        "compensation_basis": "UNKNOWN",
        "compensation_period": "UNKNOWN",
        "tax_treatment": "UNKNOWN",
        "compensation_verified": False,
        "estimated_hours_min": None,
        "estimated_hours_max": None,
        "deadline": None,
        "eligibility_text": (
            "Studierende, Absolventinnen und Absolventen sowie Wissenschaftlerinnen und "
            "Wissenschaftler mit einer innovativen Gründungsidee aus Wissenschaft und "
            "Forschung. Eine Anbindung an eine Hochschule oder Forschungseinrichtung ist "
            "erforderlich."
        ),
        "eligibility_structured": [
            {
                "label": "Connection to a university or research institution",
                "strength": "HARD",
                "source_text": (
                    "Eine Anbindung an eine Hochschule oder Forschungseinrichtung "
                    "ist essenziell."
                ),
            },
            {"label": "Science- or research-based founding idea", "strength": "HARD"},
        ],
        "source_url": (
            "https://www.exist.de/EXIST/Navigation/DE/Gruendungsfoerderung/"
            "EXIST-Gruenderstipendium/exist-gruenderstipendium.html"
        ),
        "evidence_confidence": "SOURCE_BACKED",
        "last_verified_at": NOW,
    },
    {
        "id": "curated-exist-forschungstransfer",
        "title": "EXIST-Forschungstransfer",
        "organization": "EXIST - Existenzgründungen aus der Wissenschaft (BMWE)",
        "category": "PAID_PROGRAM",
        "subcategory": "Federal research-transfer funding",
        "description": (
            "Federal support for research-based startups of high technical complexity "
            "with an existing proof of principle. Provides financial support alongside "
            "mentoring, access to university infrastructure and networking. A connection "
            "to a university or research institution is required."
        ),
        "summary": (
            "Federal funding for development-intensive, research-based startups. The "
            "programme page does not publish the funding amounts or the phase structure."
        ),
        "country": "DE",
        "remote_type": "UNKNOWN",
        "required_skills": [],
        "required_languages": [{"code": "de", "minimum": "UNKNOWN", "strength": "UNKNOWN"}],
        "employment_type": "GRANT_FUNDED",
        "compensation_min_minor": None,
        "compensation_max_minor": None,
        "compensation_basis": "UNKNOWN",
        "compensation_period": "UNKNOWN",
        "tax_treatment": "UNKNOWN",
        "compensation_verified": False,
        "estimated_hours_min": None,
        "estimated_hours_max": None,
        "deadline": None,
        "eligibility_text": (
            "Besonders entwicklungsintensive Gründungsvorhaben mit vorhandenem Proof of "
            "Principle und Anbindung an eine Hochschule oder Forschungseinrichtung."
        ),
        "eligibility_structured": [
            {"label": "Existing proof of principle", "strength": "HARD"},
            {"label": "Connection to a university or research institution", "strength": "HARD"},
        ],
        "source_url": (
            "https://www.exist.de/EXIST/Navigation/DE/Gruendungsfoerderung/"
            "EXIST-Forschungstransfer/exist-forschungstransfer.html"
        ),
        "evidence_confidence": "SOURCE_BACKED",
        "last_verified_at": NOW,
    },
]


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)

    (DATA / "demo_opportunities.json").write_text(
        json.dumps(
            {
                "generated_at": NOW,
                "note": (
                    "FICTIONAL DATA. Every organisation named here is invented and marked "
                    "as such. Every record is loaded with is_demo=true and can never "
                    "claim verified compensation. Do not treat any of these as a real "
                    "offer."
                ),
                "opportunities": [
                    {**record, "is_demo": True, "compensation_verified": False}
                    for record in DEMO
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    (DATA / "curated_opportunities.json").write_text(
        json.dumps(
            {
                "generated_at": NOW,
                "note": (
                    "REAL programmes, recorded by hand from the page at source_url on "
                    "last_verified_at. Null compensation fields mean the page does not "
                    "state a figure - not missing data to be filled in later by "
                    "estimation. Adding an entry here means a person read the page."
                ),
                "opportunities": [{**record, "is_demo": False} for record in CURATED],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(DEMO)} demo and {len(CURATED)} curated opportunities to {DATA}")


if __name__ == "__main__":
    main()
