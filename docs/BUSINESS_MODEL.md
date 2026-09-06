# Business model

A hypothesis, not a plan. Nobody has paid for this, so there is no evidence
about willingness to pay and this document does not pretend otherwise.

---

## The hypothesis

**Free**

Profile and CV extraction · the first Money Map · a limited set of
opportunities · the Germany check · Tax & Rules with citations · goals and
calculators.

Enough to be genuinely useful, because a free tier that does not work is not a
funnel — it is a demo with a paywall.

**Pro — €9–€19 per month**

Continuous discovery rather than on demand · alerts on high-match opportunities
· the full action workspace and drafts · advanced Money Map and income
portfolio · outcome tracking over time.

**The price range is a guess.** It brackets what a professional pays for a
productivity subscription and sits well below what one additional €500 month
would justify. That reasoning is plausible and unevidenced.

### Why subscription rather than commission

Commission on placements would be the obvious model and it is the wrong one
here. It would create a direct incentive to rank opportunities by what pays us
rather than what fits the user, in a product whose entire value is that the
ranking is defensible. `MatchScore` has no field for commercial value; adding
one would be a visible schema change rather than a weight nobody noticed.

---

## Unit economics

### Cost per user

The expensive path is a discovery run: search-API calls plus model extraction
per fetched page.

| Component | Per run | Notes |
|---|---|---|
| Search API | ~6 queries | Tavily's pricing tier at low volume |
| Page fetches | ≤ 12 | Capped in `MAX_PAGES_PER_RUN` |
| Extraction | ≤ 12 calls | ~4k input, ~600 output tokens each |
| Planning | 1 call | ~1k input |
| Explanations | ~8 calls | Low effort, short output |

**We are not putting a euro figure here.** Token counts depend on page length,
model choice and effort level, and a made-up number in a unit-economics table is
worse than an empty cell — which is exactly why `estimate_cost_micros` returns
`NULL` for a model with no published price rather than zero.

What *is* built is the measurement: `llm_usage` records provider, model,
purpose, tokens, latency and cost on every call including failures. After a week
of real usage, `GET /api/metrics` produces cost per Money Map from data instead
of arithmetic.

### The levers, in the order they will be used

1. **Effort per purpose.** Already implemented: classification runs at `low`,
   extraction at `medium`, tax answers at `high`. A global default of `high`
   is how an MVP's economics quietly become indefensible.
2. **Safety screening before extraction.** A blocked listing costs nothing —
   the classifier runs before any model call.
3. **Feed and API sources over search.** RSS costs one fetch for many
   opportunities; search costs a fetch and an extraction per result.
4. **Caching.** Fetches are cached for an hour; the same opportunity discovered
   by two users is extracted once and de-duplicated by fingerprint.
5. **Discovery rate limit.** 20 runs per user per hour, in its own bucket. New
   opportunities appear over days, so this costs users nothing and caps the
   worst case.
6. **Lexical retrieval by default.** The knowledge corpus costs zero.

### Gross margin

At €9–€19 with a handful of discovery runs a month, the margin should be
comfortable. That sentence is an expectation, not a measurement, and it stays
that way until there is usage data.

---

## Later models

**B2B2C licensing.** Career platforms, universities, professional bodies and
transition programmes have populations who need exactly this and no way to
serve them. A university career service already has the profiles; it has no
opportunity graph. The product is built for this — sources are pluggable and the
matching engine is profile-agnostic — but it is P2 and nothing has been sold.

**Partner and lead revenue** where legally and ethically appropriate. Two
conditions, both structural:

1. **Sponsored placements are marked** and badged in the interface.
2. **Ranking is never influenced.** Same deterministic engine, same weights.

If those cannot both hold, we do not take the revenue.

---

## What we will not do

- **Sell ranking.** See above.
- **Sell user data.** No profile sales, no CV sales, no lead sales of the user
  themselves.
- **Train on user documents.** Stated in the consent text, the privacy page and
  the code.
- **Dark patterns.** No pre-ticked upgrades, no cancellation maze, no trial that
  quietly becomes a subscription. The pricing page says this.
- **Charge for the Germany check.** It is the differentiator and it is also the
  thing that stops someone making an expensive administrative mistake. Putting
  it behind a paywall would be the wrong kind of clever.

---

## Market

**Wedge:** skilled professionals in Germany seeking €500–€3,000 additional
monthly income, focused on professional-grade opportunities rather than
low-value microtasks.

**Expansion:** DACH, then EU markets with comparable administrative complexity.
The complexity is the moat, not the obstacle — the Germany check is the hardest
part to copy and the reason a generic international aggregator cannot serve this
user well.

**TAM: TODO.** No defensible bottom-up estimate exists. Producing one would
require German employment statistics segmented by profession and income
intent, and inventing a number here would contradict everything else in this
repository.

---

## What would change this document

- **H4 tested with real users** who have earned money through the product.
- **Measured cost per Money Map** from `llm_usage` after a week of usage.
- **One B2B2C conversation** with a university career service or professional
  body — enough to know whether the licensing model is real or a slide.
