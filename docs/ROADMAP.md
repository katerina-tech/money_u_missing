# Roadmap

Every P0 decision had to answer one question:

> *Does this improve our ability to help a professional discover and act on a
> legitimate income opportunity they would otherwise miss?*

If not, it was not P0.

---

## P0 — validation MVP (built)

| Area | Status |
|---|---|
| Email/password auth, sessions, refresh rotation, logout, account deletion | Done |
| CV upload / paste / manual onboarding, with a mandatory human review step | Done |
| Money Map with state-separated money and stated exclusions | Done |
| Pluggable `OpportunitySource` architecture — demo, curated, RSS, search API, public API | Done |
| Pluggable `SearchProvider` — Tavily, Brave, Serper, null, stub | Done |
| Deterministic matching with ten weighted components and explainable details | Done |
| Actionability, separate from fit | Done |
| Opportunity detail: why it matches, what we know, what we don't, Germany check | Done |
| Save, dismiss with reason, action workspace, tracking state machine | Done |
| Income recording, Money Map integration | Done |
| Versioned `LegalFact` registry with freshness horizons | Done |
| RAG over German legislation, with citations and refusals | Done |
| GROW: goals, deterministic calculators, ETF education | Done |
| FAMILY: child goals, neutral ownership comparison | Done |
| Feedback instrument and analytics with a property allowlist | Done |
| Demo mode with a fictional professional | Done |
| Landing page, privacy, about, pricing | Done |
| Personal page: baseline income (gross/net kept apart), recorded costs, household context | Done |
| KEEP direction: deterministic "money you may be losing" findings, each cited or silent | Done |
| Docker, Railway configs, health checks | Done |
| 244 + 25 + 12 tests, 42 evals, curated-data gate | Done |

### P0 gaps, honestly

These are P0 in spirit and not finished:

1. **The curated dataset holds seven opportunities.** The pipeline is built,
   tested and gated; the corpus is small because each entry means a person read
   a page. **This is still the single most important thing to fix**, because H1
   is untestable without it. What changed: records are one JSON file each rather
   than a Python literal, and `scripts/validate_curated.py` fails the build if a
   compensation figure is not quoted from its source page.
2. **No live source is enabled.** Both candidate RSS feeds failed verification —
   one 404s, one is a JavaScript shell. Live discovery needs either a working
   feed or a search API key.
3. **Notification architecture exists as a table; nothing writes to it.**
   In-app notifications were scoped as P0-optional and were not built.

---

## P1 — traction

Ordered by what unblocks validation first.

1. **Expand the curated dataset from seven to ~30 real opportunities.** Manual,
   deliberate, with a source URL, a read date and a quoted excerpt for each.
   Nothing else in P1 matters more.
2. **Enable one verified live source.** Candidates: a working public funding
   feed, a university Lehrauftrag portal with a documented API, or a licensed
   search key. Each needs a recorded access basis before it ships.
3. **Scheduled refresh.** A daily discovery run per active profile, so H3 has
   something to measure.
4. **Email alerts** for high-match opportunities and approaching deadlines. The
   notification table and the events already exist.
5. **Demo account cleanup.** Each demo session creates a real account; they
   accumulate. A retention job, and a decision on how long a demo lives.
6. **Retention policy for inactive accounts**, and the notification flow that
   precedes deletion.
7. **German UI.** All copy is centralised in `lib/copy.ts` and the corpus already
   handles German terms. This is a translation task, not a refactor — which is
   what "localisation-ready" has to mean to be worth claiming.
8. **Application workspace depth** — attachments, richer reminders, per-document
   checklists.
9. **Subscription**, behind the existing `MYM_PAYMENTS_ENABLED` flag. Only after
   H1 is supported.
10. **Outcome-driven ranking.** At roughly 50 outcomes per category, category
    win-rate becomes a signal rather than noise. Until then `outcome_summary`
    says so.
11. **Redis-backed rate limiting**, when there is more than one instance.

---

## P2 — scale

- **DACH expansion.** Austria and Switzerland need their own `LegalFact`
  registries and knowledge corpora. The jurisdiction field and the scope gate
  already exist; the corpora do not.
- **B2B2C.** Career platforms, universities, professional bodies. The matching
  engine is profile-agnostic and the sources are pluggable, so the technical
  work is an organisation model and an admin surface.
- **Partner APIs** — direct integrations with expert networks and programme
  operators, replacing page-reading with structured feeds.
- **Automated opportunity ingestion at scale**, with a human review queue rather
  than fully automatic publication.
- **Advanced income portfolio** — cadence, seasonality, concentration risk.
- **Accounting integrations** (sevDesk, lexoffice) for users who cross into
  regular freelance income.
- **Approved financial partnerships**, subject to the ranking-integrity
  commitment in `BUSINESS_MODEL.md`.

---

## Deliberately not built

Each of these would add surface area before the core hypothesis is validated.

| Not built | Why |
|---|---|
| Automatic applications | Submitting on someone's behalf is a trust and liability step that must follow validation, not precede it |
| Automatic tax filing | Regulated, and squarely outside our boundary |
| Broker or bank integration | Regulated, and the product does not need account access to work |
| Automatic grant submission | Same as automatic applications, with higher stakes |
| Complex accounting | Adjacent products do it better; partnership beats rebuilding |
| Full CRM | The action workspace covers the actual need |
| Marketplace escrow | We are not a marketplace |
| Social network | No |
| Mobile-native apps | The web app is responsive; native adds cost before there is retention to protect |
| Crypto | No |
| Multi-agent orchestration | Would add failure modes and token cost while making the ranking less reproducible — the opposite of what this product needs |

---

## The next five priorities

In order. Everything above is context for this list.

1. **Thirty real curated opportunities.** Without them, H1 is untestable and the
   product demonstrates a mechanism rather than a service.
2. **One working live source**, so refresh yields something new and H3 becomes
   measurable.
3. **Twenty user sessions** following `VALIDATION_PLAN.md`, with the dismiss
   reasons read daily.
4. **Scheduled refresh and one alert type**, so returning has a reason.
5. **Cost per Money Map, measured** from `llm_usage`, so the business model
   stops being arithmetic and starts being data.
