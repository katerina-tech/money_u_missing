"""The product's controlled vocabulary.

Everything the system can say about money, evidence, eligibility or progress is
a member of a closed set defined here. That is not tidiness for its own sake:
the central product risk is a system that quietly upgrades a guess into a fact,
and a closed vocabulary is what makes such an upgrade a type error rather than
a wording choice.

Three distinctions carry most of the weight:

* :class:`MoneyState` - potential is not earned, and the arithmetic in
  :mod:`app.services.money_map` refuses to add across the boundary.
* :class:`Confidence` / :class:`TrustLabel` - what we know, how we know it, and
  how old the knowledge is, carried alongside every externally-sourced value.
* :class:`RequirementStrength` - a requirement that is UNKNOWN is not a
  requirement that is met. Unknown is never false.
"""

from __future__ import annotations

from enum import StrEnum

# --------------------------------------------------------------------- money


class MoneyState(StrEnum):
    """How real an amount of money is.

    The ordering is the product's core progression and the reason the dashboard
    can never present a hopeful number as an achieved one.
    """

    POTENTIAL = "POTENTIAL"
    APPLIED = "APPLIED"
    OFFERED = "OFFERED"
    SECURED = "SECURED"
    EARNED = "EARNED"


#: States where money is contractually committed or already received. Only
#: these may be summed into the "secured" and "earned" figures.
COMMITTED_STATES = frozenset({MoneyState.SECURED, MoneyState.EARNED})


class CompensationPeriod(StrEnum):
    """The cadence of an amount. Never inferred - sources state it or it is UNKNOWN."""

    ONE_TIME = "ONE_TIME"
    RECURRING = "RECURRING"
    IRREGULAR = "IRREGULAR"
    UNKNOWN = "UNKNOWN"


class CompensationBasis(StrEnum):
    """The unit an amount is quoted in, used to normalise to a monthly view."""

    PER_HOUR = "PER_HOUR"
    PER_DAY = "PER_DAY"
    PER_ENGAGEMENT = "PER_ENGAGEMENT"
    PER_MONTH = "PER_MONTH"
    PER_YEAR = "PER_YEAR"
    TOTAL = "TOTAL"
    UNKNOWN = "UNKNOWN"


class TaxTreatment(StrEnum):
    """Whether a published figure is gross or net.

    Defaults to UNKNOWN for anything external. German listings very often omit
    this, and guessing turns a 42% error into a confident-looking number.
    """

    GROSS = "GROSS"
    NET = "NET"
    UNKNOWN = "UNKNOWN"


# -------------------------------------------------------------- opportunities


class IncomeStreamCategory(StrEnum):
    """The full taxonomy. P0 discovery prioritises a subset - see :data:`P0_CATEGORIES`."""

    FULL_TIME_JOB = "FULL_TIME_JOB"
    PART_TIME_JOB = "PART_TIME_JOB"
    MINIJOB = "MINIJOB"
    FREELANCE_PROJECT = "FREELANCE_PROJECT"
    CONSULTING = "CONSULTING"
    EXPERT_CALL = "EXPERT_CALL"
    TEACHING = "TEACHING"
    TUTORING = "TUTORING"
    MENTORING = "MENTORING"
    PAID_RESEARCH = "PAID_RESEARCH"
    USER_RESEARCH = "USER_RESEARCH"
    WORKSHOP = "WORKSHOP"
    SPEAKING = "SPEAKING"
    FELLOWSHIP = "FELLOWSHIP"
    PAID_PROGRAM = "PAID_PROGRAM"
    FOUNDER_PROGRAM = "FOUNDER_PROGRAM"
    GRANT = "GRANT"
    COMPETITION = "COMPETITION"
    PRIZE = "PRIZE"
    CREATOR_OPPORTUNITY = "CREATOR_OPPORTUNITY"
    ADVISORY = "ADVISORY"
    BOARD_ROLE = "BOARD_ROLE"
    DIGITAL_PRODUCT = "DIGITAL_PRODUCT"
    AFFILIATE_OR_PARTNERSHIP = "AFFILIATE_OR_PARTNERSHIP"
    OTHER = "OTHER"


#: What discovery actually goes looking for in P0. Chosen because these are
#: professional-grade, publicly listed, and legitimately retrievable - not
#: because the others do not matter.
P0_CATEGORIES: tuple[IncomeStreamCategory, ...] = (
    IncomeStreamCategory.FREELANCE_PROJECT,
    IncomeStreamCategory.CONSULTING,
    IncomeStreamCategory.EXPERT_CALL,
    IncomeStreamCategory.TEACHING,
    IncomeStreamCategory.MENTORING,
    IncomeStreamCategory.WORKSHOP,
    IncomeStreamCategory.PAID_PROGRAM,
    IncomeStreamCategory.FELLOWSHIP,
    IncomeStreamCategory.GRANT,
    IncomeStreamCategory.COMPETITION,
    IncomeStreamCategory.FOUNDER_PROGRAM,
    IncomeStreamCategory.PART_TIME_JOB,
)


class RemoteType(StrEnum):
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    ONSITE = "ONSITE"
    UNKNOWN = "UNKNOWN"


class EmploymentType(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    FREELANCE = "FREELANCE"
    CONTRACT = "CONTRACT"
    STIPEND = "STIPEND"
    GRANT_FUNDED = "GRANT_FUNDED"
    PRIZE_BASED = "PRIZE_BASED"
    UNKNOWN = "UNKNOWN"


class SourceType(StrEnum):
    """How a record reached us. Drives :class:`TrustLabel` and evidence confidence."""

    DEMO = "DEMO"
    CURATED = "CURATED"
    PUBLIC_API = "PUBLIC_API"
    RSS = "RSS"
    ORGANISATION_PAGE = "ORGANISATION_PAGE"
    SEARCH_API = "SEARCH_API"


# ------------------------------------------------------------------ evidence


class Confidence(StrEnum):
    """How well-established a single field is.

    VERIFIED means a human or a structured feed asserted it. EXTRACTED means a
    model read it off a page we retrieved - plausible, not confirmed. UNKNOWN
    means we do not have it, which is emphatically not the same as "no".
    """

    VERIFIED = "VERIFIED"
    SOURCE_BACKED = "SOURCE_BACKED"
    EXTRACTED = "EXTRACTED"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"


class TrustLabel(StrEnum):
    """The badge shown in the UI. One vocabulary, used everywhere."""

    VERIFIED = "VERIFIED"
    SOURCE_BACKED = "SOURCE_BACKED"
    UNVERIFIED = "UNVERIFIED"
    DEMO = "DEMO"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    OUTDATED = "OUTDATED"
    UNKNOWN = "UNKNOWN"


class RequirementStrength(StrEnum):
    """Whether failing a requirement disqualifies.

    HARD failures remove an opportunity from the ranking. SOFT failures cost
    points. UNKNOWN does neither: it becomes a stated uncertainty on the card,
    because the alternative is either hiding a real opportunity or implying a
    qualification the user never confirmed.
    """

    HARD = "HARD"
    SOFT = "SOFT"
    UNKNOWN = "UNKNOWN"


class SafetyVerdict(StrEnum):
    ALLOWED = "ALLOWED"
    FLAGGED = "FLAGGED"
    BLOCKED = "BLOCKED"


class ActionabilityBand(StrEnum):
    """Deliberately not called "expected net income".

    It answers "is this worth acting on now?", which is a different question
    from "does this fit me?" and must not be dressed up as a financial forecast.
    """

    HIGHLY_ACTIONABLE = "HIGHLY_ACTIONABLE"
    ACTIONABLE = "ACTIONABLE"
    REVIEW_FIRST = "REVIEW_FIRST"
    LOW_PRIORITY = "LOW_PRIORITY"


# ------------------------------------------------------------------- profile


class WorkStatus(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    EMPLOYEE_AND_SELF_EMPLOYED = "EMPLOYEE_AND_SELF_EMPLOYED"
    STUDENT = "STUDENT"
    JOB_SEEKING = "JOB_SEEKING"
    PARENTAL_LEAVE = "PARENTAL_LEAVE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class Tristate(StrEnum):
    """For administrative questions where "I do not know" is a real answer.

    A boolean here would force the user to assert something about their own tax
    registration that they may genuinely not know, and the product would then
    reason from it.
    """

    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class BenefitDisclosure(StrEnum):
    """Benefit status is never inferred - only explicitly disclosed."""

    YES = "YES"
    NO = "NO"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY"
    UNKNOWN = "UNKNOWN"


class SkillLevel(StrEnum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    EXPERT = "EXPERT"
    UNKNOWN = "UNKNOWN"


class SkillEvidence(StrEnum):
    """Where a skill claim came from. Inferred skills stay visibly inferred."""

    CV = "CV"
    USER_STATED = "USER_STATED"
    INFERRED = "INFERRED"


class LanguageLevel(StrEnum):
    """CEFR, plus NATIVE and UNKNOWN."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"
    NATIVE = "NATIVE"
    UNKNOWN = "UNKNOWN"


#: Ordering for comparisons. UNKNOWN is deliberately absent: it must never
#: compare as "at least" anything.
LANGUAGE_ORDER: dict[LanguageLevel, int] = {
    LanguageLevel.A1: 1,
    LanguageLevel.A2: 2,
    LanguageLevel.B1: 3,
    LanguageLevel.B2: 4,
    LanguageLevel.C1: 5,
    LanguageLevel.C2: 6,
    LanguageLevel.NATIVE: 7,
}


class SchedulePreference(StrEnum):
    EVENINGS = "EVENINGS"
    WEEKENDS = "WEEKENDS"
    WEEKDAY_HOURS = "WEEKDAY_HOURS"
    FLEXIBLE = "FLEXIBLE"
    UNKNOWN = "UNKNOWN"


class IncomePreference(StrEnum):
    RECURRING = "RECURRING"
    ONE_TIME = "ONE_TIME"
    NO_PREFERENCE = "NO_PREFERENCE"


# ------------------------------------------------------------------- actions


class ApplicationStatus(StrEnum):
    """The tracking state machine. Transitions are validated, not free-form."""

    DISCOVERED = "DISCOVERED"
    SAVED = "SAVED"
    PREPARING = "PREPARING"
    APPLIED = "APPLIED"
    INTERVIEW = "INTERVIEW"
    OFFERED = "OFFERED"
    WON = "WON"
    LOST = "LOST"
    ARCHIVED = "ARCHIVED"


#: Legal transitions. Kept explicit so a UI bug cannot record income against an
#: application that was never applied to.
ALLOWED_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.DISCOVERED: frozenset(
        {ApplicationStatus.SAVED, ApplicationStatus.PREPARING, ApplicationStatus.ARCHIVED}
    ),
    ApplicationStatus.SAVED: frozenset(
        {ApplicationStatus.PREPARING, ApplicationStatus.APPLIED, ApplicationStatus.ARCHIVED}
    ),
    ApplicationStatus.PREPARING: frozenset(
        {ApplicationStatus.APPLIED, ApplicationStatus.SAVED, ApplicationStatus.ARCHIVED}
    ),
    # WON is reachable directly from APPLIED and from INTERVIEW, not only from
    # OFFERED. Many of the categories this product surfaces have no distinct
    # offer stage at all - you join an expert network, your Lehrauftrag is
    # confirmed, your grant application succeeds - and forcing an OFFERED step
    # through the UI would make people either mis-record the outcome or not
    # record it. The outcome dataset is worth more than the tidier diagram.
    ApplicationStatus.APPLIED: frozenset(
        {
            ApplicationStatus.INTERVIEW,
            ApplicationStatus.OFFERED,
            ApplicationStatus.WON,
            ApplicationStatus.LOST,
            ApplicationStatus.ARCHIVED,
        }
    ),
    ApplicationStatus.INTERVIEW: frozenset(
        {
            ApplicationStatus.OFFERED,
            ApplicationStatus.WON,
            ApplicationStatus.LOST,
            ApplicationStatus.ARCHIVED,
        }
    ),
    ApplicationStatus.OFFERED: frozenset(
        {ApplicationStatus.WON, ApplicationStatus.LOST, ApplicationStatus.ARCHIVED}
    ),
    ApplicationStatus.WON: frozenset({ApplicationStatus.ARCHIVED}),
    ApplicationStatus.LOST: frozenset({ApplicationStatus.ARCHIVED}),
    ApplicationStatus.ARCHIVED: frozenset({ApplicationStatus.SAVED}),
}

#: The money state each application status implies. This mapping is why the
#: dashboard cannot show hopeful money as earned money.
STATUS_TO_MONEY_STATE: dict[ApplicationStatus, MoneyState] = {
    ApplicationStatus.DISCOVERED: MoneyState.POTENTIAL,
    ApplicationStatus.SAVED: MoneyState.POTENTIAL,
    ApplicationStatus.PREPARING: MoneyState.POTENTIAL,
    ApplicationStatus.APPLIED: MoneyState.APPLIED,
    ApplicationStatus.INTERVIEW: MoneyState.APPLIED,
    ApplicationStatus.OFFERED: MoneyState.OFFERED,
    ApplicationStatus.WON: MoneyState.SECURED,
    ApplicationStatus.LOST: MoneyState.POTENTIAL,
    ApplicationStatus.ARCHIVED: MoneyState.POTENTIAL,
}


class DismissReason(StrEnum):
    NOT_RELEVANT = "NOT_RELEVANT"
    TOO_LITTLE_MONEY = "TOO_LITTLE_MONEY"
    TOO_MUCH_TIME = "TOO_MUCH_TIME"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    ADMIN_BURDEN = "ADMIN_BURDEN"
    LOCATION = "LOCATION"
    DEADLINE = "DEADLINE"
    ALREADY_KNEW = "ALREADY_KNEW"
    OTHER = "OTHER"


class IncomeStreamStatus(StrEnum):
    """Nothing is an income stream until it is secured or earned."""

    ACTIVE = "ACTIVE"
    POTENTIAL = "POTENTIAL"
    PAUSED = "PAUSED"


# --------------------------------------------------------------- keep / grow


class LegalVerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class AmountBasis(StrEnum):
    """Whether a figure the user gave us is before or after deductions.

    There is deliberately no conversion between GROSS and NET anywhere in this
    product. Going from one to the other in Germany needs the Steuerklasse,
    church tax status, the federal state, the health and care insurance rates
    and any Freibetraege - and performing that calculation for an individual is
    the regulated act this product does not do. Whichever figure the user gives
    us is the one we store, labelled, and the one we show back.
    """

    GROSS = "GROSS"
    NET = "NET"
    UNKNOWN = "UNKNOWN"


class ExpenseCategory(StrEnum):
    """Categories of cost a self-employed person commonly records.

    Naming a category is *not* a statement that the expense is deductible.
    Whether a particular cost was "durch den Betrieb veranlasst" within the
    meaning of Section 4 Abs. 4 EStG turns on facts this product cannot see:
    private use, proportion, documentation, the nature of the activity. The
    categories exist so a person can organise their own records and take a
    specific question to a Steuerberater. They carry no verdict.
    """

    EQUIPMENT = "EQUIPMENT"
    SOFTWARE_AND_SUBSCRIPTIONS = "SOFTWARE_AND_SUBSCRIPTIONS"
    TRAVEL = "TRAVEL"
    WORKSPACE = "WORKSPACE"
    PROFESSIONAL_DEVELOPMENT = "PROFESSIONAL_DEVELOPMENT"
    PROFESSIONAL_SERVICES = "PROFESSIONAL_SERVICES"
    INSURANCE_AND_CONTRIBUTIONS = "INSURANCE_AND_CONTRIBUTIONS"
    MATERIALS = "MATERIALS"
    COMMUNICATION = "COMMUNICATION"
    MARKETING = "MARKETING"
    FEES_AND_CHARGES = "FEES_AND_CHARGES"
    OTHER = "OTHER"


#: Categories where private use is the usual reason a cost is only partly
#: claimable, and so the ones most worth raising a question about. A prompt to
#: ask - never a deduction rule, and never a percentage.
MIXED_USE_PRONE_CATEGORIES: frozenset[ExpenseCategory] = frozenset(
    {
        ExpenseCategory.EQUIPMENT,
        ExpenseCategory.WORKSPACE,
        ExpenseCategory.COMMUNICATION,
        ExpenseCategory.TRAVEL,
        ExpenseCategory.SOFTWARE_AND_SUBSCRIPTIONS,
    }
)


class LegalCategory(StrEnum):
    SELF_EMPLOYMENT = "SELF_EMPLOYMENT"
    TRADE_REGISTRATION = "TRADE_REGISTRATION"
    INCOME_TAX = "INCOME_TAX"
    VAT = "VAT"
    INVOICING = "INVOICING"
    ACCOUNTING = "ACCOUNTING"
    EMPLOYMENT = "EMPLOYMENT"
    SOCIAL_INSURANCE = "SOCIAL_INSURANCE"
    BENEFITS = "BENEFITS"
    MINIJOB = "MINIJOB"
    CAPITAL_INCOME = "CAPITAL_INCOME"
    FAMILY = "FAMILY"


class FinancialGoalType(StrEnum):
    EMERGENCY_FUND = "EMERGENCY_FUND"
    HOME = "HOME"
    EDUCATION = "EDUCATION"
    RETIREMENT = "RETIREMENT"
    CHILD = "CHILD"
    OTHER = "OTHER"


class AccountOwnership(StrEnum):
    """For the family module's neutral comparison. No recommended default."""

    PARENT = "PARENT"
    CHILD = "CHILD"


# ------------------------------------------------------------- intent (graph)


class Intent(StrEnum):
    OPPORTUNITY_DISCOVERY = "OPPORTUNITY_DISCOVERY"
    PROFILE = "PROFILE"
    ACTION_PLANNING = "ACTION_PLANNING"
    TAX_EDUCATION = "TAX_EDUCATION"
    GROW_EDUCATION = "GROW_EDUCATION"
    FAMILY = "FAMILY"
    GENERAL_HELP = "GENERAL_HELP"


class SearchIntent(StrEnum):
    """What a generated query bundle is trying to find."""

    FREELANCE = "FREELANCE"
    CONSULTING = "CONSULTING"
    EXPERT_CALL = "EXPERT_CALL"
    TEACHING = "TEACHING"
    PAID_PROGRAM = "PAID_PROGRAM"
    GRANT = "GRANT"
    COMPETITION = "COMPETITION"
    PART_TIME = "PART_TIME"
