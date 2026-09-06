# Architecture

## The organising decision

Everything in this system follows from one choice: **a language model may read
and phrase, but never decide.**

That is not a stylistic preference. The product's value proposition is that its
opportunities are real and its scores are defensible. A model that could set a
match score would make both unfalsifiable — the score would drift between runs,
could not be explained component by component, and could be influenced by the
persuasive language of the listing being scored.

So the system is split cleanly:

| Layer | Implementation | Model? |
|---|---|---|
| Reading a CV into a draft | `services/cv_parsing.py` | Yes — output is a `ProfileDraft`, a different type from `UserProfile`, which the user must confirm |
| Planning search queries | `services/search_planner.py` | Yes — produces queries, never records |
| Reading a retrieved page | `services/normalize.py` | Yes — into a closed schema where every field is nullable |
| Phrasing a computed score | `services/explanation.py` | Yes — cannot change a number, and is discarded if it drops the caveats |
| Drafting application text | `api/routes/actions.py` | Yes — reviewed and sent by the user |
| Composing a cited tax answer | `services/tax_education.py` | Yes — only from retrieved passages |
| **Match scoring** | `services/matching.py` | **No** |
| **Actionability** | `services/actionability.py` | **No** |
| **Safety classification** | `services/safety.py` | **No** |
| **De-duplication** | `services/dedupe.py` | **No** |
| **All money arithmetic** | `services/money_map.py`, `domain/money.py` | **No** |
| **Germany check** | `services/germany_check.py` | **No** |
| **Calculators** | `services/calculators.py` | **No** |
| **Preference learning** | `services/learning.py` | **No** |

`tests/test_matching.py::test_no_language_model_is_reachable_from_matching`
asserts the split by inspecting the module source. It is cheap and it catches
the exact regression that would matter.

---

## Layers

```
frontend/  ── Next.js 16 App Router, TypeScript strict, Tailwind v4
    │           renders what the API reports, including what it does not know
    ▼  HTTP + JWT
backend/app/
  api/       routes, DTOs, mappers, dependencies (auth, rate limits, sessions)
  graph/     the discovery pipeline as a LangGraph graph
  services/  the engines — deterministic and model-assisted, clearly separated
  sources/   OpportunitySource implementations (demo, curated, RSS, search, API)
  search/    SearchProvider implementations (Tavily, Brave, Serper, null, stub)
  rag/       chunking, BM25 + optional dense retrieval, the knowledge store
  llm/       one narrow provider contract; Anthropic, OpenRouter, scripted, null
  security/  auth, injection guard, uploads, safe outbound HTTP, rate limits
  domain/    pure data and pure functions — no I/O, no model calls
  db/        SQLAlchemy models, portable column types, engine and sessions
```

`domain/` has no dependency on anything below it. That is what makes the
matching and money rules cheap to pin down exhaustively: every case in
`test_matching.py` and `test_money.py` constructs its inputs directly, with no
database and no fixtures.

---

## The discovery pipeline

```
              ┌──────────────────────┐
              │  build_search_plan   │  model, or templates when unavailable
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │   search_sources     │  curated → RSS → search API → demo
              └──────────┬───────────┘  (exit if nothing)
                         ▼
              ┌──────────────────────┐
              │      normalize       │  safety → injection → extract → validate
              └──────────┬───────────┘  (exit if nothing)
                         ▼
              ┌──────────────────────┐
              │     deduplicate      │  canonical URL, then org+title+deadline,
              └──────────┬───────────┘  then bounded fuzzy within one org
                         ▼
              ┌──────────────────────┐
              │     safety_check     │  re-run after merges
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │   freshness_check    │  (exit if nothing)
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │ deterministic_match  │  no model reachable
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │        rank          │  fit 0.7 + actionability 0.3
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │   best_next_move     │  exactly one recommendation
              └──────────────────────┘
```

### Why LangGraph, and why not agents

The pipeline genuinely is a graph: it has conditional edges and three early
exits where continuing would produce a misleading "0 matches" instead of an
honest "no sources returned anything". Expressing that as a graph makes the
sequence inspectable — `workflow.describe()` returns the stage list, which is
what this document and the demo script quote.

What it is deliberately *not* is a set of agents delegating to each other.
Multi-agent structure here would add failure modes, multiply token cost, and
make the ranking less reproducible — the opposite of what the product needs. The
graph degrades to a plain function call (`run_pipeline`) if LangGraph is
unavailable, and that plain version is the reference implementation.

### Ordering matters

Sources are queried curated-first because de-duplication keeps the
best-evidenced record. A curated entry a human read should win over a search
snippet about the same listing, and `_quality()` in `dedupe.py` encodes exactly
that.

---

## How an opportunity becomes real

```
OpportunityCandidate            ← raw, untrusted, from a source
        │
        ├─ safety classification (before any model call — a blocked listing
        │    costs nothing and is never summarised persuasively)
        │
        ├─ injection screening (retrieved pages fail closed)
        │
        ├─ structured extraction into ExtractedOpportunity
        │    every field nullable; the prompt says null is a correct answer
        │
        ├─ Pydantic validation → Opportunity
        │
        ├─ evidence attachment (SourceRef, Confidence — never VERIFIED here)
        │
        └─ re-run safety on the extracted text
```

File-backed sources (curated, demo) skip extraction entirely: their JSON is
already structured. That path is what proves the pipeline does not *require* a
model, and it is the path the offline demo uses.

`Confidence` can never reach `VERIFIED` through this pipeline. That requires a
human re-check, recorded separately.

---

## Data model

25 tables. Three properties are designed in:

**Deletion is real.** Every table holding personal data hangs off `users.id`
with `ondelete="CASCADE"`. Account deletion is one `DELETE`. `opportunities`
deliberately does *not* cascade — an opportunity is public information about the
world, not about the user — and the join tables that connect them do.

**Unknown survives storage.** Nullable columns mean unknown. There are no
sentinel zeroes and no `NOT NULL DEFAULT 0` on a money column, because a zero
meaning "not published" is indistinguishable from a zero meaning "unpaid" the
moment it leaves the schema file.

**Money is integer cents.** No `FLOAT` anywhere near an amount.

Two CHECK constraints carry product rules into the storage layer:

- `ck_demo_cannot_be_verified` — a demo record cannot claim verified pay.
- `ck_active_stream_is_committed` — an income stream is only `ACTIVE` when its
  money state is `SECURED` or `EARNED`.
- `ck_income_is_committed` — an income event is only ever `SECURED` or `EARNED`.

### Portability

One environment variable decides everything. `MYM_DATABASE_URL` unset gives
SQLite; set gives Postgres with pgvector. The portability is confined to
`db/base.py` — three custom column types and one capability probe. No
repository, service or route contains a dialect branch.

`UtcDateTime` exists because SQLite has no timezone type and returns naive
datetimes regardless of `timezone=True`. Since the entire freshness and
staleness system is built on subtracting stored timestamps from
`datetime.now(UTC)`, that difference is invisible until it raises — or worse,
until a comparison silently succeeds against a local-time value.

---

## Retrieval

**Lexical by default.** BM25 in numpy, always available, no model download, no
key, no network. For a corpus of a few hundred chunks of German tax guidance
whose queries contain the exact terms the documents use — *Kleinunternehmer­
regelung*, *Fragebogen zur steuerlichen Erfassung* — BM25 is extremely strong,
and it is explainable when it goes wrong.

Two additions were needed for German:

- **Umlaut folding.** `Nebentätigkeit` and `Nebentaetigkeit` must be the same
  token. Without it, a question typed on a non-German keyboard misses a document
  entirely about its subject.
- **Compound expansion.** German compounds freely; BM25 matches tokens exactly.
  A query for `Nebentaetigkeit` retrieved *nothing* from a document whose every
  paragraph says `Nebentaetigkeitsklausel`. Query terms with no exact match are
  expanded to vocabulary terms that contain them, at a discount.

**Scope gates.** Retrieval always returns its top-k, so "how do I bake sourdough
bread" gets a best match too — and a question about Portuguese capital gains
scores *higher* than a good German one, because it shares the vocabulary. Two
gates handle this: a named-jurisdiction check (we hold German law only) and a
requirement that at least one distinctive query term appears in the retrieved
passages. Measured at 21/21 on the `retrieval_scope` eval suite, which tests
both directions.

**Dense retrieval is an upgrade, not a requirement.** `MYM_EMBEDDING_BACKEND=local`
uses fastembed on-device; `openai` uses a hosted endpoint. When present, results
are fused by reciprocal rank — chosen over score-weighted fusion because BM25
scores and cosine similarities are not on comparable scales.

---

## Security architecture

### Prompt injection: five layers

1. **Normalisation** — NFKC, strip invisible and direction-control characters,
   fold homoglyphs, decode and inspect base64 blocks. Obfuscation is removed
   before anything inspects the text.
2. **Weighted heuristics** — a score, never a verdict. One phrase should not
   condemn a legitimate CV; several together warrant a look.
3. **A model classifier** — consulted only above a threshold, so cost is paid on
   suspicious input. A provider refusing the text on content grounds is folded
   in as *evidence about the text*, not treated as an outage.
4. **Structure** — untrusted content only ever appears inside a fenced `user`
   message, after fence tokens inside it have been defanged.
5. **Output validation** — every response is a closed Pydantic schema.

Layers 4 and 5 are the ones that matter. A successful injection has no channel
through which to act: it cannot become a system instruction, and it cannot
produce an output field the schema does not declare.

**Policy differs by provenance, deliberately.** Uploaded files and retrieved
pages fail closed. The user's own text and our own curated corpus fail open with
a log — because refusing to process a CV that contains the word "ignore" is a
worse failure than reading a hostile one that structure already contains.

### Outbound HTTP

`SafeFetcher` is the only way third-party content enters the system. Redirects
are followed manually so every hop is re-validated: a redirect to
`http://169.254.169.254/` is the whole point of the attack, and a normal client
follows it happily. Size is enforced while streaming, not from `Content-Length`,
which can simply be omitted.

---

## Deployment

Two containers, each non-root with a health check.

**Backend.** Multi-stage; `uv sync --frozen` fails rather than silently
resolving something different from what the tests ran against. Migrations run in
the entrypoint — the right trade at one instance, because the schema can never
be behind the code, and the wrong trade at multiple replicas where concurrent
migrations race. The entrypoint says so, so the decision is revisited rather
than inherited.

**Frontend.** `NEXT_PUBLIC_API_BASE_URL` is a build argument. Next inlines
`NEXT_PUBLIC_*` at build time; setting it only at runtime yields an image whose
browser code calls localhost — a failure that presents as CORS and is not.

**Production refuses to start** without an explicit `MYM_JWT_SECRET`, without
`MYM_DATABASE_URL`, or with `*` in CORS origins.

### Recommended production configuration

```
MYM_ENVIRONMENT=production
MYM_DATABASE_URL=postgresql+psycopg://…   # EU region — see GDPR_DATA_MAP.md
MYM_JWT_SECRET=<48+ random bytes>
MYM_CORS_ORIGINS=https://app.example.com
MYM_LOG_FORMAT=json
ANTHROPIC_API_KEY=…                        # optional
MYM_SEARCH_PROVIDER=tavily                 # optional
MYM_EMBEDDING_BACKEND=local                # optional
```

---

## Observability

Structured JSON logs with a closed event enum (`logging_config.Event`). Every
model call records provider, model, purpose, tokens, latency, success and
estimated cost into `llm_usage` — including failures, because a provider that
only bills the happy path makes retries invisible in cost reporting.

Never logged: CV text, tax questions, full prompts, API keys, tokens. User ids
appear only as a salted 12-character hash.

Cost is `NULL` rather than zero for a model with no published price here — a
zero would sum silently into a dashboard and make an unpriced model look free.

---

## Known architectural limits

1. **Rate limiting is in-process.** Per-instance, so two replicas double the
   effective limit. Correct for one container; the interface is one constructor
   away from Redis.
2. **The BM25 index is in-memory**, rebuilt lazily. Correct under a megabyte of
   corpus; at a hundred thousand chunks this moves into Postgres full-text.
3. **`mypy --strict` is relaxed for `app.api.*` and `app.graph.workflow`.**
   FastAPI's `Depends()` defaults and LangGraph's node overloads cannot be
   followed without more casts than the safety is worth. Scattering `type:
   ignore` through the routes would hide real errors among the noise. Those
   layers are covered by the API tests.
4. **The demo creates a real account per session.** Simple and correct, and it
   accumulates rows. A cleanup job is P1.
