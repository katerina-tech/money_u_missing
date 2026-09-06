# Validation plan

What we believe, what would prove us wrong, and how the product is instrumented
to tell the difference.

**Current status: nothing is validated.** No users, no revenue, no interviews.
Every hypothesis below is untested. The product exists to test them.

---

## Hypotheses

### H1 — Cross-category discovery surfaces opportunities people miss

*A cross-category personalised opportunity engine helps skilled professionals
discover actionable income opportunities they would otherwise miss.*

This is the load-bearing one. If it fails, nothing else matters.

- **Measured by:** the in-product question *"Did Money You're Missing show you an
  opportunity you probably would not have found yourself?"* (YES / PARTLY / NO)
- **Supports it:** ≥ 60% YES or PARTLY, and dismissals that are *not*
  concentrated on ALREADY_KNEW.
- **Falsifies it:** < 40% YES or PARTLY, or ALREADY_KNEW as the top dismiss
  reason. That would mean we are re-presenting the platforms people already
  check.
- **Confounder to watch:** the current corpus is mostly demo data. Until the
  curated dataset grows, a low score may measure our corpus rather than the
  thesis. This must be resolved before H1 is judged.

### H2 — German administrative context is valued before acting

*Users value seeing Germany-specific administrative and tax context before
pursuing additional income.*

- **Measured by:** `tax_check_viewed` per `opportunity_opened`; whether users
  who open the Germany check apply at a higher rate; ADMIN_BURDEN dismiss
  frequency.
- **Supports it:** > 40% of opened opportunities have their Germany check
  expanded; qualitative reports that it changed a decision.
- **Falsifies it:** < 15% engagement. That would mean it is a trust signal on
  the landing page rather than a feature — still worth having, but not worth
  building further.

### H3 — Opportunities change often enough to bring people back

*Users return because opportunities change continuously.*

- **Measured by:** weekly return rate; `opportunity_search_started` per user per
  week; new-opportunity yield per refresh.
- **Supports it:** > 30% week-one return, and refreshes that yield new records.
- **Falsifies it:** returns near zero, or refreshes that return the same set.
  **Honest risk:** with no live source enabled, refresh currently yields nothing
  new. H3 is untestable until live discovery is on, and claiming otherwise would
  be measuring a constant.

### H4 — Continuous discovery is worth paying for

*Users are willing to pay for continuous high-quality opportunity discovery and
prioritisation.*

- **Measured by:** nothing yet. There is no payment flow, and there will not be
  until H1 is supported.
- **What we will *not* do:** treat a "would you pay?" survey answer as evidence.
  Stated intent to pay is not evidence of paying.
- **First real test:** a manual offer to users who have recorded income through
  the product. Someone who earned €800 because of it is the only person whose
  answer means anything.

### H5 — Outcome data improves recommendations

*Outcome data improves recommendation quality over time.*

- **Measured by:** whether match scores of applied-to opportunities exceed those
  of dismissed ones, over time; whether preference adjustment reduces dismissal.
- **Status:** the data is collected. It does **not** feed ranking, because
  per-user outcome counts are single digits and treating that as signal would be
  the exact error this product refuses to make about opportunities.
- **Testable at:** roughly 50 outcomes per category across all users.

---

## First 20 users

### Who

Skilled professionals living in Germany, employed or freelance, who have said
they want more income and have limited time. Recruit from professional
communities, alumni networks and a small number of direct approaches. Not
friends, and not people who will be polite.

Deliberately **not**: students, people outside Germany, or anyone looking for a
new full-time job. Those are different products.

### Protocol

**Session 1 — 30 minutes, observed.**

1. Five minutes: what do they currently do to find additional income? What did
   they try last and what happened? *(Ask before showing anything — the answer
   is contaminated afterwards.)*
2. They onboard with their own CV. Watch where they hesitate. Do not help.
3. They read their Money Map. **Ask them to talk aloud.** Specifically: does any
   number surprise them, and do they believe it?
4. They open one opportunity. Do they read "What we don't know"? Does it change
   their confidence up or down?
5. They answer both in-product questions.
6. Five minutes: what would make you come back next week? What is missing?

**Between sessions.** Instrument only. No nudges, no emails.

**Session 2 — 15 minutes, day 14.**

1. Did you pursue anything? What happened?
2. If not, what stopped you? *(This is the most valuable question in the
   study.)*
3. Would you notice if this disappeared?

### What we are listening for

- The moment someone says **"I didn't know that existed"** — H1.
- The moment someone says **"but what does that mean for my tax"** *before* we
  show the Germany check — H2.
- Whether anyone opens it again unprompted — H3.
- Whether anyone asks what it costs — a weak H4 signal, recorded but not
  counted.

### What would make us stop and rethink

- Most users say they already knew everything shown. → The sources are wrong,
  not the product.
- Users like the Money Map but never apply. → We built a browsing tool.
- The Germany check is ignored. → The differentiator is not one.
- Nobody returns. → It is a one-time utility, not a product.

None of those means the idea is dead. Each points at a different thing to fix,
which is why the questions are separated.

---

## Anti-patterns we are avoiding

**Vanity metrics.** Sign-ups, page views and time on site are not in
`METRICS.md`. Whether someone applied to something is.

**Leading questions.** The in-product questions ask what happened, not how they
felt. "Did we show you something you would not have found?" is checkable
against their own behaviour; "Do you like it?" is not.

**Counting intent as outcome.** `would_pursue` and `application_marked_applied`
are separate metrics precisely because the gap between them is the finding.

**Measuring the demo.** Demo sessions are flagged `is_demo` throughout and must
be excluded from every validation metric. A jury clicking through is not a user.

---

## Timeline

| Week | What |
|---|---|
| 1 | Expand the curated dataset to ~30 real opportunities. Without this, H1 is untestable. |
| 1 | Enable one live source. Without this, H3 is untestable. |
| 2 | Recruit 20. Run session 1. |
| 2–3 | Instrument only. Read the dismiss reasons daily — they are the highest-information signal available. |
| 4 | Session 2. Decide: iterate on matching, iterate on sources, or reconsider the wedge. |

**The first two rows are the point.** Running a user study against demo data
would produce a confident number about nothing.
