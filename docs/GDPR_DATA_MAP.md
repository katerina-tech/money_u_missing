# GDPR data map

What is collected, why, on what basis, for how long, and how to remove it.
Written for a product that processes CVs — the most sensitive thing a
professional routinely hands over — and deployed for the German market.

---

## Roles

The operator of a deployment is the **controller**. Processors are the model
provider (when configured), the search provider (when configured), and the
database host.

With no API keys configured, **there are no processors**: nothing leaves the
server. That is the default, and it is also how the demo runs.

---

## Data inventory

| Data | Purpose | Legal basis | Retention | Deletion path |
|---|---|---|---|---|
| Email address | Identify the account, sign in | Contract (Art. 6(1)(b)) | Until deletion | `DELETE /api/auth/account` |
| Password | Authenticate | Contract | Argon2id hash only; plaintext exists only within the request | Account deletion |
| Refresh tokens | Keep a session alive, allow logout | Contract | Until expiry or revocation; SHA-256 hash only | Logout, or account deletion |
| CV file | Extract skills once | **Consent** (Art. 6(1)(a)), recorded | Until deleted; not needed after the profile is confirmed | `DELETE /api/profile/cv` |
| CV extracted text | Re-extraction without re-upload | **Consent** | Same, and cleared by the same call | `DELETE /api/profile/cv` |
| Profile: skills, role, experience, city, languages | Matching, search planning | Contract | Until deletion | Profile page, or account deletion |
| Income goal, minimum, preference | Scoring `income_goal_fit` | Contract | Until deletion | Profile page |
| Hours, schedule, remote preference | Scoring `availability_fit`, `location_fit` | Contract | Until deletion | Profile page |
| Work status | Deciding which Germany-check questions apply | Contract | Until deletion | Profile page |
| Gewerbe / freelance registration answers | Same | Contract | Until deletion | Profile page |
| **Benefit disclosure** | Showing reporting rules that apply | **Consent**, and optional — `PREFER_NOT_TO_SAY` exists | Until changed | Profile page |
| Saved / dismissed opportunities | The board, and ranking adjustment | Contract | Until deletion | Account deletion |
| Dismiss reasons | Preference learning | Contract (legitimate expectation of the service) | Until reset | `DELETE /api/preferences` |
| Applications, checklists, notes, drafts | The action workspace | Contract | Until deletion | Account deletion |
| Recorded income events | The Money Map, outcome data | Contract | Until deletion | Account deletion |
| Financial and child goals | GROW / FAMILY | Contract | Until deletion | Per-goal delete, or account deletion |
| Feedback responses | Product validation | Legitimate interest (Art. 6(1)(f)) | Until deletion | Account deletion |
| Analytics events | Measuring whether the product works | Legitimate interest | Until deletion | Account deletion |
| Notifications | In-app messages | Contract | Until deletion | Account deletion |
| LLM usage records | Unit economics | Legitimate interest | Kept; `user_id` set to NULL on deletion | — |
| Audit events | Evidencing security actions | Legal obligation / legitimate interest | Kept, keyed by one-way hash | Not deletable, and not personal data alone |

### A child's data

The FAMILY module stores a **label** the parent chooses, an age and amounts.
There is no field for a child's name, date of birth or any identifier. The form
says so.

---

## Data minimisation in practice

Three places where less is sent than would be convenient:

**The search planner** receives skills, role, seniority, languages, location and
availability. Not the display name, not the email, not the portfolio URL. It
does not need them, and they would otherwise travel to a third-party model for
no reason. (`_profile_summary` in `services/search_planner.py`.)

**Analytics** has a per-event allowlist of property names *and types*. Anything
else is dropped with a warning before it is written. Income is recorded as a
bucket (`"500_1000"`), never as an amount — "how much does this user earn" is
not a question the analytics table needs to answer.

**Logs** reduce CV text and tax questions to a length and a truncated hash.
Deliberately no preview: for a CV, the first 200 characters are the identifying
ones, so the usual compromise would put a name, an employer and a city into log
storage.

---

## Consent

Two consents, both recorded verbatim in `consent_records` with a timestamp:

1. **Privacy notice**, at signup. Required; signup fails without it.
2. **CV processing**, before a CV or pasted profile is read. Required; the
   endpoint refuses without it.

The exact wording shown is stored, so consent can be *evidenced* rather than
asserted, and both are visible at `GET /api/profile/consents` and on the
settings page. Withdrawal is recorded as `withdrawn_at` rather than a delete, so
the audit trail survives the withdrawal.

---

## Rights, and where they are exercised

| Right | How |
|---|---|
| Access (Art. 15) | Settings → *Download everything we hold*. Real JSON of every row, excluding the password hash and stored file paths — neither is information about the user they do not have. |
| Rectification (Art. 16) | The profile page. Every field is editable, and clearing a field clears it. |
| Erasure (Art. 17) | Settings → *Delete my account*. One `DELETE`; every personal table cascades. |
| Restriction (Art. 18) | Delete the CV while keeping the profile; reset preference learning. |
| Portability (Art. 20) | The same JSON export. |
| Objection (Art. 21) | `DELETE /api/preferences` stops ranking adjustment; feedback and analytics go with the account. |

### Why deletion actually works

Every table holding personal data has `ForeignKey("users.id", ondelete="CASCADE")`.
Deleting the user row deletes everything — no checklist to forget when a table
is added next month, which is how "we deleted your data" quietly becomes false.

SQLite does not enforce foreign keys by default, so `PRAGMA foreign_keys=ON` is
set on every connection. Without it the cascades would silently do nothing on
the local database.

Stored CV files are removed from disk **before** the row delete, because a
filesystem is not covered by a foreign key.

`tests/test_api.py::test_account_deletion_removes_every_personal_row` asserts
the row counts afterwards, and asserts that the audit record survives.

---

## Transfers

| Processor | Data sent | When |
|---|---|---|
| Anthropic (or OpenRouter) | CV text (once), profile summary, retrieved page content, tax questions | Only when an LLM key is configured |
| Tavily / Brave / Serper | Generated search queries containing skill and role terms | Only when a search key is configured |
| Database host | Everything in the inventory | Always |

**Recommendation: deploy the database in an EU region.** For Supabase this is
chosen at project creation and cannot be changed afterwards — pick `eu-central-1`
(Frankfurt) or another EU region. A product about German income that stored
German CVs outside the EU without saying so would not be worth trusting.

Model and search providers may process outside the EU. A deployment that needs
to avoid that can run with `MYM_LLM_PROVIDER=none` and
`MYM_SEARCH_PROVIDER=none` — the product still works, with the degradations the
capability endpoint reports.

---

## Security measures (Art. 32)

Argon2id password hashing · refresh tokens stored hashed and revocable ·
per-user authorisation with no route accepting a user id from the request ·
TLS in deployment · secrets as `SecretStr`, never logged · upload validation ·
SSRF prevention · rate limiting · restrictive CSP and security headers ·
validation errors that never echo the submitted value · structured logs with
hashed subject ids.

---

## Retention

The product has no automatic deletion job. Data is kept until the user removes
it, which is the honest description of the current behaviour.

Two things a production deployment should add, and neither is built:

1. **Demo account cleanup.** Each demo session creates a real account. They
   accumulate.
2. **A retention policy for inactive accounts.**

Both are P1 in `ROADMAP.md`. They are listed here rather than omitted, because a
data map that describes intentions instead of behaviour is worse than none.

---

## Breach response

Not built: this is a pre-launch MVP with no users. Before launch a deployment
needs a documented notification process (Art. 33/34), a controller contact
point, and a decision on whether a DPO is required.

`audit_events` provides the trail — signups, logins, failed logins, deletions —
keyed by hash and outliving the account.
