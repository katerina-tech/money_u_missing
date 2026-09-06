/**
 * API client tests.
 *
 * The interesting behaviour is not the happy path - it is what happens when the
 * session expires mid-request, when the network is gone, and whether tokens
 * outlive a closed tab.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, tokens } from "../lib/api";

const storage = new Map<string, string>();

beforeEach(() => {
  storage.clear();
  vi.stubGlobal("sessionStorage", {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => void storage.set(key, value),
    removeItem: (key: string) => void storage.delete(key),
  });
  vi.stubGlobal("window", {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("token storage", () => {
  it("uses sessionStorage so a closed tab ends the session", () => {
    tokens.write({
      access_token: "a",
      refresh_token: "r",
      token_type: "bearer",
      expires_in: 1800,
      user_id: "u1",
      email: "x@example.com",
      is_demo: false,
    });
    expect(storage.get("mym.access")).toBe("a");
    // Nothing is written to localStorage; the module never touches it.
    expect(tokens.isSignedIn).toBe(true);
    tokens.clear();
    expect(tokens.isSignedIn).toBe(false);
  });

  it("records demo sessions so the UI can badge them", () => {
    tokens.write({
      access_token: "a",
      refresh_token: "r",
      token_type: "bearer",
      expires_in: 60,
      user_id: "u1",
      email: null,
      is_demo: true,
    });
    expect(tokens.read().isDemo).toBe(true);
  });
});

describe("error handling", () => {
  it("surfaces the backend's message and its recovery advice", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: "Draft writing is unavailable.", recovery: "Try later." }, 503),
      ),
    );
    await expect(api.capabilities()).rejects.toMatchObject({
      message: "Draft writing is unavailable.",
      status: 503,
    });
  });

  it("flags a 503 as a degradation rather than a failure", async () => {
    const error = new ApiError("unavailable", 503);
    expect(error.isDegraded).toBe(true);
    expect(new ApiError("bad", 400).isDegraded).toBe(false);
  });

  it("does not blame the user for a network failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    await expect(api.health()).rejects.toMatchObject({
      status: 0,
    });
    await api.health().catch((error: ApiError) => {
      expect(error.recovery).toContain("Nothing you have saved is affected");
    });
  });
});

describe("session refresh", () => {
  it("refreshes once on a 401 and retries the original request", async () => {
    tokens.write({
      access_token: "expired",
      refresh_token: "refresh-me",
      token_type: "bearer",
      expires_in: 0,
      user_id: "u1",
      email: null,
      is_demo: false,
    });

    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        if (url.endsWith("/api/auth/refresh")) {
          return jsonResponse({
            access_token: "fresh",
            refresh_token: "r2",
            token_type: "bearer",
            expires_in: 1800,
            user_id: "u1",
            email: null,
            is_demo: false,
          });
        }
        // First protected call fails, the retry succeeds.
        return calls.filter((c) => c.endsWith("/api/profile")).length === 1
          ? jsonResponse({ detail: "expired" }, 401)
          : jsonResponse({ display_name: "Sam" });
      }),
    );

    const profile = await api.profile();
    expect(profile.display_name).toBe("Sam");
    expect(calls.filter((c) => c.endsWith("/api/auth/refresh"))).toHaveLength(1);
    expect(storage.get("mym.access")).toBe("fresh");
  });

  it("gives up and clears the session when the refresh also fails", async () => {
    tokens.write({
      access_token: "expired",
      refresh_token: "stale",
      token_type: "bearer",
      expires_in: 0,
      user_id: "u1",
      email: null,
      is_demo: false,
    });
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "no" }, 401)));

    await expect(api.profile()).rejects.toMatchObject({ status: 401 });
    expect(tokens.isSignedIn).toBe(false);
  });
});
