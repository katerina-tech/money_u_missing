# Demo script

Ninety seconds to explain the company. Longer version follows for a technical
audience.

**Before you start:** `python scripts/tasks.py dev`, then open
<http://localhost:3000>. No account and no API keys are needed.

---

## The 90 seconds

### 0:00 — The name, immediately

> "Money You're Missing. It means earning opportunities you're overlooking — not
> unclaimed government money, not forgotten subscriptions."

Point at the clarification paragraph in the first viewport. Get this out of the
way in ten seconds; it is the most common misreading and it costs you the rest
of the demo if you leave it.

### 0:10 — One click, no account

Click **Build my Money Map**.

> "No sign-up. This is a fictional professional — a Berlin data engineer, six
> hours a week free, wanting fifteen hundred a month extra."

### 0:20 — The map

> "One profile, and here are opportunities across six categories: an expert
> network, a consulting engagement, a Lehrauftrag, a paid research panel, a
> federal founder programme, a grant. Nobody checks all six. That's the product."

### 0:35 — The money, and what it refuses to do

Point at the four figures.

> "Goal, secured, earned, potential — never added together. The progress bar is
> at zero because nothing has been secured yet, and filling it with potential
> would be the most dishonest thing this product could do."

Point at the exclusion line.

> "And four of these publish no compensation at all. We count them and exclude
> them from the totals, and we say so. That's normal for grants and programmes —
> guessing would be the easy thing and the wrong thing."

### 0:50 — Open one

Click any opportunity.

> "Every score is computed in code — same profile, same listing, same number
> every time, and every component is a sentence you can read. The AI never
> touches it."

Point at **What we don't know**.

> "Same visual weight as what we do know. Most tools put their doubts in a
> footnote."

### 1:05 — The Germany check

Scroll to it.

> "This is the differentiator. This engagement may be self-employed activity;
> whether it's freiberuflich or gewerblich depends on facts we can't see, and we
> say that rather than guessing. Here are the questions to put to your Finanzamt
> — specific ones, not 'consult a professional'. And here are the sources: § 19
> UStG, § 14 GewO, § 138 AO, retrieved with a date."

### 1:20 — Track it

Click **Prepare application** → **Mark as Applied** → **Mark as Won**.

> "It asks what it *actually* paid. Not the advertised amount — the difference
> between those two is the most valuable data this product collects."

Enter 450. Go back to the Money Map.

> "Four hundred and fifty euros, secured. That's the only way money moves out of
> potential."

### 1:30 — Close

> "One profile, real opportunities, honest about what it doesn't know, and the
> German context you need before you act. Starting in Germany."

---

## The technical version (five minutes)

Everything above, plus:

### The architecture claim

> "The language model does three things: reads a CV into a draft you confirm,
> plans search queries, and phrases scores that were already computed. That's the
> whole list.
>
> Matching, actionability, safety classification, de-duplication, every money
> figure and the Germany check are ordinary Python. There's a test that inspects
> the matching module's source and fails if a provider ever appears in it."

Show `ARCHITECTURE.md`'s split table.

### The provenance claim

Open the two EXIST records.

> "These are real federal programmes. Their compensation fields are null,
> because the pages we read don't state the amounts. Those nulls are the most
> important data in the repository — publishing a plausible stipend figure for a
> real federal programme is exactly the failure we're built to avoid."

Then `GET /api/provenance`:

> "Two RSS feeds are registered and disabled. One 404s, one is a JavaScript
> shell with no discoverable feed. We checked both, and they ship marked NOT YET
> VERIFIED rather than pretending to work."

### The honesty claim

Show `GET /api/tax/facts`.

> "Ten verified legal facts, three deliberately not. The Minijob earnings limit
> isn't stated anywhere in this product, because § 8 SGB IV gives a formula and
> delegates the number to a Bundesanzeiger publication we haven't recorded. The
> row exists, marked unavailable, and the answer layer can't quote it."

Ask a tax question in the UI, then ask an off-topic one.

> "Answers arrive with citations, or don't arrive. `CitedAnswer` fails
> validation if you try to construct an answered response with no citations — so
> even a fully subverted prompt can't return an uncited answer."

### It runs on nothing

> "No API keys. Everything you just saw — matching, the Germany check, the
> knowledge corpus, tracking — runs with an empty `.env`. Keys add CV
> extraction, live search and written explanations, and the capability endpoint
> reports exactly what's degraded."

Show the reduced-mode banner.

### Tests

```bash
python scripts/tasks.py check
```

> "180 backend tests, 25 frontend, 9 end-to-end, 42 evaluation cases, mypy
> strict. Nothing makes a paid model call, which is why it's reasonable to run
> on every commit.
>
> The evals are adversarial on purpose: they script the model doing the wrong
> thing — inventing a salary, following an injected instruction, dropping the
> caveats — and check the surrounding system catches it."

---

## Questions you will get

**"How do you get more opportunities?"**
> Curated first — a person reads a page. Then verified feeds and public APIs,
> then licensed search. We have two real records today. Getting to thirty is
> week one, and until we do, our main hypothesis isn't testable. The pipeline is
> built and tested.

**"Isn't this just a ChatGPT wrapper?"**
> Show the split table. Every decision is deterministic Python. A wrapper can't
> tell you why it scored something 84.

**"What if LinkedIn does this?"**
> It could. It hasn't, because expert networks, grants and Lehraufträge are
> outside its category. The more credible threat is a German tax app adding an
> opportunity layer — they already own the administrative relationship.

**"What's the traction?"**
> None. No users, no revenue, no interviews. What exists is a working product
> and the instrumentation to find out whether it helps — two questions in the
> interface and a defined metric set.

---

## What not to do

- **Don't hide the demo badges.** They are a feature. A jury that leaves
  thinking they saw live offers is a jury you misled.
- **Don't claim traction.** The honest slide is the memorable one in a room that
  has seen fifty invented ones.
- **Don't skip "What we don't know".** It looks like a weakness and it is the
  whole argument.
- **Don't demo with an LLM key on** unless you have checked the latency. The
  no-key path is faster, fully deterministic, and shows more of the product.
