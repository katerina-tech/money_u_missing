# Pitch deck outline

Ten slides. Every number is either measured from this build or marked TODO.
Nothing is invented — including the traction slide, which is the one that
usually is.

---

## 1 — Money You're Missing

> **Money You're Missing**
> One profile. Multiple ways to earn.
>
> A personal opportunity-to-income engine for skilled professionals in Germany.

*Say:* the name means earning opportunities you are overlooking. Not unclaimed
government money, not forgotten subscriptions. Clear that up in the first ten
seconds — it is the most common misreading.

## 2 — Problem

> Your experience is worth more than one paycheck.
>
> Jobs are in one place. Freelance work in another. Expert networks somewhere
> else. Programmes, fellowships and grants are scattered across hundreds of
> institutional pages nobody checks.
>
> And then: what does this mean for my employment contract, my tax
> registration, my VAT?

*Say:* the search problem and the administrative problem are both real, and
solving only one leaves the person stuck.

*Do not say:* any market-size statistic. There isn't a defensible one.

## 3 — Current behaviour

> People check the one channel they already know, and stop.

*Say:* the alternative to us is not a competitor. It is a browser with eleven
tabs, abandoned on a Sunday evening. **TODO: replace with a verbatim quote from
user interview #1.** That quote is worth more than this whole slide.

## 4 — Solution

> One profile → real opportunities → transparent match → Germany check → one
> next action → tracked to actual income.

*Say:* the pipeline is the product. Each arrow is a place where other tools
stop.

## 5 — Product demo

**Live.** Ninety seconds, no slides. See `DEMO_SCRIPT.md`.

The three moments that matter:
- Opportunities across six categories from one profile.
- "What we don't know", given the same weight as what we do.
- Potential and secured money never added together.

## 6 — Why we win

> **The AI never decides anything.**
>
> It reads a CV into a draft you confirm, plans search queries, and phrases
> scores that were already computed. Everything that decides — match,
> actionability, safety, every money figure, the Germany check — is ordinary
> code. Same inputs, same score, every time.
>
> **Unknown stays unknown.** Missing pay is "Not published", never €0.

*Say:* this is why we can defend a number to a user who disagrees with it, and
why a listing cannot argue its way up the ranking.

*Expect:* "isn't the AI the moat?" Answer: no, and slide 9 says what is.

## 7 — Market

> **Wedge:** Germany · skilled professionals · €500–€3,000 additional monthly
> income · professional-grade opportunities.
>
> **Then:** DACH → EU markets with comparable administrative complexity.

**TAM: TODO.** Say so. A bottom-up estimate needs German employment data
segmented by profession and income intent, and we have not built one.

*Say:* the administrative complexity is the moat, not the obstacle. It is why a
generic international aggregator cannot serve this user.

## 8 — Business model

> **Free** — profile, first Money Map, limited opportunities, Germany check.
> **Pro (hypothesis, €9–€19/mo)** — continuous discovery, alerts, full action
> workspace, tracking.
> **Later** — B2B2C to career platforms, universities, professional bodies.

*Say:* the price is a hypothesis and nobody has paid. We will not sell ranking —
`MatchScore` has no field for commercial value, deliberately.

## 9 — Validation and traction

> **Nothing is validated yet. No users, no revenue, no interviews.**
>
> What exists: a working product, and the instrumentation to find out.
>
> - H1: does this surface opportunities people would miss?
> - H2: is German context valued before acting?
> - H3: do opportunities change enough to bring people back?

*Say:* the two in-product questions and the dismiss-reason taxonomy are how we
learn *which part* is wrong — sources, matching, or discovery.

*Also say:* the honest blocker. The curated dataset holds two real
opportunities. Until it holds thirty, H1 is untestable, and running a study
before then would produce a confident number about nothing. That is week one.

**This slide is the credibility test.** A room that has seen fifty decks with
invented traction will remember the one that said "not yet, and here is exactly
how we will know".

## 10 — Vision and ask

> Every professional in Europe has a map of what their experience is actually
> worth — across every way it can be paid for, with the local context needed to
> act.

**Ask: TODO.** No amount, no use of funds, no milestone commitment is asserted
here. Fill in before pitching, and make the milestone the thing that resolves
H1.

---

## Appendix slides to have ready

- **Architecture** — the AI/deterministic split table from `ARCHITECTURE.md`.
- **Provenance** — the two real records with null compensation. The most
  persuasive slide in the deck, because it shows discipline rather than claiming
  it.
- **Security** — the five-layer injection defence, and the SSRF re-validation on
  every redirect hop.
- **Testing** — 180 + 25 + 9 + 42, none of which makes a paid model call.
- **Regulatory boundaries** — how each line is enforced structurally.

## Questions to expect

**"Why won't LinkedIn do this?"** It could. It has not, because expert networks,
grants and Lehraufträge are outside its category and its model rewards depth in
recruiting. The more credible threat is a German tax app adding an opportunity
layer — it already owns the administrative relationship.

**"Isn't this just a wrapper?"** Every decision in the product is deterministic
Python. The model reads and phrases. Show the table.

**"Where does the supply come from?"** Curated first, feeds and public APIs
next, licensed search after that. Show the provenance doc, including the two
feeds that failed verification and ship disabled.

**"Two real opportunities?"** Yes, and that is the number. Each one means a
person read a page. Scaling it is P1 and the pipeline is built and tested.
