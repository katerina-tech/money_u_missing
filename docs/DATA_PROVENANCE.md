# Data provenance

Where every piece of data in this product came from, on what basis we hold it,
and what we refuse to do. `GET /api/provenance` returns a machine-readable
version of the source table, including disabled sources.

---

## The rule

**An opportunity may only exist because a source published it.**

There is no code path anywhere in this repository that constructs an
`Opportunity` from a model's imagination. The language model plans queries and
reads pages we fetched; `services/normalize.py` validates what it read against
a closed schema; the model never authors a record.

Consequences that are visible in the data:

- Every opportunity carries a `SourceRef` — name, URL, source type, retrieval
  timestamp — and the API returns it on every card.
- `Confidence` cannot reach `VERIFIED` through the automated pipeline. That
  requires a human re-check.
- A field the source did not publish is `null`, everywhere, all the way to the
  interface.

---

## Opportunity sources

### Curated — real, human-recorded

Seven records, each read by hand from the publisher's own page. One file per
record under `backend/curated/`, so adding one is editing data rather than
editing Python.

**Read 2026-09-04 — federal programmes, no amount published:**

| Programme | Source | Compensation |
|---|---|---|
| EXIST-Gründerstipendium | [exist.de](https://www.exist.de/EXIST/Navigation/DE/Gruendungsfoerderung/EXIST-Gruenderstipendium/exist-gruenderstipendium.html) | `null` — the page does not state the amounts |
| EXIST-Forschungstransfer | [exist.de](https://www.exist.de/EXIST/Navigation/DE/Gruendungsfoerderung/EXIST-Forschungstransfer/exist-forschungstransfer.html) | `null` — the page does not state the amounts |

**Read 2026-09-06 — teaching rates, published verbatim in the institution's own
regulation:**

| Institution | Source | Compensation, as published |
|---|---|---|
| Universität Erfurt | [Satzung, Lesefassung 2024-01-31](https://www.uni-erfurt.de/fileadmin/Hauptseiten/Studium/Hochschulrecht/Satzungsrecht_UE/weitere-Satzungen/3.AEnd_LA_Verg_S___2024-01-31_Lesefassung.pdf) | 33,00 / 38,00 / 43,00 € per Einzelstunde, by qualification |
| DHBW | [Lehrvergütungssatzung, 2019-09-30](https://www.dhbw.de/fileadmin/user_upload/Dokumente/Amtliche_Bekanntmachungen/2019/29_2019_Bekanntmachung_Lehrverguetungssatzung.pdf) | 14 / 42 / 55 € je Lehrstunde, by session type |
| HAWK Hildesheim/Holzminden/Göttingen | [Ordnung, from SoSe 2018](https://www.hawk.de/sites/default/files/2018-05/lavergo_z_00_ordnung_verguetung_lehrauftraege_hawk.pdf) | up to 30 / 40 / 100 € je Lehrstunde, by teaching role |
| Universität Speyer | [Regelung, from 2022-04-01](https://www.uni-speyer.de/fileadmin/Universitaet/Rechtsgrundlagen/Lehrauftragsverguetung-1.pdf) | 31 € per Einzelstunde (45 min); 9 € per marked script |
| VHS Hannover | [Honorarordnung, from 2025-08-01](https://www.hannover.de/content/download/407385/file/Honorarordnung_VHS.pdf) | 25,00 € minimum; no ceiling published |

Two things about that second table are deliberate.

**The unit is a teaching hour, not a clock hour.** Every one of these rates is
per *Einzelstunde* or *Lehrstunde* — 45 minutes at most of these institutions —
and the published rate already absorbs preparation and marking. Each record says
so in its summary, because "42 €/hour" read as a clock hour is a materially
different number from the one the institution actually publishes.

**These pages publish a rate, not a vacancy.** None of them advertises a
specific open assignment. Every record says that in as many words rather than
implying an opening that may not exist.

### The nulls, and the rule that now protects them

**The EXIST nulls are still the most important data in this repository.** Both
are real federal programmes that certainly pay something. We do not know how
much, because the pages we read do not say. Publishing a plausible figure would
be exactly the failure this product exists to avoid, so the records say the
amount is not published and the interface renders "Not published".

That used to be protected by care alone. It is now protected by
`scripts/validate_curated.py`, which runs as part of `check` and **fails the
build** if a record states a compensation figure whose digits do not appear in
the `source_excerpt` quoted from the page. Typing a plausible stipend onto a
real federal programme is no longer something a careless afternoon can do: it
would require also fabricating the sentence that says so, which is a different
and far more deliberate act.

`CuratedOpportunitySource` refuses to load a record without a `source_url`.
Curation is the claim that a person looked at a page; a record with nothing to
point at cannot support that claim.

### Demo — fictional

14 records in `data/demo_opportunities.json`. Every organisation name is
invented and reads as invented ("Northlight Expert Circle (fictional)",
"Hansa Logistik Werke (fictional)"). Every record is loaded with
`is_demo: true` and `compensation_verified: false`, forced at load time rather
than trusted from the file.

Three independent mechanisms keep demo data from masquerading as real:

1. A Pydantic validator rejects a demo record claiming verified compensation.
2. A database CHECK constraint (`ck_demo_cannot_be_verified`) rejects the same.
3. `DemoOpportunitySource` forces both fields as it loads.

Deadlines are generated relative to the run date, so the demo never shows an
expired opportunity to a jury.

### RSS feeds — registered and disabled

| Feed | Status | Why |
|---|---|---|
| EU Funding & Tenders Portal | **NOT YET VERIFIED** | The documented feed URL returns HTTP 404 |
| Förderdatenbank (BMWK) | **NOT YET VERIFIED** | The RSS page is a JavaScript shell with no discoverable feed URL |

Both were checked on 2026-09-04 through `SafeFetcher` — the same code path the
product would use. They ship **disabled**, are listed by `GET /api/provenance`
with a note, and appear in `opportunity_sources` with `is_enabled: false`.

A source that 404s on every run is worse than one that is honestly absent, and a
registry that hides its gaps cannot be trusted about the ones it fills.

### Search API — off by default

`SearchAPIOpportunitySource` discovers pages through a licensed search API
(Tavily, Brave or Serper — pluggable), then fetches and reads each page
properly. `MYM_SEARCH_PROVIDER=none` is the default, so a fresh clone makes no
outbound search calls.

A snippet is never treated as sufficient. A snippet is a fragment chosen to look
relevant; building an opportunity record from one would mean publishing an
organisation, a deadline and possibly a compensation figure on the strength of
forty words of ranked marketing text.

---

## German legal knowledge

Ten documents in `data/knowledge/`, retrieved from
[Gesetze im Internet](https://www.gesetze-im-internet.de/) (Bundesministerium
der Justiz) on **2026-09-04**. Each carries front matter with its source URL,
topic and retrieval date, and every chunk inherits that metadata so a citation
needs no join.

| Document | Statute |
|---|---|
| Kleinunternehmerregelung | § 19 UStG |
| Rechnung: Pflichtangaben | § 14 Abs. 4 UStG |
| Freiberuflich or Gewerbe | § 18 EStG, § 14 GewO |
| Steuerliche Erfassung | § 138 AO |
| EÜR and Betriebsausgaben | § 4 Abs. 3 and 4 EStG |
| Grundfreibetrag | § 32a EStG |
| Sparer-Pauschbetrag | § 20 Abs. 9 EStG |
| Minijob | § 8 SGB IV |
| Arbeitslosengeld and Nebentätigkeit | §§ 138, 155 SGB III |
| Nebentätigkeit and employment contracts | Art. 12 GG |

### Legal facts: 10 verified, 3 deliberately not

`data/legal_facts.json` holds 13 versioned facts. Ten are `VERIFIED` with a
structured value read from the statute.

Three are **not**, and the gaps are visible rather than filled:

| Fact | Status | Why |
|---|---|---|
| `de_minijob_threshold` | `NEEDS_REVIEW`, `content_available: false` | § 8 Abs. 1a SGB IV gives a *formula* — minimum wage × 130 ÷ 3, rounded up — and delegates the figure to a Bundesanzeiger publication. We did not record that publication, so **this product does not state a Minijob euro figure anywhere.** |
| `de_kuenstlersozialkasse` | `UNKNOWN`, `content_available: false` | Conditions not recorded from the authority |
| `de_uebungsleiterfreibetrag` | `UNKNOWN`, `content_available: false` | § 3 Nr. 26 EStG amounts not recorded |

`LegalFactRepository.for_topics()` excludes `content_available: false` rows, so
the answer layer cannot quote them. `GET /api/tax/facts` lists them anyway, so
the gap is visible in the product.

### Freshness

Every fact has an effective period and a `last_verified_at`. A stored `VERIFIED`
does not stay verified: past `MYM_LEGAL_FACT_MAX_AGE_DAYS` (365) it becomes
`NEEDS_REVIEW`, the Germany check flags itself as needing verification, and the
tax answer carries a staleness warning. German thresholds move yearly and a
model states last year's value with identical fluency.

`stale_fact_rate` is exposed at `GET /api/metrics` as a product health metric.

---

## What we refuse to do

Not aspirations — these are absent from the codebase, and some are enforced.

| Refused | Enforcement |
|---|---|
| Bypassing a login | No cookie jar, no credential store, no auth in `SafeFetcher` |
| Solving CAPTCHAs | No such code |
| Circumventing paywalls | No such code |
| Private or undocumented APIs | Registry entries record a public access basis |
| Scraping LinkedIn, Indeed, Xing, Glassdoor, Meta | `BLOCKED_HOSTS` in `sources/websearch.py` |
| Ignoring robots.txt | `RobotsCache`, on by default |
| Hammering a host | `HostThrottle`, one request per second per host |
| Downloading arbitrary files | Content-type allowlist; text formats only |
| Unbounded downloads | Size cap enforced while streaming |
| Reaching internal addresses | Every resolved IP checked; redirects re-validated per hop |

A source's `access_basis` is recorded in prose when it is registered and
surfaced by `GET /api/provenance`. The answer to "were you allowed to do that?"
lives in the code rather than in someone's memory.

---

## Prohibited opportunity categories

`OpportunitySafetyClassifier` blocks, deterministically and explainably:

MLM and pyramid recruitment · undeclared/cash-in-hand work · money-mule and
account-rental schemes (including *Finanzagent* listings) · fake reviews and
engagement · gambling and betting systems · benefit and grant misrepresentation
· unlicensed financial services · stolen or counterfeit goods.

And **flags without hiding**: upfront payment requests, guaranteed or
unrealistic earnings, up-front identity-document requests, and pushes to
contact via a messaging app only. A flag is not proof, and suppressing a
legitimate listing is also a harm — so those are shown with a visible warning
and the user decides.

Rules are patterns, not a model. A suppression decision should not vary between
runs and should be explainable to the source if challenged. Both English and
German terms are covered, and letter-spacing evasion is handled.

---

## Data the user provides

| Data | Purpose | Sent to a model? |
|---|---|---|
| CV file / pasted text | Extract skills and experience, once, with explicit consent | Yes, during extraction only |
| Profile (skills, role, hours, goal) | Matching and search planning | A subset — never name, email or portfolio |
| Work status, admin answers | Deciding which Germany-check questions to raise | No |
| Tax questions | Retrieval and cited answering | Yes |
| Recorded income | The Money Map and outcome data | No |

Never used for training. Stated in the consent text, in the privacy page, and
here.

---

## Reproducing the datasets

```bash
python scripts/tasks.py data     # regenerates knowledge + opportunity data
python scripts/tasks.py seed     # loads facts, ingests corpus, registers sources
```

`scripts/build_knowledge.py` and `scripts/build_opportunity_data.py` are the
single definition of the corpus and the datasets, with the retrieval date at the
top. "Where did this number come from?" has exactly one answer.
