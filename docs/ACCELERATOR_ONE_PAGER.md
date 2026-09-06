# Money You're Missing — one-pager

**One profile. Multiple ways to earn.**

A personal opportunity-to-income engine for skilled professionals in Germany.

---

## Problem

Income opportunities are fragmented across dozens of unrelated platforms. Jobs
are in one place, freelance work in another, expert networks somewhere else, and
programmes, fellowships and grants are scattered across hundreds of
institutional pages nobody checks. A capable professional who wants an extra
€500–€3,000 a month has to become their own research team — and then still has
to work out what a freelance engagement means for their employment contract,
their tax registration and their VAT position.

Most give up, or default to the one channel they already know.

## Target customer

Skilled professionals living in Germany — employed, freelance, or both — who
want to increase or diversify their income and do not have hours to spend
searching. Initial goal range €500–€3,000 per month.

Not students, not job-seekers looking for a new full-time role, not microtask
workers.

## Solution

One professional profile becomes a prioritised map of real earning
opportunities, each with a transparent match score, an honest statement of what
is not known, the German administrative questions it raises, and one recommended
next action — then tracked from potential through applied to actually paid.

## Why now

- Professional earning opportunities are increasingly fragmented across
  categories that did not exist as consumer channels a decade ago.
- Language models can now structure a complex professional profile and read
  unstructured opportunity pages reliably enough to be useful — *if* they are
  constrained to reading rather than deciding.
- Search infrastructure makes cross-source discovery technically feasible for a
  small team.
- Structured eligibility and outcome data compounds: knowing what people
  actually pursued and won is a dataset nobody currently holds.
- German administrative complexity creates a decision-support problem that a
  generic international product cannot solve.

## Product

Three layers, weighted roughly 70/20/10:

- **EARN** — discover, match, prioritise, act, track. The product.
- **KEEP** — source-backed German tax and administrative context, attached to
  the opportunity that raises it.
- **GROW** — connect additional income to goals, with deterministic calculators.

## Market wedge

Germany · skilled professionals · additional income · professional-grade
opportunities. Then DACH, then EU markets with comparable administrative
complexity — where the complexity is the moat rather than the obstacle.

**TAM: TODO.** No defensible bottom-up estimate exists. Producing one would
require German employment data segmented by profession and income intent, and an
invented number would contradict the product's central claim.

## Business model

Free tier that genuinely works; Pro at a hypothesised €9–€19/month for
continuous discovery, alerts, the full action workspace and tracking. Later,
B2B2C licensing to career platforms, universities and professional bodies.

**Willingness to pay is unmeasured.** No payment flow exists; payments are
behind a feature flag and off.

## Competition

Side-hustle generators produce ideas, not opportunities. Job and freelance
platforms each cover one category. Aggregators cover one vertical. German tax
apps engage after income exists. Personal finance apps look backwards.

No one covers the intersection: **real cross-category opportunities +
deterministic personal matching + German administrative context + action
workflow + outcome tracking.** The individual cells are not novel; the
combination is, and it only holds if the execution does.

The most credible threat is a German tax app adding an opportunity layer — it
already owns the administrative relationship and the trust.

## Differentiation

**The language model never decides anything.** It reads a CV into a draft you
confirm, plans search queries, and phrases scores that were already computed.
Every decision — match, actionability, safety, de-duplication, all money
arithmetic, the Germany check — is ordinary Python. Same inputs, same score,
every time, and every component is a sentence you can read.

**Unknown stays unknown.** Missing compensation is "Not published", never €0.
Opportunities with no published pay are counted separately and excluded from
totals, with the exclusion stated. The goal bar moves only on money actually
secured. A requirement we cannot check becomes a stated uncertainty, never a
rejection.

**The Germany check** attaches administrative considerations and specific
questions — sourced from stored legislation with retrieval dates — to the
opportunity that raises them.

## Technology

Next.js 16 / TypeScript strict · FastAPI / Python 3.12 / Pydantic / SQLAlchemy /
Alembic · Postgres + pgvector with a working SQLite fallback · LangGraph
discovery pipeline · pluggable opportunity sources and search providers ·
five-layer prompt-injection defence · BM25 retrieval with German umlaut folding
and compound expansion.

**Runs with zero credentials.** 180 backend tests, 25 frontend tests, 9 e2e
tests, 42 AI evaluation cases — none of which makes a paid model call.
`mypy --strict` clean.

## Moat hypothesis

Not the AI. Four things that compound, none of which we have yet:

1. **Opportunity graph** — structured, de-duplicated, multi-category records
   with provenance.
2. **Eligibility graph** — profile-to-opportunity constraints, structured.
3. **Outcome data** — what people actually pursued, and what it actually paid.
   The gap between advertised and real compensation is a dataset nobody holds.
4. **European compliance knowledge** — versioned, source-backed, jurisdiction-
   specific.

**Stated as strategy, not as achievement.** Today the opportunity graph holds
two real records.

## Validation

**Nothing is validated.** No users, no revenue, no interviews.

The product is instrumented to find out: two questions in the interface *("Did
we show you something you would not have found?"* / *"Would you pursue this?"*),
a feedback table, a dismiss-reason taxonomy, and a defined metric set. See
`VALIDATION_PLAN.md` for the hypotheses and what would falsify each.

## Roadmap

**P0 (built).** Auth, CV onboarding, Money Map, source architecture,
deterministic matching, actionability, opportunity detail, action tracking,
Germany check, RAG, feedback, analytics, demo, landing page.

**P1 (next).** Expand the curated dataset to ~30 real opportunities; enable one
verified live source; scheduled refresh and email alerts; demo cleanup;
subscription behind the existing flag.

**P2.** DACH expansion, B2B2C, partner APIs, automated ingestion, outcome-driven
ranking.

## Team

**TODO.** No team information is asserted here.

## Ask

**TODO.** No funding amount, use of funds or milestone commitment is asserted
here.

---

*Status: validation-stage MVP. Demo data is labelled DEMO throughout. The
curated dataset holds two real programmes, both with null compensation, because
their pages do not state the amounts.*
