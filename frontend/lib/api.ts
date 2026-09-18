/**
 * The API client.
 *
 * One place that talks to the backend, so error handling, token refresh and
 * the "your data is safe" degradation message are written once rather than
 * per component.
 *
 * Tokens live in `sessionStorage`, not `localStorage`: a shared laptop should
 * not leave someone signed into their income profile after the tab closes, and
 * the refresh flow makes the shorter lifetime invisible in normal use.
 */

import type {
  Application,
  BaselineIncome,
  Capabilities,
  ChildGoal,
  Expense,
  Goal,
  Household,
  LeaksResponse,
  LegalFact,
  MoneyMap,
  OpportunityDetail,
  OpportunitySummary,
  OwnershipCard,
  PersonalOverview,
  Profile,
  ProfileDraftResponse,
  Projection,
  SourceProvenance,
  StatementImportResult,
  StatementPreview,
  Targets,
  TaxAnswer,
  Tokens,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

const ACCESS_KEY = "mym.access";
const REFRESH_KEY = "mym.refresh";
const DEMO_KEY = "mym.demo";

export class ApiError extends Error {
  readonly status: number;
  /** What the user can do about it. Present when the backend offered one. */
  readonly recovery: string | null;

  constructor(message: string, status: number, recovery: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.recovery = recovery;
  }

  /** True when the feature is degraded rather than broken. */
  get isDegraded(): boolean {
    return this.status === 503;
  }
}

// ------------------------------------------------------------------ tokens

export const tokens = {
  read(): { access: string | null; refresh: string | null; isDemo: boolean } {
    if (typeof window === "undefined")
      return { access: null, refresh: null, isDemo: false };
    return {
      access: sessionStorage.getItem(ACCESS_KEY),
      refresh: sessionStorage.getItem(REFRESH_KEY),
      isDemo: sessionStorage.getItem(DEMO_KEY) === "1",
    };
  },
  write(value: Tokens): void {
    if (typeof window === "undefined") return;
    sessionStorage.setItem(ACCESS_KEY, value.access_token);
    sessionStorage.setItem(REFRESH_KEY, value.refresh_token);
    sessionStorage.setItem(DEMO_KEY, value.is_demo ? "1" : "0");
  },
  clear(): void {
    if (typeof window === "undefined") return;
    sessionStorage.removeItem(ACCESS_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
    sessionStorage.removeItem(DEMO_KEY);
  },
  get isSignedIn(): boolean {
    return tokens.read().access !== null;
  },
};

// ----------------------------------------------------------------- request

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Set false for endpoints that work signed-out (health, capabilities). */
  auth?: boolean;
  /** Internal: prevents an infinite refresh loop. */
  retried?: boolean;
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, auth = true, retried = false } = options;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const stored = tokens.read();
  if (auth && stored.access)
    headers["Authorization"] = `Bearer ${stored.access}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    // A network failure is not the same as a rejected request, and the message
    // should not imply the user did something wrong.
    throw new ApiError(
      "We could not reach the service.",
      0,
      "Check your connection and try again. Nothing you have saved is affected.",
    );
  }

  // One transparent refresh attempt, then give up. Looping on a 401 would turn
  // an expired session into a burst of requests.
  if (response.status === 401 && auth && !retried && stored.refresh) {
    const refreshed = await refreshSession(stored.refresh);
    if (refreshed) return request<T>(path, { ...options, retried: true });
    tokens.clear();
  }

  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      (payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : null) ?? "Something went wrong.";
    const recovery =
      payload && typeof payload === "object" && "recovery" in payload
        ? String((payload as { recovery: unknown }).recovery)
        : null;
    throw new ApiError(detail, response.status, recovery);
  }
  return payload as T;
}

async function refreshSession(refreshToken: string): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return false;
    tokens.write((await response.json()) as Tokens);
    return true;
  } catch {
    return false;
  }
}

// -------------------------------------------------------------------- api

export const api = {
  // --- meta
  capabilities: () =>
    request<Capabilities>("/api/capabilities", { auth: false }),
  provenance: () =>
    request<SourceProvenance[]>("/api/provenance", { auth: false }),
  health: () => request<{ status: string }>("/api/health", { auth: false }),

  // --- identity
  async signup(email: string, password: string): Promise<Tokens> {
    const result = await request<Tokens>("/api/auth/signup", {
      method: "POST",
      auth: false,
      body: { email, password, accept_privacy: true },
    });
    tokens.write(result);
    return result;
  },
  async login(email: string, password: string): Promise<Tokens> {
    const result = await request<Tokens>("/api/auth/login", {
      method: "POST",
      auth: false,
      body: { email, password },
    });
    tokens.write(result);
    return result;
  },
  async startDemo(): Promise<Tokens> {
    const result = await request<Tokens>("/api/demo/session", {
      method: "POST",
      auth: false,
    });
    tokens.write(result);
    return result;
  },
  async logout(): Promise<void> {
    try {
      await request<void>("/api/auth/logout", { method: "POST" });
    } finally {
      tokens.clear();
    }
  },
  me: () =>
    request<{ user_id: string; email: string; is_demo: boolean }>(
      "/api/auth/me",
    ),
  exportData: () => request<Record<string, unknown>>("/api/auth/export"),
  deleteAccount: async (): Promise<void> => {
    await request<void>("/api/auth/account", { method: "DELETE" });
    tokens.clear();
  },

  // --- profile
  profile: () => request<Profile>("/api/profile"),
  saveProfile: (profile: Profile) =>
    request<Profile>("/api/profile", { method: "PUT", body: profile }),
  confirmProfile: () =>
    request<Profile>("/api/profile/confirm", { method: "POST" }),
  pasteCv: (text: string) =>
    request<ProfileDraftResponse>("/api/profile/cv/paste", {
      method: "POST",
      body: { text, consent_to_process: true },
    }),
  async uploadCv(file: File): Promise<ProfileDraftResponse> {
    const form = new FormData();
    form.append("file", file);
    form.append("consent_to_process", "true");
    const stored = tokens.read();
    const response = await fetch(`${API_BASE}/api/profile/cv/upload`, {
      method: "POST",
      headers: stored.access
        ? { Authorization: `Bearer ${stored.access}` }
        : {},
      body: form,
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(
        payload && typeof payload === "object" && "detail" in payload
          ? String((payload as { detail: unknown }).detail)
          : "That file could not be processed.",
        response.status,
      );
    }
    return payload as ProfileDraftResponse;
  },
  deleteCv: () => request<void>("/api/profile/cv", { method: "DELETE" }),
  listCv: () =>
    request<
      {
        id: string;
        filename: string;
        size_bytes: number;
        uploaded_at: string;
        deleted_at: string | null;
        file_present: boolean;
        extracted_text_present: boolean;
      }[]
    >("/api/profile/cv"),
  consents: () =>
    request<
      {
        purpose: string;
        statement: string;
        granted_at: string;
        withdrawn_at: string | null;
      }[]
    >("/api/profile/consents"),

  // --- money map and opportunities
  moneyMap: () => request<MoneyMap>("/api/money-map"),
  refreshMoneyMap: () =>
    request<MoneyMap>("/api/money-map/refresh", { method: "POST" }),
  opportunities: (params: { savedOnly?: boolean; minScore?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.savedOnly) query.set("saved_only", "true");
    if (params.minScore) query.set("min_score", String(params.minScore));
    const suffix = query.toString() ? `?${query}` : "";
    return request<OpportunitySummary[]>(`/api/opportunities${suffix}`);
  },
  opportunity: (id: string) =>
    request<OpportunityDetail>(`/api/opportunities/${id}`),
  save: (id: string) =>
    request<Application>(`/api/opportunities/${id}/save`, { method: "POST" }),
  dismiss: (id: string, reason: string, note?: string) =>
    request<void>(`/api/opportunities/${id}/dismiss`, {
      method: "POST",
      body: { opportunity_id: id, reason, note: note ?? null },
    }),

  // --- actions
  applications: () => request<Application[]>("/api/applications"),
  application: (id: string) => request<Application>(`/api/applications/${id}`),
  updateWorkspace: (id: string, patch: Record<string, unknown>) =>
    request<Application>(`/api/applications/${id}`, {
      method: "PATCH",
      body: patch,
    }),
  transition: (id: string, status: string, outcome?: Record<string, unknown>) =>
    request<Application>(`/api/applications/${id}/status`, {
      method: "POST",
      body: { status, outcome: outcome ?? null },
    }),
  draft: (id: string, kind: string) =>
    request<{ kind: string; text: string; note: string }>(
      `/api/applications/${id}/draft`,
      {
        method: "POST",
        body: { kind },
      },
    ),
  income: () =>
    request<
      {
        id: string;
        label: string;
        amount_minor: number;
        currency: string;
        period: string;
        money_state: string;
        occurred_on: string;
      }[]
    >("/api/income"),

  // --- keep
  askTax: (question: string) =>
    request<TaxAnswer>("/api/tax/ask", { method: "POST", body: { question } }),
  legalFacts: () => request<LegalFact[]>("/api/tax/facts", { auth: false }),
  knowledgeStatus: () =>
    request<Record<string, unknown>>("/api/tax/status", { auth: false }),

  // --- grow and family
  goals: () => request<Goal[]>("/api/goals"),
  createGoal: (goal: Record<string, unknown>) =>
    request<Goal>("/api/goals", { method: "POST", body: goal }),
  deleteGoal: (id: string) =>
    request<void>(`/api/goals/${id}`, { method: "DELETE" }),
  project: (input: {
    initial_minor: number;
    monthly_contribution_minor: number;
    annual_return: number;
    months: number;
    annual_inflation?: number | null;
  }) =>
    request<Projection>("/api/grow/project", {
      method: "POST",
      auth: false,
      body: input,
    }),
  etfEducation: () =>
    request<{
      disclaimer: string;
      terms: { term: string; explanation: string }[];
    }>("/api/grow/etf-education", { auth: false }),
  childGoals: () => request<ChildGoal[]>("/api/family/goals"),
  createChildGoal: (goal: Record<string, unknown>) =>
    request<ChildGoal>("/api/family/goals", { method: "POST", body: goal }),
  deleteChildGoal: (id: string) =>
    request<void>(`/api/family/goals/${id}`, { method: "DELETE" }),
  ownership: () =>
    request<OwnershipCard>("/api/family/ownership", { auth: false }),

  // --- personal money
  personalOverview: () => request<PersonalOverview>("/api/personal/overview"),
  leaks: () => request<LeaksResponse>("/api/personal/leaks"),
  async previewStatement(file: File): Promise<StatementPreview> {
    const form = new FormData();
    form.append("file", file);
    const stored = tokens.read();
    const response = await fetch(
      `${API_BASE}/api/personal/statements/preview`,
      {
        method: "POST",
        headers: stored.access
          ? { Authorization: `Bearer ${stored.access}` }
          : {},
        body: form,
      },
    );
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(
        payload && typeof payload === "object" && "detail" in payload
          ? String((payload as { detail: unknown }).detail)
          : "That file could not be read.",
        response.status,
      );
    }
    return payload as StatementPreview;
  },
  importStatement: (items: Record<string, unknown>[]) =>
    request<StatementImportResult>("/api/personal/statements/import", {
      method: "POST",
      body: { items },
    }),
  targets: () => request<Targets>("/api/personal/targets"),
  setTargets: (current_monthly_minor: number, target_monthly_minor: number) =>
    request<Targets>("/api/personal/targets", {
      method: "PUT",
      body: { current_monthly_minor, target_monthly_minor },
    }),
  baselineIncome: () => request<BaselineIncome[]>("/api/personal/income"),
  addBaselineIncome: (entry: Record<string, unknown>) =>
    request<BaselineIncome>("/api/personal/income", {
      method: "POST",
      body: entry,
    }),
  deleteBaselineIncome: (id: string) =>
    request<void>(`/api/personal/income/${id}`, { method: "DELETE" }),
  expenses: () => request<Expense[]>("/api/personal/expenses"),
  addExpense: (entry: Record<string, unknown>) =>
    request<Expense>("/api/personal/expenses", { method: "POST", body: entry }),
  deleteExpense: (id: string) =>
    request<void>(`/api/personal/expenses/${id}`, { method: "DELETE" }),
  setHousehold: (payload: Record<string, unknown>) =>
    request<Household>("/api/personal/household", {
      method: "PUT",
      body: payload,
    }),

  // --- validation
  feedback: (payload: {
    question: string;
    answer: string;
    reason?: string | null;
    note?: string | null;
    opportunity_id?: string | null;
  }) =>
    request<{ id: string }>("/api/feedback", { method: "POST", body: payload }),
  preferences: () => request<Record<string, unknown>>("/api/preferences"),
  resetPreferences: () =>
    request<void>("/api/preferences", { method: "DELETE" }),
  outcomes: () => request<Record<string, unknown>>("/api/outcomes"),
  metrics: () =>
    request<Record<string, unknown>>("/api/metrics", { auth: false }),
};
