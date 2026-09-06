# Competitor analysis

**There are no empty markets.** Every function this product performs is
performed today by something — usually by the user, manually, badly. The
question is not whether competitors exist but whether the *combination* is
defensible.

---

## Categories

### 1. AI side-hustle generators

ChatGPT prompts, "50 ways to earn" newsletters, and a long tail of apps that
generate ideas from a description of you.

**What they do well.** Zero friction, genuinely creative, occasionally
surfaces a category you had not considered.

**Where they stop.** They produce *ideas*, not opportunities. "Become an expert
network consultant" is a sentence; it is not something you can apply to. There
is no organisation, no compensation, no deadline, no eligibility, and nothing to
click. The user is left exactly where they started, with a better vocabulary.

**Honest overlap.** Our search planner does the same associative work — knowing
that a data engineer should also be searched for as an expert-network candidate.
The difference is that our output is then *executed against real sources*, and a
hallucinated query simply finds nothing.

### 2. Multi-income management apps

Tools for tracking multiple income streams once you have them.

**What they do well.** The tracking half, often better than we do.

**Where they stop.** They assume you already have the income. They do not find
anything, and finding is the hard part.

**Honest overlap.** Our Money Map and income portfolio are a thinner version of
what these do well. If a user only wants tracking, they should use one of these.

### 3. Job and freelance platforms

LinkedIn, Xing, Indeed, StepStone, Malt, Freelancermap, Upwork.

**What they do well.** Enormous supply, real listings, mature matching within
their category.

**Where they stop.** Each is one category. A professional wanting €1,500 extra
has to check a job board *and* a freelance marketplace *and* expert networks
*and* university teaching bureaus *and* grant databases — and the last three
have no aggregator at all. None of them tells a German employee that a
freelance engagement raises a Nebentätigkeit question.

**Honest overlap.** Substantial in the categories they cover. We do not compete
on full-time job supply and should not try.

### 4. Opportunity aggregators

Grant databases, fellowship listings, Förderdatenbank, EU funding portals.

**What they do well.** Deep coverage in one vertical, often authoritative.

**Where they stop.** Vertical-specific, largely unpersonalised, and frequently
hostile to use — during this build the EU feed URL returned 404 and the
Förderdatenbank RSS page turned out to be a JavaScript shell with no
discoverable feed. That difficulty is itself the opportunity.

### 5. German tax apps

Taxfix, WISO, Smartsteuer, Accountable, sevDesk.

**What they do well.** Filing, bookkeeping, invoicing. Regulated and mature.

**Where they stop.** They engage *after* you have income. They answer "how do I
declare this?", not "should I take this on, and what does it imply?".

**Honest overlap.** Adjacent, not overlapping. We deliberately do not compute
tax; they deliberately do not find work. A partnership is more plausible than a
collision.

### 6. Personal finance apps

Finanzguru, Outbank, budgeting tools.

**What they do well.** Categorising money that already exists.

**Where they stop.** Backward-looking. They tell you where your money went, not
where more could come from.

**Name confusion risk.** "Money You're Missing" sounds like it belongs here —
unclaimed money, forgotten subscriptions, tax refunds. That is the wrong
expectation and it costs us the wrong visitors, which is why the landing page
clarifies it in the first viewport.

---

## The intersection

No single category does all five:

| | Cross-category real opportunities | Personal deterministic matching | German admin context | Action workflow | Outcome tracking |
|---|:--:|:--:|:--:|:--:|:--:|
| Side-hustle generators | ✗ | ✗ | ✗ | ✗ | ✗ |
| Income management apps | ✗ | ✗ | ✗ | ✗ | ✓ |
| Job / freelance platforms | ~ (one category) | ~ | ✗ | ~ | ✗ |
| Opportunity aggregators | ~ (one vertical) | ✗ | ✗ | ✗ | ✗ |
| German tax apps | ✗ | ✗ | ✓ | ✗ | ~ |
| Personal finance apps | ✗ | ✗ | ✗ | ✗ | ~ |
| **This product** | ✓ | ✓ | ✓ | ✓ | ✓ |

**The honest reading of that table:** the individual cells are not novel. The
combination is, and the combination is only defensible if the execution holds —
which is why so much of this repository is about evidence, provenance and
refusing to invent things.

---

## Who could do this better than us

Stated plainly, because a competitor analysis that only lists weaker rivals is
marketing.

**LinkedIn**, if it decided to. It has the profiles, the supply and the
distribution. It has not, because expert networks, grants and Lehraufträge are
outside its category and its business model rewards depth in recruiting rather
than breadth in earning.

**A German tax app** adding an opportunity layer. Taxfix or Accountable already
own the administrative relationship and the trust. This is the most credible
competitive threat, and it is why the Germany check must stay a feature of the
opportunity — attached to a listing, answering "what would this mean for me?" —
rather than a tax module bolted on.

**A well-funded aggregator** with a scraping team. Faster to more supply, and
would beat us on coverage. It would not beat us on eligibility, on honest
unknowns, or on the administrative layer, because those are product decisions
rather than volume.

---

## Why the differentiation might not hold

- **Coverage beats nuance for many users.** Someone who just wants more
  freelance work may prefer one large marketplace to a careful cross-category
  map.
- **The Germany check may be a trust signal rather than a used feature.** H2
  exists to find out, and a low engagement number is a real possible outcome.
- **Honest unknowns may read as weakness.** "Not published" on half the cards is
  truthful and less satisfying than a confident estimate. Some users will prefer
  the confident competitor. That is a real cost of the position, taken
  deliberately.

---

## The wedge

Germany · skilled professionals · €500–€3,000 additional monthly income ·
professional-grade opportunities · consulting, expert calls, teaching,
professional freelance, paid programmes, grants and competitions.

Narrow on purpose. The administrative complexity that makes Germany hard is the
same complexity that makes a generic international aggregator useless here — and
it is the part that takes longest to copy.
