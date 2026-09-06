"""OpportunitySafetyClassifier: keeping illegitimate work out of the results.

The product recommends ways to earn money to people who want more of it. That
is precisely the audience predatory schemes target, and an aggregator that
scrapes broadly will pick up MLM recruitment, "account renting", paid-review
farms and benefit-fraud-adjacent cash work unless something stops it.

Deterministic and conservative, in that order. The rules below are readable,
testable and auditable; a model is not consulted, because the decision to
suppress someone's earning opportunity should not vary between runs and should
be explainable to the source if challenged.

Three outcomes:

* BLOCKED - matched a prohibited category. Never shown, never stored as active.
* FLAGGED - matched a risk signal that is often but not always illegitimate
  (unrealistic returns, upfront payment). Shown with a visible warning, because
  suppressing a legitimate listing is also a harm and the user can judge.
* ALLOWED - nothing matched. Not a safety endorsement, and the UI does not
  present it as one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.enums import SafetyVerdict
from app.domain.opportunity import Opportunity, OpportunityCandidate, SafetyAssessment


@dataclass(frozen=True)
class Rule:
    id: str
    verdict: SafetyVerdict
    reason: str
    patterns: tuple[re.Pattern[str], ...]


def _rx(*sources: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(s, re.IGNORECASE) for s in sources)


#: Prohibited categories. German terms are included because the target market is
#: Germany and a purely English rule set would miss the majority of local cases.
BLOCK_RULES: tuple[Rule, ...] = (
    Rule(
        "mlm",
        SafetyVerdict.BLOCKED,
        "Multi-level marketing or pyramid recruitment.",
        _rx(
            r"\b(multi[- ]?level\s+marketing|mlm)\b",
            r"\b(pyramid|ponzi)\s+(scheme|system)\b",
            r"\bnetwork\s+marketing\b",
            r"\bstrukturvertrieb\b",
            r"\bschneeballsystem\b",
            r"\brecruit\s+(your\s+)?(own\s+)?(down[- ]?line|team)\s+.{0,30}\bcommission\b",
            r"\b(build|baue)\s+(your|dein)\s+(own\s+)?team\b.{0,40}\bpassive(s)?\s+(income|einkommen)\b",
        ),
    ),
    Rule(
        "undeclared_work",
        SafetyVerdict.BLOCKED,
        "Undeclared or cash-in-hand work.",
        _rx(
            r"\bschwarzarbeit\b",
            r"\b(bar\s+auf\s+die\s+hand|schwarz\s+bezahlt)\b",
            r"\bcash[- ]in[- ]hand\b",
            r"\b(no|ohne)\s+(tax|steuer|rechnung|invoice)\b.{0,30}\b(paid|bezahlt|payment)\b",
            r"\bunder\s+the\s+table\b",
            r"\bohne\s+anmeldung\s+arbeiten\b",
            r"\bnicht\s+versteuert\b",
        ),
    ),
    Rule(
        "identity_or_account_misuse",
        SafetyVerdict.BLOCKED,
        "Renting or lending an account, identity or bank details.",
        _rx(
            r"\b(rent|lend|verleih)\w*\s+(your|dein|ihr)\s+(account|konto|identity|ausweis)\b",
            r"\b(bank\s+)?(konto|account)\s+(zur\s+verf.gung|vermieten|verleihen)\b",
            r"\bfinanzagent\b",
            r"\bmoney\s+mule\b",
            r"\breceive\s+(and\s+)?(forward|transfer)\s+(payments|funds|money)\b.{0,40}"
            r"\b(commission|provision)\b",
            r"\buse\s+your\s+(personal\s+)?bank\s+account\s+to\s+(receive|process)\b",
        ),
    ),
    Rule(
        "fake_engagement",
        SafetyVerdict.BLOCKED,
        "Fake reviews, followers or engagement.",
        _rx(
            r"\b(fake|gef.lschte)\s+(reviews?|bewertungen|followers?|accounts?)\b",
            r"\b(write|schreibe)\s+.{0,20}\b(positive\s+reviews?|5[- ]?star\s+reviews?)\b"
            r".{0,40}\b(paid|bezahlt|per\s+review)\b",
            r"\bbuy\s+(followers|likes|engagement)\b",
            r"\brezensionen\s+kaufen\b",
        ),
    ),
    Rule(
        "gambling",
        SafetyVerdict.BLOCKED,
        "Gambling, betting systems or casino arbitrage.",
        _rx(
            r"\b(casino|roulette|blackjack|sportwetten)\b.{0,40}\b(system|strategy|profit|verdien)\b",
            r"\b(matched|arbitrage)\s+betting\b",
            r"\bwettbonus\s+.{0,20}\b(gewinn|profit)\b",
            r"\bguaranteed\s+(betting|gambling)\s+(profit|wins)\b",
        ),
    ),
    Rule(
        "benefit_or_grant_fraud",
        SafetyVerdict.BLOCKED,
        "Misrepresentation to obtain benefits or grants.",
        _rx(
            r"\b(claim|beantrage)\s+.{0,30}\b(without\s+declaring|ohne\s+anzugeben)\b",
            r"\b(hide|verschweige)\s+.{0,25}\b(income|einkommen)\b.{0,25}\b(jobcenter|agentur|amt)\b",
            r"\bgrant\s+application\s+.{0,30}\bfalse\s+(information|details)\b",
        ),
    ),
    Rule(
        "unlicensed_financial_services",
        SafetyVerdict.BLOCKED,
        "Unlicensed financial services or securities advice.",
        _rx(
            # "no licence", "without a licence", "ohne Zulassung", "unlicensed"
            r"\b(sell|selling|vertreib|vermittel)\w*\s+"
            r"(investments?|securities|wertpapiere|financial\s+products?)\b.{0,50}"
            r"\b(no\s+licen[cs]e|without\s+(a\s+)?licen[cs]e|unlicen[cs]ed|"
            r"ohne\s+(bafin[- ])?zulassung|keine\s+lizenz)\b",
            r"\b(unlicen[cs]ed|ohne\s+bafin[- ]zulassung)\b.{0,40}"
            r"\b(financial|investment|anlage|finanz)\w*\s*(advice|beratung|services?)\b",
            r"\bcopy\s+trading\b.{0,40}\bguaranteed\b",
            r"\b(crypto|forex)\s+(signals?|bot)\b.{0,40}\bguaranteed\s+(profit|return)\b",
        ),
    ),
    Rule(
        "stolen_or_illegal_goods",
        SafetyVerdict.BLOCKED,
        "Handling stolen goods or illegal resale.",
        _rx(
            r"\b(hehlerei|stolen\s+goods)\b",
            r"\b(resell|weiterverkauf)\w*\s+.{0,30}\b(counterfeit|f.lschung|replica)\b",
        ),
    ),
)

#: Signals that often accompany a scam but also appear in legitimate listings.
#: A genuine competition really does offer a prize; a genuine training provider
#: really does charge for a certificate. Flag, do not suppress.
FLAG_RULES: tuple[Rule, ...] = (
    Rule(
        "upfront_payment",
        SafetyVerdict.FLAGGED,
        "The listing appears to ask you to pay before earning.",
        _rx(
            r"\b(registration|starter|joining|training)\s+fee\b",
            r"\b(vorkasse|startgeb.hr|teilnahmegeb.hr|kaution)\b",
            r"\byou\s+(must\s+)?(purchase|buy|invest)\s+.{0,30}\b(kit|package|starter)\b",
            r"\binvestition\s+erforderlich\b",
        ),
    ),
    Rule(
        "unrealistic_returns",
        SafetyVerdict.FLAGGED,
        "The listing promises unusually high or guaranteed earnings.",
        _rx(
            r"\bguaranteed\s+(income|earnings|profit|return)\b",
            r"\bgarantiert\w*\s+(einkommen|gewinn|verdienst)\b",
            r"\b\d{4,}\s*(eur|euro|€)\s*(per|pro)\s*(week|woche|day|tag)\b",
            r"\b(verdiene|earn)\s+.{0,15}\b(sofort|instantly|immediately)\b",
            r"\bpassive[s]?\s+(income|einkommen)\b.{0,30}\b(guaranteed|garantiert|ohne\s+arbeit)\b",
            r"\bno\s+(experience|skills?)\s+(needed|required)\b.{0,40}\b\d{3,}\s*(eur|euro|€)\b",
        ),
    ),
    Rule(
        "personal_data_request",
        SafetyVerdict.FLAGGED,
        "The listing appears to ask for sensitive personal or banking details up front.",
        _rx(
            r"\bsend\s+.{0,25}\b(passport|ausweis|id\s+card|personalausweis)\b.{0,30}\bto\s+apply\b",
            r"\b(bank|iban)\s+details?\s+(required|needed)\s+(to|for)\s+(apply|register)\b",
            r"\bkopie\s+des\s+personalausweises\b.{0,40}\bbewerbung\b",
        ),
    ),
    Rule(
        "contact_off_platform",
        SafetyVerdict.FLAGGED,
        "The listing pushes contact to a messaging app rather than an organisation.",
        _rx(
            r"\b(contact|kontakt)\s+.{0,20}\b(whatsapp|telegram|signal)\b.{0,30}\b(only|nur)\b",
            r"\bapply\s+via\s+(whatsapp|telegram)\b",
        ),
    ),
)


def _searchable(text: str) -> str:
    """Collapse spacing so `f r e e   m o n e y` is not a bypass."""
    collapsed = re.sub(r"\s+", " ", text)
    # Also produce a de-spaced variant for the letter-spacing evasion, appended
    # so the original still matches word-boundary patterns.
    return collapsed + "\n" + re.sub(r"(?<=\b\w) (?=\w\b)", "", collapsed)


class OpportunitySafetyClassifier:
    """Deterministic, explainable, and biased towards not suppressing."""

    def __init__(
        self,
        block_rules: tuple[Rule, ...] = BLOCK_RULES,
        flag_rules: tuple[Rule, ...] = FLAG_RULES,
    ) -> None:
        self._block = block_rules
        self._flag = flag_rules

    def classify_text(self, *parts: str | None) -> SafetyAssessment:
        haystack = _searchable(" \n ".join(p for p in parts if p))
        matched: list[str] = []
        reasons: list[str] = []

        for rule in self._block:
            if any(p.search(haystack) for p in rule.patterns):
                matched.append(rule.id)
                reasons.append(rule.reason)
        if matched:
            return SafetyAssessment(
                verdict=SafetyVerdict.BLOCKED, reasons=reasons, matched_rules=matched
            )

        for rule in self._flag:
            if any(p.search(haystack) for p in rule.patterns):
                matched.append(rule.id)
                reasons.append(rule.reason)
        if matched:
            return SafetyAssessment(
                verdict=SafetyVerdict.FLAGGED, reasons=reasons, matched_rules=matched
            )

        return SafetyAssessment(verdict=SafetyVerdict.ALLOWED, reasons=[], matched_rules=[])

    def classify(self, opportunity: Opportunity) -> SafetyAssessment:
        return self.classify_text(
            opportunity.title,
            opportunity.organization,
            opportunity.description,
            opportunity.summary,
            opportunity.eligibility_text,
        )

    def classify_candidate(self, candidate: OpportunityCandidate) -> SafetyAssessment:
        """Screen before extraction, so a blocked listing never costs a model call."""
        return self.classify_text(candidate.title, candidate.raw_text)


DEFAULT_CLASSIFIER = OpportunitySafetyClassifier()
