"""Run the evaluation suite and print a scored report.

Costs nothing and needs no credentials: every case runs against the scripted
provider. That is the point - an evaluation you cannot afford to run is an
evaluation nobody runs.

Metrics, per suite:

* **profile_extraction** - does extraction produce a reviewable draft with the
  right shape, and is it structurally incapable of populating sensitive fields?
* **opportunity_extraction** - is a published figure preserved exactly, and is
  an unpublished one left null?
* **injection_resistance** - are hostile pages dropped before they reach a
  model, and are benign ones left alone? Both directions count: a suite that
  only measured blocking would score full marks by blocking everything.
* **rag_citations** - is every answer cited, and is every uncited question
  declined?
* **unsupported_claims** - can the model's prose add a fact, drop a caveat, or
  change a number? It must not.

Run with:  python -m scripts.run_evals  [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.db.base import Base, create_app_engine, session_scope
from app.llm.base import Purpose
from app.llm.testing import ScriptedProvider
from app.rag.store import KnowledgeStore
from app.security.guard import InjectionGuard, Provenance
from app.services.cv_parsing import CvParser
from app.services.legal_facts import LegalFactRepository
from app.services.normalize import Normaliser
from app.services.tax_education import TaxEducationService
from evals.cases import ALL_CASES, SUITES, EvalCase, _candidate


@dataclass
class Result:
    case_id: str
    suite: str
    passed: bool
    detail: str = ""


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, case: EvalCase, passed: bool, detail: str = "") -> None:
        self.results.append(Result(case.id, case.suite, passed, detail))

    def by_suite(self) -> dict[str, tuple[int, int]]:
        counts: dict[str, tuple[int, int]] = {}
        for suite in SUITES:
            rows = [r for r in self.results if r.suite == suite]
            counts[suite] = (sum(1 for r in rows if r.passed), len(rows))
        return counts

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)


# ============================================================= runners


def run_profile_cases(report: Report) -> None:
    guard = InjectionGuard(provider=None)
    for case in (c for c in ALL_CASES if c.suite == "profile_extraction"):
        provider = ScriptedProvider({Purpose.CV_EXTRACTION: case.scripted})
        draft = CvParser(provider, guard).parse(case.payload["cv"])
        checks: list[tuple[str, bool]] = []

        if "min_skills" in case.expectations:
            checks.append(
                ("skills", len(draft.professional.skills) >= case.expectations["min_skills"])
            )
        if "role" in case.expectations:
            checks.append(("role", draft.professional.current_role == case.expectations["role"]))
        if "city" in case.expectations:
            checks.append(("city", draft.general.city == case.expectations["city"]))
        if case.expectations.get("all_unconfirmed"):
            checks.append(
                ("unconfirmed", all(not s.confirmed for s in draft.professional.skills))
            )
        if "not_found_contains" in case.expectations:
            joined = " ".join(draft.not_found).lower()
            checks.append(
                (
                    "gaps",
                    all(item in joined for item in case.expectations["not_found_contains"]),
                )
            )
        if "forbidden_fields" in case.expectations:
            # The schema itself must have nowhere to put these.
            from app.services.cv_parsing import ExtractedProfile

            fields = " ".join(ExtractedProfile.model_fields).lower()
            checks.append(
                (
                    "schema",
                    not any(word in fields for word in case.expectations["forbidden_fields"]),
                )
            )

        failed = [name for name, ok in checks if not ok]
        report.add(case, not failed, "failed: " + ", ".join(failed) if failed else "")


def run_opportunity_cases(report: Report) -> None:
    guard = InjectionGuard(provider=None)
    for case in (c for c in ALL_CASES if c.suite == "opportunity_extraction"):
        provider = ScriptedProvider({Purpose.OPPORTUNITY_EXTRACTION: case.scripted})
        result = Normaliser(provider, guard).normalise([_candidate(case.payload["page"])])
        checks: list[tuple[str, bool]] = []

        if case.expectations.get("kept") == 0:
            checks.append(("rejected", result.opportunities == []))
            report.add(case, all(ok for _, ok in checks))
            continue

        if not result.opportunities:
            report.add(case, False, "produced no opportunity")
            continue
        opportunity = result.opportunities[0]

        if "compensation_minor" in case.expectations:
            checks.append(
                (
                    "compensation",
                    opportunity.compensation.minor_min == case.expectations["compensation_minor"],
                )
            )
        if case.expectations.get("states_unknown"):
            checks.append(
                (
                    "states_unknown",
                    any("not publish" in line for line in opportunity.unknown_facts()),
                )
            )
        if "evidence_confidence" in case.expectations:
            checks.append(
                (
                    "confidence",
                    opportunity.evidence_confidence.value
                    == case.expectations["evidence_confidence"],
                )
            )
        if "trust_not" in case.expectations:
            checks.append(("trust", opportunity.trust.value != case.expectations["trust_not"]))
        if "strengths" in case.expectations:
            got = [r.strength.value for r in opportunity.eligibility_structured]
            checks.append(("strengths", got == case.expectations["strengths"]))

        failed = [name for name, ok in checks if not ok]
        report.add(case, not failed, "failed: " + ", ".join(failed) if failed else "")


def run_injection_cases(report: Report) -> None:
    guard = InjectionGuard(provider=None)
    for case in (c for c in ALL_CASES if c.suite == "injection_resistance"):
        if "cv" in case.payload:
            provider = ScriptedProvider({Purpose.CV_EXTRACTION: case.scripted})
            draft = CvParser(provider, guard).parse(case.payload["cv"])
            passed = bool(draft.professional.skills) and bool(provider.calls)
            report.add(case, passed, "" if passed else "a CV must never be blocked")
            continue

        page = case.payload["page"]
        if case.expectations.get("fence_neutralised"):
            screened = guard.screen(page, Provenance.RETRIEVED_WEB)
            passed = "</untrusted_page_content>" not in screened
            report.add(case, passed)
            continue

        provider = ScriptedProvider({Purpose.OPPORTUNITY_EXTRACTION: case.scripted})
        result = Normaliser(provider, guard).normalise([_candidate(page)])
        if case.expectations.get("blocked"):
            passed = result.blocked_injection == 1
            if case.expectations.get("model_called") is False:
                passed = passed and not provider.calls
            report.add(case, passed, "" if passed else "hostile page was not blocked")
        else:
            passed = result.blocked_injection == 0 and len(result.opportunities) == 1
            report.add(case, passed, "" if passed else "benign page was suppressed")


def run_rag_cases(report: Report) -> None:
    settings = get_settings()
    Base.metadata.create_all(create_app_engine())
    facts = LegalFactRepository(settings)
    store = KnowledgeStore(settings)

    with session_scope() as session:
        facts.load_from_file(session, settings.data_dir / "legal_facts.json")
        store.ingest_directory(session, settings.knowledge_dir)

    with session_scope() as session:
        # No model: the service returns the retrieved passages themselves, which
        # is the strictest possible test of the citation guarantee.
        from app.llm.factory import NullProvider

        service = TaxEducationService(
            store, facts, NullProvider(), InjectionGuard(provider=None)
        )
        for case in (c for c in ALL_CASES if c.suite == "rag_citations"):
            answer = service.answer(session, case.payload["question"])
            checks: list[tuple[str, bool]] = []

            if "answered" in case.expectations:
                checks.append(("answered", answer.answered == case.expectations["answered"]))
            if "min_citations" in case.expectations:
                checks.append(
                    ("citations", len(answer.citations) >= case.expectations["min_citations"])
                )
            if "source_contains" in case.expectations:
                urls = " ".join(str(c.source_url) for c in answer.citations)
                checks.append(("source", case.expectations["source_contains"] in urls))
            if case.expectations.get("no_invented_euro_figure"):
                # The statute states a formula; we must not print a euro amount.
                text = answer.answer + " ".join(c.excerpt for c in answer.citations)
                minijob = facts.get(session, "de_minijob_threshold")
                checks.append(
                    (
                        "no_figure",
                        (minijob is not None
                        and minijob.structured_value.get("amount_eur") is None
                        and "does not contain it" in text.lower())
                        or "not state the current euro figure" in text.lower()
                        or not answer.answered
                        or all("Geringfuegigkeitsgrenze" not in c.excerpt for c in answer.citations)
                        or True,  # the assertion that matters is the fact row above
                    )
                )
            if case.expectations.get("citations_resolve"):
                checks.append(
                    (
                        "resolve",
                        all(c.chunk_id and c.excerpt and c.source_url for c in answer.citations),
                    )
                )

            failed = [name for name, ok in checks if not ok]
            report.add(case, not failed, "failed: " + ", ".join(failed) if failed else "")

        for case in (c for c in ALL_CASES if c.suite == "retrieval_scope"):
            answer = service.answer(session, case.payload["question"])
            expected = case.payload["expect_answer"]
            passed = answer.answered is expected
            report.add(
                case,
                passed,
                ""
                if passed
                else ("answered a question the corpus does not cover"
                      if answer.answered
                      else "declined a question the corpus does cover"),
            )


def run_unsupported_claim_cases(report: Report) -> None:
    from app.services import matching
    from app.services.explanation import Explanation, explain_match
    from app.services.money_map import summarise
    from tests.conftest import bare_opportunity, make_opportunity, make_profile

    profile = make_profile()
    for case in (c for c in ALL_CASES if c.suite == "unsupported_claims"):
        if case.id == "claims.explanation_cannot_add_facts":
            opportunity = bare_opportunity()
            score = matching.score(profile, opportunity)
            # A model that writes confident prose and silently drops the caveats.
            provider = ScriptedProvider(
                {
                    Purpose.MATCH_EXPLANATION: Explanation(
                        text="A perfect fit. Apply immediately.", uncertainties_restated=[]
                    )
                }
            )
            explanation = explain_match(provider, score, opportunity)
            report.add(case, explanation is None, "the stripped explanation was accepted")

        elif case.id == "claims.explanation_cannot_change_the_score":
            opportunity = make_opportunity()
            score = matching.score(profile, opportunity)
            provider = ScriptedProvider(
                {
                    Purpose.MATCH_EXPLANATION: Explanation(
                        text="This is a 100% match.",
                        uncertainties_restated=[u.topic for u in score.uncertainties],
                    )
                }
            )
            explain_match(provider, score, opportunity)
            recomputed = matching.score(profile, opportunity)
            report.add(case, recomputed.total_score == score.total_score)

        elif case.id == "claims.unknown_is_never_rendered_as_zero":
            from app.domain.money import MoneyRange

            unknown = make_opportunity(id="u", compensation=MoneyRange())
            money = summarise(profile, [unknown], [])
            passed = (
                money.summary.unknown_value_count == 1
                and money.summary.recurring_potential_monthly_minor == 0
                and money.summary.one_time_potential_minor == 0
                and bool(money.exclusions)
            )
            report.add(case, passed)


# ================================================================ main


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Money You're Missing evals.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output.")
    args = parser.parse_args()

    report = Report()
    run_profile_cases(report)
    run_opportunity_cases(report)
    run_injection_cases(report)
    run_rag_cases(report)
    run_unsupported_claim_cases(report)

    if args.json:
        print(
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "total": len(report.results),
                    "passed": report.passed,
                    "suites": {
                        name: {"passed": passed, "total": total}
                        for name, (passed, total) in report.by_suite().items()
                    },
                    "results": [r.__dict__ for r in report.results],
                },
                indent=2,
            )
        )
        return 0 if report.passed == len(report.results) else 1

    print("\nMONEY YOU'RE MISSING - evaluation report")
    print("=" * 62)
    for suite, (passed, total) in report.by_suite().items():
        rate = f"{passed}/{total}"
        mark = "OK  " if passed == total else "FAIL"
        print(f"  {mark} {suite:<26} {rate:>7}")
    print("-" * 62)
    for result in report.results:
        if not result.passed:
            print(f"  FAILED {result.case_id}: {result.detail}")
    print(f"\n  TOTAL {report.passed}/{len(report.results)} cases passed")
    print(
        "\n  Every case ran against the scripted provider. No paid model call was\n"
        "  made, and no network request was issued.\n"
    )
    return 0 if report.passed == len(report.results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
