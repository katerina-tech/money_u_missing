# Regulatory boundaries

Three lines this product does not cross: tax advice, legal advice, and
investment advice. Each is enforced by how the code is built, not by a
disclaimer — because a disclaimer under a paragraph that reads like advice does
not stop the paragraph reading like advice.

---

## 1. Tax and legal (Steuerberatung / Rechtsberatung)

### The line

In Germany, advising on someone's individual tax position is a regulated
activity reserved to Steuerberater and comparable professionals
(Steuerberatungsgesetz). Legal advice on individual matters is likewise
reserved (Rechtsdienstleistungsgesetz). This product is neither.

### What it does

- Retrieves passages from a corpus of German legislation, each with its source
  URL and retrieval date.
- Answers **only** from those passages, with citations.
- Distinguishes what the rule generally says from what depends on the
  individual's circumstances.
- Produces **specific questions** to put to a Finanzamt or Steuerberater.

### What it never does

- **State a tax amount owed.** No code computes one.
- **Convert a net figure into a gross one, or the reverse.** That needs the
  Steuerklasse, church tax status, the federal state and the insurance rates.
  Doing it for an individual is the regulated act, so the personal page stores
  whichever basis the user gave, totals the two separately, and never sums them.
- **Say that a recorded cost is deductible.** Costs are recorded and added up;
  whether any of them reduces someone's tax is a question the page puts to a
  Finanzamt rather than answers.
- **Compute anyone's Kinderfreibetrag.** § 32 EStG is quoted with its source;
  what an individual receives depends on a comparison at assessment and on how
  the amounts are split, neither of which this product performs.
- **Classify the user's activity** as freiberuflich or gewerblich. That turns on
  facts the product cannot see and is contested between tax offices. The Germany
  check says so explicitly, every time.
- **Tell anyone which legal form to choose.**
- **Answer from model memory.** If retrieval returns nothing relevant, the
  answer is a refusal.

### How it is enforced

| Mechanism | Where |
|---|---|
| `CitedAnswer` fails validation if `answered=True` with no citations | `domain/legal.py` |
| Jurisdiction gate — a question naming another country is declined | `services/tax_education.py` |
| Relevance gate — no distinctive shared term means no answer | `services/tax_education.py` |
| An answer whose citations do not resolve becomes a refusal | `services/tax_education.py` |
| Freshness — a fact past its review horizon is `NEEDS_REVIEW`, not quoted | `domain/legal.py` |
| The Germany check is built from `LegalFact` rows and templates, never a model | `services/germany_check.py` |
| Benefit guidance appears **only** on explicit disclosure | `services/germany_check.py` |
| Gross and net are never converted into one another, anywhere | `domain/finances.py` |
| `ExpenseSummary` has no field for a tax effect, rate or saving | `domain/finances.py` |
| Recorded costs produce questions for a Finanzamt, never a verdict | `domain/finances.py` |
| Children are recorded only on explicit disclosure, by age, never named | `domain/finances.py` |
| A test reads the module source and fails on `to_net`, `to_gross`, `tax_rate` | `tests/test_finances.py` |
| Every "money you may be losing" finding cites a stored fact, or carries no figure | `services/leaks.py` |
| A quoted ceiling is the statute's figure, never what the user would receive | `services/leaks.py` |
| No finding is raised without a trigger in the user's own data | `services/leaks.py` |
| The findings have a count, never a euro total - summing ceilings would invent one | `services/leaks.py` |

The structural point: there is no way to construct a positive answer object
without having retrieved something to point at. Even a fully subverted prompt
cannot return an uncited answer, because the type will not validate.

### Tested

`tests/test_keep_and_grow.py` — a cited answer, a refusal for an uncovered
question, a refusal with an empty corpus, the never-quoted Minijob figure, and
the assertion that the Germany check contains no determination.
`evals/` — the `rag_citations` and `retrieval_scope` suites, 25 cases.

---

## 2. Investment advice

### The line

Personal recommendations concerning financial instruments are a regulated
investment service under MiFID II, implemented in Germany through the WpIG and
KWG. A recommendation is personal when it is presented as suitable for that
person, or is based on their circumstances.

### What it does

- **Calculators.** The user supplies the return assumption, the horizon and the
  contribution. The product computes what those inputs imply and labels the
  output illustrative.
- **Objective education.** ETF, index, UCITS, diversification, TER, replication,
  accumulating vs distributing, domicile, fund size, market risk, volatility,
  time horizon — explained factually.
- **A neutral family comparison.** Parent-held vs child-held savings, side by
  side.

### What it never does

- **Suggest a return rate.** The calculator field is the user's assumption, and
  the hint under it says so.
- **Name, rank or compare products.** The ETF section contains no product name;
  a test asserts that.
- **Produce an allocation.**
- **Recommend an account ownership.** `OwnershipComparison.recommended` is
  typed, always `None`, and present as a field so its absence is explicit in the
  API contract rather than merely unimplemented.
- **Execute anything.** There is no broker integration and no order concept.

### How it is enforced

| Mechanism | Where |
|---|---|
| No model is reachable from the calculators — asserted by a test | `services/calculators.py` |
| `recommended: AccountOwnership \| None`, always `None` | `domain/goals.py` |
| Return assumptions outside ±20% are refused rather than rendered | `services/calculators.py` |
| Every projection carries its disclaimer as a field on the result | `domain/goals.py` |
| The ETF response has no field a recommendation could go in | `api/routes/grow.py` |

### A deliberate conservatism

Contributions are applied at the **end** of each month. Assuming they arrive at
the start inflates the final figure by about one month's growth. Small, and
exactly the kind of quiet optimism this product avoids.

Negative returns are permitted, because a tool that only models markets going up
is useless for the scenario people most need to see.

### Tested

`tests/test_keep_and_grow.py` — determinism, conservatism, refused assumptions,
the mandatory disclaimer, no model reachable, no product named, and no
recommended ownership.

---

## 3. Employment and benefits

### The line

Whether a Nebentätigkeit clause is enforceable, and what a benefit recipient
must report, are individual legal questions.

### What it does

- Raises the employment-contract question when the user has told us they are
  employed.
- Shows benefit reporting considerations **only** when the user has explicitly
  disclosed benefit receipt.
- Cites §§ 138 and 155 SGB III for the 15-hour rule and the €165 allowance.

### What it never does

- **Infer benefit status.** `BenefitDisclosure` has an explicit
  `PREFER_NOT_TO_SAY`, defaults to `UNKNOWN`, and the CV extraction schema has
  no field for it — a model could not populate it if it tried.
- **Infer work status** from a CV gap or a job title.
- **Tell anyone whether their clause is enforceable.**

### Tested

`test_benefit_guidance_appears_only_on_explicit_disclosure`,
`test_employer_guidance_appears_only_for_employees`,
`profile.sensitive_fields_are_unreachable` (eval).

---

## 4. Opportunity safety

Not a regulatory line, but the same discipline. The product recommends ways to
earn money to people who want more of it — precisely the audience predatory
schemes target.

`OpportunitySafetyClassifier` blocks prohibited categories deterministically and
flags risk signals without hiding them. Rules, not a model: a decision to
suppress someone's earning opportunity should not vary between runs, and should
be explainable to the source if challenged.

See `DATA_PROVENANCE.md` for the category list.

---

## 5. Ranking integrity

If sponsored placements are ever introduced:

- They will be marked `is_sponsored` and badged in the interface.
- They will be scored by the same deterministic engine as everything else.
- **`MatchScore` has no field for commercial value.** Adding one would be a
  schema change, visible in review, rather than a weight nobody noticed.

Stated in `BUSINESS_MODEL.md` as a commitment, and in `domain/opportunity.py`
as a comment next to the field.

---

## What a reviewer should check

1. `services/calculators.py` — grep for `llm`. Nothing.
2. `services/matching.py` — same. A test asserts it.
3. `domain/legal.py` — the `CitedAnswer` validator.
4. `domain/goals.py` — `recommended` is `None`.
5. `api/routes/grow.py` — the ETF response shape.
6. `services/germany_check.py` — every string is a consideration or a question.
7. `python scripts/tasks.py eval` — 42 cases, including adversarial ones.
