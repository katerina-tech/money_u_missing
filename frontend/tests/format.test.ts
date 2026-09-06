/**
 * Formatting tests.
 *
 * These are the frontend half of "unknown is not false". The backend refuses to
 * invent a figure; these tests check the interface refuses to *render* one -
 * because a null that formats as "€0" undoes the whole guarantee at the last
 * step, in the only place the user actually looks.
 */

import { describe, expect, it } from "vitest";

import {
  BAND_COPY,
  DISMISS_REASONS,
  TRUST_COPY,
  formatAge,
  formatDeadline,
  formatHours,
  formatMinor,
  formatMoneyRange,
  formatPercent,
  parseMoneyInput,
  titleCase,
} from "../lib/format";
import type { Money } from "../lib/types";

function money(overrides: Partial<Money> = {}): Money {
  return {
    minor_min: null,
    minor_max: null,
    currency: "EUR",
    basis: "UNKNOWN",
    period: "UNKNOWN",
    tax_treatment: "UNKNOWN",
    verified: false,
    unknown_note: null,
    ...overrides,
  };
}

describe("money is never invented", () => {
  it("renders null as 'Not published', never as zero", () => {
    expect(formatMinor(null)).toBe("Not published");
    expect(formatMinor(undefined)).toBe("Not published");
    expect(formatMoneyRange(money())).toBe("Not published");
  });

  it("distinguishes an unpublished amount from a genuine zero", () => {
    expect(formatMinor(null)).not.toBe(formatMinor(0));
    expect(formatMinor(0)).toContain("0");
  });

  it("keeps a published range as a range", () => {
    const formatted = formatMoneyRange(
      money({ minor_min: 85_000, minor_max: 110_000, basis: "PER_DAY" }),
    );
    expect(formatted).toContain("850");
    expect(formatted).toContain("1,100");
    expect(formatted).toContain("/day");
  });

  it("collapses a single figure rather than showing a range of one", () => {
    const formatted = formatMoneyRange(money({ minor_min: 15_000, minor_max: 15_000 }));
    expect(formatted).not.toContain("–");
  });

  it("only says gross or net when the source did", () => {
    expect(formatMoneyRange(money({ minor_min: 1000, tax_treatment: "GROSS" }))).toContain(
      "gross",
    );
    expect(formatMoneyRange(money({ minor_min: 1000, tax_treatment: "UNKNOWN" }))).not.toMatch(
      /gross|net/,
    );
  });

  it("round-trips a typed amount into minor units", () => {
    expect(parseMoneyInput("850")).toBe(85_000);
    expect(parseMoneyInput("1.500,50")).toBe(150_050);
    expect(parseMoneyInput("€ 2,5")).toBe(250);
    expect(parseMoneyInput("")).toBeNull();
    expect(parseMoneyInput("abc")).toBeNull();
  });
});

describe("other absences", () => {
  it("says so when hours are not published", () => {
    expect(formatHours(null, null)).toBe("Not published");
  });

  it("always expresses hours per week, matching what the scorer compares", () => {
    expect(formatHours(4, 8)).toBe("4–8 h/week");
    expect(formatHours(2, 2)).toBe("2 h/week");
  });

  it("does not pretend a missing deadline is no deadline", () => {
    expect(formatDeadline(null).label).toBe("No deadline published");
  });

  it("marks an imminent deadline as urgent and a distant one as not", () => {
    const soon = new Date(Date.now() + 2 * 86_400_000).toISOString().slice(0, 10);
    const far = new Date(Date.now() + 90 * 86_400_000).toISOString().slice(0, 10);
    expect(formatDeadline(soon).urgent).toBe(true);
    expect(formatDeadline(far).urgent).toBe(false);
  });

  it("reports a passed deadline as passed rather than hiding it", () => {
    const past = new Date(Date.now() - 3 * 86_400_000).toISOString().slice(0, 10);
    expect(formatDeadline(past).label).toContain("Closed");
    expect(formatDeadline(past).urgent).toBe(false);
  });

  it("renders a null ratio as a dash, not as zero percent", () => {
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(0)).toBe("0%");
  });
});

describe("vocabulary", () => {
  it("gives every trust label a plain-language meaning", () => {
    for (const [label, copy] of Object.entries(TRUST_COPY)) {
      expect(copy.label.length, label).toBeGreaterThan(0);
      expect(copy.meaning.length, label).toBeGreaterThan(10);
    }
  });

  it("never describes a demo record as anything but fictional", () => {
    expect(TRUST_COPY.DEMO.meaning.toLowerCase()).toContain("fictional");
    expect(TRUST_COPY.DEMO.meaning.toLowerCase()).toContain("not a real offer");
  });

  it("describes actionability as priority, never as predicted income", () => {
    for (const copy of Object.values(BAND_COPY)) {
      expect(copy.meaning.toLowerCase()).not.toMatch(/eur|€|income|earn/);
    }
  });

  it("offers the full dismiss-reason vocabulary the backend accepts", () => {
    const values = DISMISS_REASONS.map((reason) => reason.value);
    for (const expected of [
      "NOT_RELEVANT",
      "TOO_LITTLE_MONEY",
      "TOO_MUCH_TIME",
      "NOT_QUALIFIED",
      "ADMIN_BURDEN",
      "LOCATION",
      "DEADLINE",
      "ALREADY_KNEW",
      "OTHER",
    ]) {
      expect(values).toContain(expected);
    }
  });

  it("humanises enum values", () => {
    expect(titleCase("EXPERT_CALL")).toBe("Expert Call");
    expect(titleCase("WON")).toBe("Won");
  });

  it("describes recency without pretending to precision", () => {
    expect(formatAge(0)).toBe("Seen today");
    expect(formatAge(1)).toBe("Seen yesterday");
    expect(formatAge(45)).toContain("months");
  });
});
