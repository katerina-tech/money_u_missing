# Metrics

Definitions, and where each number actually comes from. `GET /api/metrics`
computes these from real rows.

**A rate is `null` when its denominator is zero.** Not `0%`. No data is not the
same as a zero result, and a table showing 0% for an unmeasured step invites
exactly the wrong conclusion.

---

## Funnel metrics

| Metric | Definition | Numerator / denominator |
|---|---|---|
| **Profile completion** | Did they finish onboarding? | `profile_completed` / `signup_completed` |
| **Money Map activation** | Did they get a map? | `money_map_created` / `profile_completed` |
| **Opportunity relevance** | Did we find something they would have missed? | `feedback[would_not_have_found] ∈ {YES, PARTLY}` / all responses |
| **Would-pursue rate** | Interest, before action | `feedback[would_pursue] ∈ {YES, MAYBE}` / all responses |
| **Save rate** | Interest, revealed | `opportunity_saved` / `opportunity_opened` |
| **Action rate** | Did they start preparing? | `application_prepared` / `opportunity_saved` |
| **Application rate** | Did they actually apply? | `application_marked_applied` / `opportunity_saved` |
| **Win rate** | Did applying work? | `opportunity_won` / `application_marked_applied` |
| **Weekly return rate** | Do they come back? | Distinct users with any event in week *n+1* / in week *n* |

### The two that matter most

**Would-pursue → application rate.** The gap between "I would pursue this" and
"I applied" is the honest measure of whether the product produces action or only
interest. A high save rate with a low application rate means we are building a
bookmarking tool.

**Opportunity relevance rate (H1).** If people are not being shown things they
would have missed, the entire thesis is wrong, and no amount of polish elsewhere
fixes it.

---

## Money metrics

Every one is derived from user-entered figures, never from an advertised range.

| Metric | Definition |
|---|---|
| **Income secured** | Sum of `income_events` where `money_state = SECURED` |
| **Income earned** | Sum where `money_state = EARNED` |
| **Time to first secured income** | Days from `signup_completed` to first `SECURED` event |
| **Realisation ratio** | Recorded amount ÷ the listing's published lower bound, where both exist |

The realisation ratio is the most interesting number this product can produce
and nobody else has. It measures how far advertised compensation is from what
people are actually paid — which is why the outcome form asks for the real
figure instead of pre-filling the advertised one.

---

## Quality metrics

These measure whether the product is being honest, and they are as important as
the funnel.

| Metric | Definition | Where |
|---|---|---|
| **Source verification rate** | Opportunities with `evidence_confidence ∈ {VERIFIED, SOURCE_BACKED}` / all active | `opportunities` |
| **Stale fact rate** | Legal facts not `VERIFIED` after the freshness horizon / all facts | `GET /api/metrics` |
| **Unsupported-claim rate** | Eval cases in `unsupported_claims` + `opportunity_extraction` that fail | `scripts/run_evals.py` |
| **Retrieval scope accuracy** | In-scope answered + out-of-scope declined / all | `retrieval_scope` suite |
| **Injection resistance** | Hostile blocked + benign passed / all | `injection_resistance` suite |
| **Refusal rate** | Tax questions declined / asked | `tax_answer_refused` log events |
| **High-match opportunities per user** | Count with `total_score ≥ 70` | `opportunity_matches` |

### Current values

Measured on this build, 2026-09-04:

| Metric | Value |
|---|---|
| Stale fact rate | 0.23 (3 of 13 unverified — the Minijob figure and two unpopulated registry entries) |
| Unsupported-claim rate | 0/8 cases fail |
| Retrieval scope accuracy | 21/21 |
| Injection resistance | 5/5 attack cases, 5/5 benign cases |
| Source verification rate | 2/16 (the two curated records; the rest are demo) |

The source verification rate is low and that is the honest number: the corpus is
two real programmes. It is the metric that must move first.

---

## Cost metrics

From `llm_usage`, recorded on every call including failures.

| Metric | Definition |
|---|---|
| **Cost per Money Map** | Sum of `estimated_cost_micros` for one discovery run |
| **Cost per user per month** | Sum per user over 30 days |
| **Cost by purpose** | Grouped by `purpose` — extraction, planning, explanation, tax |
| **Failure rate** | `success = false` / all calls |

Cost is `NULL` for a model with no published price in `PRICING_USD_PER_MTOK`
rather than zero, so an unpriced model cannot look free.

**Currently zero**, because the default configuration makes no model calls. That
is a real number for the default deployment and a placeholder for a keyed one.

---

## What is not measured, and why

- **Revenue.** There is none.
- **Retention beyond week one.** Not enough elapsed time.
- **NPS.** A twelve-user sample produces a number with no meaning.
- **TAM.** No defensible bottom-up estimate exists yet; see the one-pager.
- **Outcome-driven ranking quality.** Outcome data is collected but not used —
  per-user counts are too small to be a signal, and `outcome_summary` says so.

---

## Instrumentation

`services/analytics.py` defines the event allowlist. Adding an event means
adding it to `SCHEMA` with its permitted property names and types; anything
else is dropped before it is written. That is what keeps CV text out of the
analytics table, which the schema alone could not.

Events recorded: `signup_completed`, `profile_completed`, `money_map_created`,
`opportunity_search_started`, `opportunities_returned`, `opportunity_opened`,
`opportunity_saved`, `opportunity_dismissed`, `application_prepared`,
`application_marked_applied`, `opportunity_offered`, `opportunity_won`,
`opportunity_lost`, `income_recorded`, `tax_check_viewed`,
`legal_source_opened`, `goal_created`, `child_goal_created`,
`feedback_submitted`.

---

## The next 14 days

The only metrics worth watching while there are a dozen users:

1. **Opportunity relevance rate** — target ≥ 60% YES or PARTLY. Below 40%, the
   thesis is in trouble.
2. **Would-pursue rate** — target ≥ 50% YES or MAYBE.
3. **Application rate** — target ≥ 20%. This is the one that will be lowest and
   the one that matters.
4. **Dismiss reasons, by frequency** — this tells us *which* part is wrong.
   "Too little money" means the sources are wrong. "Not qualified" means the
   matching is wrong. "Already knew it" means the discovery is wrong.
5. **Source verification rate** — must rise from 2 real opportunities.

Everything else is noise at this sample size, and treating it as signal would be
the same error the product refuses to make about opportunities.
