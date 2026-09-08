# Money You're Missing

**One profile. Multiple ways to earn.**

A personal opportunity-to-income engine for skilled professionals in Germany.
One professional profile becomes a prioritised map of *real* earning
opportunities, with the source-backed German administrative context needed to
act on them — and honest accounting of what is not known.

---

## What this is

**The problem.** Income opportunities are fragmented across dozens of unrelated
platforms. Jobs are in one place, freelance work in another, expert networks
somewhere else, and programmes, fellowships and grants are scattered across
hundreds of institutional pages nobody checks. A capable professional who wants
an extra €500–€3,000 a month has to become their own research team.

**The solution.** One profile → real opportunities from real sources → a
deterministic personal match → Germany-specific administrative context → one
recommended next action → tracking from potential through applied to actually
paid.

**What it is not.** Not an idea generator, not a job board, not a ChatGPT
wrapper, and not a tax adviser. The difference is concrete and checkable:
every opportunity in this product exists because a source published it, and
every card links back to that source.

## The one thing to understand about the architecture

**The language model never decides anything.**

It does exactly three jobs: it reads a CV into a structured draft *you* review,
it plans search queries, and it phrases explanations of scores that were already
computed. That is the complete list.

Everything that decides something is ordinary Python:

| Decision | Where it is made | Model involved? |
|---|---|---|
| Match score, and every component of it | `app/services/matching.py` | No — the module cannot even import a provider, and a test asserts that |
| Actionability band | `app/services/actionability.py` | No |
| Safety classification | `app/services/safety.py` | No — deterministic rules, so a suppression can be explained to the source |
| De-duplication | `app/services/dedupe.py` | No |
| Every money figure | `app/services/money_map.py` | No |
| German administrative considerations | `app/services/germany_check.py` | No — built from `LegalFact` rows, not from prompts |
| Savings and child projections | `app/services/calculators.py` | No |

The consequence: the same profile and the same listing always produce the same
score, every component of that score is a sentence you can read, and a listing
cannot argue its way up the ranking because nothing in the ranking reads its
persuasion.

## Unknown means unknown

Most listings do not publish what they pay. Most do not state a time
commitment. Many state requirements ambiguously. A product that filled those
gaps with plausible numbers would be more satisfying and worth considerably
less, because you would have no way to tell which figures were real.

So absence is preserved end to end:

- A missing compensation is `NULL` in the database, `null` on the wire, and
  **"Not published"** in the interface — never `€0`.
- Opportunities with no published pay are counted separately and **excluded
  from every total**, with the exclusion stated next to the total.
- A requirement we cannot evaluate becomes a stated uncertainty on the card,
  never a rejection. `UNKNOWN` is never `false`.
- The goal progress bar moves only on money that has actually been secured or
  earned. Filling it with potential would be the single most dishonest pixel
  this product could draw.
- The Minijob earnings limit is not stated anywhere in this product, because
  § 8 SGB IV gives a *formula* and delegates the figure to a Bundesanzeiger
  publication we have not recorded. The fact row exists, marked unavailable, and
  the answer layer will not quote it.

---

## Getting started

Requires Python 3.12+, Node 22+, and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/katerina-tech/money_u_missing.git
cd money_u_missing
python scripts/tasks.py setup     # or: make setup
python scripts/tasks.py dev       # or: make dev
```

Then open <http://localhost:3000> and click **Build my Money Map**.

**No API keys are required.** With an empty `.env` you get: the full product,
14 demo opportunities plus 7 real curated records, deterministic matching and
actionability, the Germany check with citations, the German knowledge corpus
with lexical retrieval, all calculators, tracking, and the complete test and
evaluation suites.

`make` is optional. Every task has a cross-platform equivalent —
`python scripts/tasks.py <task>` — because `make` is not available on a default
Windows install, and the Makefile delegates to that script rather than
duplicating it.

### Commands

| Task | What it does |
|---|---|
| `setup` | Install both halves, generate data, migrate, seed |
| `dev` | Run the API on :8000 and the web app on :3000 |
| `test` | Backend + frontend unit tests (no network, no paid calls) |
| `e2e` | Playwright end-to-end tests (needs the API running) |
| `eval` | The AI evaluation suite (scripted provider; costs nothing) |
| `check` | Everything CI runs: lint, typecheck, test, eval |
| `reset` | Delete the local database and rebuild it |

---

## Architecture

```
frontend/            Next.js 16, TypeScript strict, Tailwind v4
backend/
  app/
    domain/          Pure data and pure functions. No I/O, no model calls.
    services/        The deterministic engines + model-assisted helpers
    graph/           LangGraph discovery pipeline
    sources/         Pluggable OpportunitySource implementations
    search/          Pluggable SearchProvider implementations
    rag/             Chunking, retrieval, the knowledge store
    llm/             One narrow provider contract, several implementations
    security/        Auth, injection guard, uploads, safe outbound HTTP
    db/              SQLAlchemy models, portable column types
    api/             FastAPI routes, DTOs, mappers
  evals/             The evaluation dataset
docs/                Architecture, provenance, GDPR, metrics, business
```

### The discovery pipeline

```
build_search_plan → search_sources → normalize → deduplicate
  → safety_check → freshness_check → deterministic_match → rank → best_next_move
```

Expressed as a LangGraph graph with conditional early exits, and also available
as a plain function (`run_pipeline`) that is the reference implementation. It is
deliberately *not* a set of agents delegating to each other: multi-agent
structure here would add failure modes and token cost while making the ranking
less reproducible.

### How an opportunity becomes real

```
SOURCE → safety screen → injection screen → structured extraction
  → Pydantic validation → evidence attachment → de-duplication → freshness → match
```

Every step can reject, and rejection is the normal case. A discovery run that
returns four results can account for the other forty, and the interface shows
that accounting rather than hiding it in a log.

### Degradation matrix

The capability endpoint (`GET /api/capabilities`) reports this, and the UI
renders it as a banner rather than offering buttons that fail.

| Missing | Still works | Degrades to |
|---|---|---|
| No LLM key | Matching, scoring, Money Map, Germany check, calculators, tracking, curated + demo discovery | CV extraction offers manual entry; search planning uses templates; explanations fall back to the computed bullet list |
| No search key | Everything above | Discovery uses curated + demo datasets, and says so |
| No `DATABASE_URL` | Everything | Local SQLite with numpy vector search |
| No `local-embed` extra | Retrieval | BM25 lexical retrieval, which is strong on this corpus |
| Empty corpus | Everything else | Tax questions are declined rather than answered |

---

## Data sources

### Real, verified (2 records)

Recorded by hand from each programme's own page on 2026-09-04:

- **EXIST-Gründerstipendium** — compensation fields `null`, because the page
  does not state the amounts.
- **EXIST-Forschungstransfer** — same.

Those nulls are the point. Publishing a plausible stipend figure for a real
federal programme is precisely the failure this product exists to avoid.

### Demo (14 records)

Fictional, invented organisation names, `is_demo: true` on every record, and a
database CHECK constraint that forbids a demo record from claiming verified
compensation. Badged **DEMO** everywhere it appears.

### German legal knowledge (10 documents, 13 facts)

Retrieved from [Gesetze im Internet](https://www.gesetze-im-internet.de/) on
2026-09-04: § 19 and § 14 UStG, § 4, § 18, § 20 and § 32a EStG, § 14 GewO,
§ 138 AO, § 8 SGB IV, §§ 138 and 155 SGB III.

Ten facts are `VERIFIED`. Three are deliberately **not**: the Minijob figure
(formula only in the statute), Künstlersozialkasse conditions, and the
Übungsleiterfreibetrag amounts. They are listed with `content_available: false`
so the gap is visible, and they are never quoted.

Two RSS feeds are registered and **disabled**: the EU Funding & Tenders feed URL
returns 404, and the Förderdatenbank RSS page is a JavaScript shell with no
discoverable feed. Both were checked; `GET /api/provenance` reports them as
pending verification rather than pretending they work.

### What is never done

No login bypass, no CAPTCHA solving, no paywall circumvention, no private APIs,
no LinkedIn/Indeed/Xing/Glassdoor scraping (host-blocked in code). robots.txt is
respected, requests are rate-limited per host, and every fetch is SSRF-checked,
size-capped and content-type-checked.

---

## Security

| Control | Where |
|---|---|
| Argon2id password hashing, constant-work verification | `security/auth.py` |
| JWT access + server-side revocable, rotating refresh tokens | `security/auth.py` |
| Five-layer prompt-injection defence (normalise, score, classify, structure, schema) | `security/guard.py` |
| SSRF prevention with per-hop DNS re-validation | `security/web.py` |
| Upload validation: size, extension, declared type, magic bytes | `security/uploads.py` |
| Two-bucket rate limiting (browsing vs. spend) | `security/ratelimit.py` |
| Security headers, restrictive CSP, CORS allowlist | `main.py`, `ratelimit.py` |
| Per-user isolation — no route takes a user id from the request | `api/deps.py` |
| Validation errors never echo the submitted value | `main.py` |

The injection defence is layered rather than pattern-based, and the two layers
that matter most are not detection at all: untrusted content never enters a
system message, and every model response is a closed Pydantic schema — so a
successful injection cannot produce a field the system acts on.

Policy differs by provenance on purpose. A retrieved web page that looks like an
attack is dropped. A *user's own CV* that trips the same heuristics is processed
anyway, because refusing to help a security engineer find work is the worse
failure.

---

## Privacy and GDPR

- **Deletion is real.** Every personal table cascades from `users.id`. Account
  deletion is one `DELETE`, not a checklist someone forgets to update. Tested.
- **CV deletion removes the file *and* the extracted text.**
- **Consent is recorded verbatim**, shown back to the user, and withdrawable.
- **Analytics cannot leak**: every event has an allowlist of property names and
  types; anything else is dropped. Income is stored as a bucket, never a figure.
- **Logs never contain documents**: CV text and tax questions are reduced to a
  length and a truncated hash — not even a preview, because the opening lines of
  a CV are the identifying ones.
- **The search planner does not receive your identity** — only skills, role,
  languages, location and availability.
- **No training on your data.** Stated in the consent text and in the code.
- **EU region recommended** for the database; see `docs/GDPR_DATA_MAP.md`.

---

## AI boundaries

- Never invents compensation, deadlines, organisations, eligibility, tax
  treatment or legal requirements.
- Never answers a regulatory question it cannot cite. `CitedAnswer` refuses to
  validate an answered response with no citations, so this holds even if the
  prompt were subverted.
- Never gives personalised investment advice. The GROW calculators take *your*
  assumptions; the ETF section explains terminology and names no product; the
  family comparison has no recommended option and no field for one.
- An explanation that drops the stated uncertainties is discarded and the
  computed bullet list is shown instead — there is an eval for it.

---

## Testing

| Suite | Count | Command |
|---|---|---|
| Backend unit | 180 | `tasks.py test-backend` |
| Frontend unit | 25 | `tasks.py test-frontend` |
| End-to-end | 9 | `tasks.py e2e` |
| AI evaluation | 42 | `tasks.py eval` |

**No test makes a paid model call or a network request.** Everything runs
against `ScriptedProvider` and `FailingProvider`, which is what makes it
reasonable to run on every commit.

The evaluation scripts are deliberately *adversarial*: they script the model
doing the wrong thing — inventing a salary, following an injected instruction,
dropping the caveats — and check that the surrounding system catches it. An eval
that only scripts correct output measures nothing.

Backend is `mypy --strict` clean across 78 files. Strict mode is relaxed only
for `app.api.*` and `app.graph.workflow`, where FastAPI's `Depends()` defaults
and LangGraph's node overloads cannot be followed without more casts than the
safety is worth; those layers are covered by the API tests instead.

---

## Deployment

Both halves ship as containers with health checks and non-root users, and
`railway.json` for each.

```bash
python scripts/tasks.py docker-build
```

**Backend.** Set `MYM_DATABASE_URL` (Postgres, EU region), `MYM_JWT_SECRET`,
`MYM_ENVIRONMENT=production` and `MYM_CORS_ORIGINS`. The app refuses to start in
production without a signing key or with `*` CORS. Migrations run in the
entrypoint — correct for a single instance, and flagged in the script as a
decision to revisit at multiple replicas.

**Frontend.** `NEXT_PUBLIC_API_BASE_URL` is a **build argument**, not a runtime
variable: Next inlines `NEXT_PUBLIC_*` at build time, and setting it only at
runtime produces an image whose browser code calls localhost.

See `docs/ARCHITECTURE.md` for the full deployment notes.

---

## Environment variables

Every one is optional. See `.env.example` for the annotated list.

| Variable | Default | Effect if unset |
|---|---|---|
| `MYM_DATABASE_URL` | SQLite file | Local file database |
| `MYM_JWT_SECRET` | ephemeral | Sessions end on restart; refuses to boot in production |
| `ANTHROPIC_API_KEY` | — | CV extraction, planning and explanations degrade |
| `MYM_SEARCH_PROVIDER` + key | `none` | Curated + demo datasets only |
| `MYM_EMBEDDING_BACKEND` | `lexical` | BM25 retrieval |
| `MYM_CORS_ORIGINS` | `http://localhost:3000` | — |
| `MYM_DEMO_MODE_ENABLED` | `true` | — |
| `MYM_PAYMENTS_ENABLED` | `false` | — |

---

## Known limitations

Stated plainly, because a limitations section that lists only comfortable
problems is worse than none.

1. **Seven real opportunities.** The curated dataset holds seven verified
   programmes. Everything else is demo data. The pipeline that would ingest more
   is built and tested; the corpus is small because each entry means a person
   read a page.
2. **No live source is enabled by default.** Both candidate RSS feeds failed
   verification. Live discovery requires a search API key.
3. **The skills graph is hand-written.** It knows what has been typed into it
   (~130 skills). A skill outside it gets no related-skill credit. That is
   visible and fixable; a model-generated graph would be invisible and wrong.
4. **Eligibility evaluation is narrow.** `_evaluate_requirement` recognises a
   handful of conditions the profile actually answers and returns "cannot tell"
   for everything else. Deliberate: confident wrong answers about someone's
   eligibility are the one error with a real cost.
5. **Rate limiting is in-process.** Behind two replicas the effective limit
   doubles. Correct for a single-container MVP; the interface is one constructor
   away from Redis.
6. **No German UI yet.** All copy is centralised in `lib/copy.ts` and the
   backend corpus handles German terms, but the interface ships in English.
7. **Outcome data does not yet influence ranking.** It is collected; per-user
   counts are too small to be a signal, and `outcome_summary` says so rather
   than pretending.
8. **`estimated_hours` is always per week.** A source stating total project
   hours would need converting during extraction; the extraction prompt says to
   leave it null instead.
9. **Willingness to pay is unmeasured.** The pricing page says so.

## What was deliberately not built

Automatic applications, automatic tax filing, bank or broker integration,
accounting integrations, a CRM, escrow, mobile apps, email infrastructure,
and multi-agent orchestration. Each would add surface area before the core
hypothesis is validated. See `docs/ROADMAP.md`.

---

## Documentation

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, the AI/deterministic split, deployment |
| [DATA_PROVENANCE.md](docs/DATA_PROVENANCE.md) | Every source, its access basis, and what is refused |
| [REGULATORY_BOUNDARIES.md](docs/REGULATORY_BOUNDARIES.md) | Tax, legal and investment lines, and how they are enforced |
| [GDPR_DATA_MAP.md](docs/GDPR_DATA_MAP.md) | Data collected, purpose, retention, deletion path |
| [METRICS.md](docs/METRICS.md) | Metric definitions and how each is computed |
| [VALIDATION_PLAN.md](docs/VALIDATION_PLAN.md) | Hypotheses, the first-20 user test, what would falsify them |
| [BUSINESS_MODEL.md](docs/BUSINESS_MODEL.md) | Pricing hypothesis, unit economics, what we will not sell |
| [COMPETITOR_ANALYSIS.md](docs/COMPETITOR_ANALYSIS.md) | Categories, honest overlaps, the wedge |
| [ACCELERATOR_ONE_PAGER.md](docs/ACCELERATOR_ONE_PAGER.md) | The summary, with TODOs where evidence does not exist |
| [PITCH_DECK_OUTLINE.md](docs/PITCH_DECK_OUTLINE.md) | Ten slides |
| [ROADMAP.md](docs/ROADMAP.md) | P0 / P1 / P2 |
| [DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | The 90-second walkthrough |

---

## Status

A validation-stage MVP. No users, no revenue, no traction. The product is
instrumented to find out whether it helps: two questions in the interface, a
feedback table, and an analytics funnel with defined metrics.

Nothing in this repository claims otherwise.
