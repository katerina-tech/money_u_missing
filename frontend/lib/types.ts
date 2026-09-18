/**
 * Wire types, mirroring backend/app/api/dto.py.
 *
 * Hand-written rather than generated, and deliberately so: the point of
 * restating them is that a backend field rename becomes a TypeScript error in
 * the component that reads it, which is where the missing data would actually
 * show up. A generated client would compile happily and render an empty card.
 *
 * Money is always integer minor units plus a currency. There is no `number`
 * anywhere in this file that means euros.
 */

export type TrustLabel =
  | "VERIFIED"
  | "SOURCE_BACKED"
  | "UNVERIFIED"
  | "DEMO"
  | "NEEDS_REVIEW"
  | "OUTDATED"
  | "UNKNOWN";

export type ActionabilityBand =
  "HIGHLY_ACTIONABLE" | "ACTIONABLE" | "REVIEW_FIRST" | "LOW_PRIORITY";

export type ApplicationStatus =
  | "DISCOVERED"
  | "SAVED"
  | "PREPARING"
  | "APPLIED"
  | "INTERVIEW"
  | "OFFERED"
  | "WON"
  | "LOST"
  | "ARCHIVED";

export type DismissReason =
  | "NOT_RELEVANT"
  | "TOO_LITTLE_MONEY"
  | "TOO_MUCH_TIME"
  | "NOT_QUALIFIED"
  | "ADMIN_BURDEN"
  | "LOCATION"
  | "DEADLINE"
  | "ALREADY_KNEW"
  | "OTHER";

export type Tristate = "YES" | "NO" | "UNKNOWN";
export type BenefitDisclosure = "YES" | "NO" | "PREFER_NOT_TO_SAY" | "UNKNOWN";
export type RemoteType = "REMOTE" | "HYBRID" | "ONSITE" | "UNKNOWN";
export type SkillLevel =
  "BEGINNER" | "INTERMEDIATE" | "ADVANCED" | "EXPERT" | "UNKNOWN";
export type SkillEvidence = "CV" | "USER_STATED" | "INFERRED";
export type LanguageLevel =
  "A1" | "A2" | "B1" | "B2" | "C1" | "C2" | "NATIVE" | "UNKNOWN";

export interface Tokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  email: string | null;
  is_demo: boolean;
}

export interface Money {
  minor_min: number | null;
  minor_max: number | null;
  currency: string;
  basis: string;
  period: string;
  tax_treatment: string;
  verified: boolean;
  /** Present when nothing is published. Rendered instead of an empty slot. */
  unknown_note: string | null;
}

export interface Skill {
  name: string;
  key: string;
  level: SkillLevel;
  years: number | null;
  evidence: SkillEvidence;
  related: string[];
  confirmed: boolean;
}

export interface Profile {
  display_name: string | null;
  city: string | null;
  federal_state: string | null;
  country: string;
  current_role: string | null;
  years_experience: number | null;
  skills: Skill[];
  industries: string[];
  education: Education[];
  certifications: Certification[];
  languages: { code: string; level: LanguageLevel }[];
  portfolio_url: string | null;
  current_primary_income_type: string | null;
  desired_additional_monthly_minor: number | null;
  minimum_worthwhile_minor: number | null;
  income_preference: "RECURRING" | "ONE_TIME" | "NO_PREFERENCE";
  hours_per_week: number | null;
  schedule_preference:
    "EVENINGS" | "WEEKENDS" | "WEEKDAY_HOURS" | "FLEXIBLE" | "UNKNOWN";
  remote_preference: RemoteType;
  willing_to_travel: Tristate;
  work_status:
    | "EMPLOYEE"
    | "SELF_EMPLOYED"
    | "EMPLOYEE_AND_SELF_EMPLOYED"
    | "STUDENT"
    | "JOB_SEEKING"
    | "PARENTAL_LEAVE"
    | "OTHER"
    | "UNKNOWN";
  has_gewerbe: Tristate;
  has_freelance_tax_registration: Tristate;
  knows_employer_rules: Tristate;
  receives_employment_benefits: BenefitDisclosure;
  confirmed: boolean;
  completeness: number;
  currency: string;
}

export interface Education {
  qualification: string;
  institution: string | null;
  field_of_study: string | null;
  completed_year: number | null;
}

export interface Certification {
  name: string;
  issuer: string | null;
  issued_year: number | null;
}

export interface ProfileDraftResponse {
  draft: Profile;
  not_found: string[];
  extraction_notes: string[];
  inferred_skill_count: number;
  source: string;
}

export interface ScoreComponent {
  name: string;
  score: number;
  weight: number;
  detail: string;
  was_unknown: boolean;
}

export interface Match {
  total_score: number;
  eligible: boolean;
  components: ScoreComponent[];
  hard_failures: { requirement: string; explanation: string }[];
  uncertainties: {
    topic: string;
    explanation: string;
    how_to_resolve: string | null;
  }[];
  explanation_inputs: string[];
  /** Model-written. Always labelled as such; the bullets are the source of truth. */
  explanation: string | null;
  weights_version: string;
}

export interface Actionability {
  score: number;
  band: ActionabilityBand;
  headline_reason: string;
  factors: { name: string; score: number; weight: number; detail: string }[];
  blockers: string[];
}

export interface OpportunitySummary {
  id: string;
  title: string;
  organization: string | null;
  category: string;
  remote_type: RemoteType;
  city: string | null;
  country: string | null;
  compensation: Money;
  estimated_hours_min: number | null;
  estimated_hours_max: number | null;
  deadline: string | null;
  trust: TrustLabel;
  is_demo: boolean;
  is_sponsored: boolean;
  safety_verdict: string;
  safety_reasons: string[];
  source_name: string;
  source_url: string | null;
  last_seen_days_ago: number;
  match: Match | null;
  actionability: Actionability | null;
  saved: boolean;
  application_status: ApplicationStatus | null;
}

export interface GermanyCheck {
  considerations: string[];
  questions_to_check: string[];
  employment_notes: string[];
  benefit_notes: string[];
  official_sources: {
    source_name: string;
    source_url: string | null;
    title: string;
    excerpt: string;
  }[];
  needs_verification: boolean;
  disclaimer: string;
}

export interface OpportunityDetail extends OpportunitySummary {
  description: string | null;
  summary: string | null;
  required_skills: string[];
  preferred_skills: string[];
  eligibility_text: string | null;
  eligibility_structured: {
    label: string;
    strength: string;
    source_text: string | null;
  }[];
  experience_min_years: number | null;
  experience_max_years: number | null;
  employment_type: string;
  what_we_know: string[];
  what_we_dont_know: string[];
  corroborating_sources: { name: string; url: string | null; type: string }[];
  germany_check: GermanyCheck | null;
}

export interface MoneySummary {
  currency: string;
  recurring_potential_monthly_minor: number;
  recurring_potential_count: number;
  one_time_potential_minor: number;
  one_time_potential_count: number;
  secured_monthly_minor: number;
  secured_one_time_minor: number;
  secured_count: number;
  earned_total_minor: number;
  earned_count: number;
  unknown_value_count: number;
  unconvertible_count: number;
  exclusions: string[];
}

export interface BestNextMove {
  opportunity_id: string;
  title: string;
  organization: string | null;
  reasons: string[];
  call_to_action: string;
  caveat: string | null;
}

export interface IncomePath {
  category: string;
  label: string;
  opportunity_count: number;
  best_match_score: number | null;
  indicative_monthly_minor: number | null;
}

export interface DiscoveryDiagnostics {
  considered: number;
  returned: number;
  duplicates_removed: number;
  stale_removed: number;
  blocked_unsafe: number;
  blocked_injection: number;
  extraction_failures: number;
  sources_queried: number;
  sources_failed: string[];
  live_search_used: boolean;
  notices: string[];
  plan_rationale: string;
  queries: string[];
}

export interface MoneyMap {
  greeting: string;
  goal_monthly_minor: number | null;
  currency: string;
  summary: MoneySummary;
  goal_progress_ratio: number | null;
  best_next_move: BestNextMove | null;
  opportunities: OpportunitySummary[];
  income_paths: IncomePath[];
  this_week: string[];
  recent_progress: string[];
  diagnostics: DiscoveryDiagnostics;
  is_demo: boolean;
}

export interface Application {
  id: string;
  opportunity_id: string;
  opportunity_title: string;
  organization: string | null;
  status: ApplicationStatus;
  money_state: string;
  status_history: { from: string; to: string; at: string }[];
  checklist: { label: string; done: boolean }[];
  documents_needed: string[];
  questions_to_verify: string[];
  notes: string | null;
  drafts: Record<string, string>;
  reminder_at: string | null;
  applied_at: string | null;
}

export interface Citation {
  source_name: string;
  source_url: string | null;
  title: string;
  effective_year: number | null;
  retrieved_at: string | null;
  excerpt: string;
}

export interface TaxAnswer {
  question: string;
  answered: boolean;
  answer: string;
  refusal: string | null;
  citations: Citation[];
  staleness_warnings: string[];
  questions_to_verify: string[];
  disclaimer: string;
}

export interface LegalFact {
  id: string;
  category: string;
  title: string;
  summary: string;
  structured_value: Record<string, unknown>;
  effective_from: string | null;
  effective_to: string | null;
  source_name: string;
  source_url: string | null;
  last_verified_at: string | null;
  trust: TrustLabel;
  status: string;
}

export interface Goal {
  id: string;
  goal_type:
    "EMERGENCY_FUND" | "HOME" | "EDUCATION" | "RETIREMENT" | "CHILD" | "OTHER";
  name: string;
  target_minor: number;
  target_date: string | null;
  current_minor: number;
  monthly_contribution_minor: number;
  currency: string;
  progress_ratio: number;
  months_at_current_contribution: number | null;
}

export interface ChildGoal {
  id: string;
  child_label: string;
  child_age_years: number;
  target_age_years: number;
  target_minor: number;
  current_minor: number;
  monthly_contribution_minor: number;
  currency: string;
  years_remaining: number;
}

export interface Projection {
  initial_minor: number;
  monthly_contribution_minor: number;
  annual_return: number;
  annual_inflation: number | null;
  months: number;
  currency: string;
  total_contributed_minor: number;
  final_balance_minor: number;
  final_real_balance_minor: number | null;
  growth_minor: number;
  points: {
    month: number;
    contributed_minor: number;
    balance_minor: number;
    real_balance_minor: number | null;
  }[];
  disclaimer: string;
}

export interface OwnershipCard {
  title: string;
  note: string;
  considerations: {
    topic: string;
    parent_account: string;
    child_account: string;
    fact_id: string | null;
  }[];
  questions_to_check: string[];
  /** Always null. The absence is the point. */
  recommended: null;
  ownership_options: string[];
}

export interface Capabilities {
  llm_available: boolean;
  llm_provider: string;
  live_search_available: boolean;
  search_provider: string;
  retrieval_mode: string;
  knowledge_documents: number;
  knowledge_chunks: number;
  legal_facts_verified: number;
  legal_facts_total: number;
  stale_fact_rate: number | null;
  demo_mode_enabled: boolean;
  payments_enabled: boolean;
  database: string;
  pgvector: boolean;
  degradations: string[];
}

export interface SourceProvenance {
  id: string;
  name: string;
  type: string;
  access_basis: string;
  enabled: boolean;
  note: string | null;
}

// ------------------------------------------------------- personal money

export type AmountBasis = "GROSS" | "NET" | "UNKNOWN";

export type ExpenseCategory =
  | "EQUIPMENT"
  | "SOFTWARE_AND_SUBSCRIPTIONS"
  | "TRAVEL"
  | "WORKSPACE"
  | "PROFESSIONAL_DEVELOPMENT"
  | "PROFESSIONAL_SERVICES"
  | "INSURANCE_AND_CONTRIBUTIONS"
  | "MATERIALS"
  | "COMMUNICATION"
  | "MARKETING"
  | "FEES_AND_CHARGES"
  | "OTHER";

export interface BaselineIncome {
  id: string;
  label: string;
  amount_minor: number;
  currency: string;
  basis: AmountBasis;
  period: "ONE_TIME" | "RECURRING" | "IRREGULAR" | "UNKNOWN";
  is_primary: boolean;
  started_on: string | null;
  /** null when the period implies no monthly figure. Never 0 for "unknown". */
  monthly_minor: number | null;
}

export interface BaselinePicture {
  entries: BaselineIncome[];
  currency: string;
  /** Three separate totals. Deliberately no combined figure. */
  net_monthly_minor: number;
  gross_monthly_minor: number;
  unlabelled_monthly_minor: number;
  one_off_minor: number;
  notes: string[];
}

export interface Expense {
  id: string;
  label: string;
  amount_minor: number;
  currency: string;
  category: ExpenseCategory;
  incurred_on: string;
  has_receipt: Tristate;
  partly_private: Tristate;
  income_stream_id: string | null;
  application_id: string | null;
  notes: string | null;
}

export interface CategoryTotal {
  category: ExpenseCategory;
  total_minor: number;
  count: number;
  without_receipt: number;
  partly_private: number;
}

export interface ExpenseSummary {
  currency: string;
  total_minor: number;
  count: number;
  by_category: CategoryTotal[];
  without_receipt_count: number;
  questions_to_check: string[];
  disclaimer: string;
}

export interface HouseholdChild {
  label: string;
  age_years: number;
  in_education_or_training: Tristate;
}

export interface Household {
  has_children: Tristate;
  jointly_assessed: Tristate;
  children: HouseholdChild[];
  disclosed: boolean;
}

export interface PersonalOverview {
  baseline: BaselinePicture;
  expenses: ExpenseSummary;
  household: Household;
  goal_monthly_minor: number | null;
  uplift_ratio: number | null;
  facts: LegalFact[];
  questions_to_check: string[];
  disclaimer: string;
}

export interface Leak {
  id: string;
  title: string;
  why_this_applies: string;
  what_to_check: string;
  fact_ids: string[];
  /** The figure the statute prints. Never what this user would receive. */
  stated_amount_minor: number | null;
  amount_note: string | null;
}

export interface LeaksResponse {
  leaks: Leak[];
  /** Counts only. There is deliberately no euro total on this type. */
  total: number;
  with_sources: number;
  disclaimer: string;
}

export interface Targets {
  current_monthly_minor: number;
  /** Returned exactly as the user set it, including below the current income. */
  target_monthly_minor: number;
  /** The gap the product exists to close. Never negative. */
  additional_needed_minor: number;
  /** True when B sits at or below A. The band says so; it does not move B. */
  target_reached: boolean;
  currency: string;
}

// ------------------------------------------------- bank statement import

export interface StatementRow {
  booked_on: string;
  /** Negative for money leaving the account, exactly as the bank stated it. */
  amount_minor: number;
  currency: string;
  counterparty: string | null;
  reference: string;
}

export interface SuggestedExpense {
  row: StatementRow;
  /** False for everything the rules did not recognise — most of a statement. */
  suggested: boolean;
  category: ExpenseCategory | null;
  /** The word that produced the suggestion, so it can be argued with. */
  reason: string;
}

export interface Reconciliation {
  opening_minor: number | null;
  closing_minor: number | null;
  parsed_total_minor: number;
  checked: boolean;
  /** Opening + everything read equals closing. Proof the parse was complete. */
  reconciles: boolean;
}

export interface StatementPreview {
  rows: SuggestedExpense[];
  total_rows: number;
  outgoing_rows: number;
  suggested_rows: number;
  currency: string;
  /** Present for PDF statements, which print their own balances. */
  reconciliation: Reconciliation | null;
  note: string;
}

export interface StatementImportResult {
  imported: number;
  note: string;
}
