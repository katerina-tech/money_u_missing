/**
 * Formatting - and the honesty rules that live in it.
 *
 * Money is the obvious one: `formatMoney` returns "Not published" for null
 * rather than "€0", because those are different statements and a reader cannot
 * tell them apart once they are both rendered as a figure. Every other
 * formatter here follows the same principle - the absence of a value is
 * rendered as the absence of a value.
 */

import type { Money, TrustLabel } from "./types";

const LOCALE = "en-DE";

export function formatMinor(
  minor: number | null | undefined,
  currency = "EUR",
  options: { maximumFractionDigits?: number } = {},
): string {
  if (minor === null || minor === undefined) return "Not published";
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency,
    maximumFractionDigits: options.maximumFractionDigits ?? 0,
    minimumFractionDigits: 0,
  }).format(minor / 100);
}

const BASIS_SUFFIX: Record<string, string> = {
  PER_HOUR: "/hour",
  PER_DAY: "/day",
  PER_MONTH: "/month",
  PER_YEAR: "/year",
  PER_ENGAGEMENT: " per engagement",
  TOTAL: " total",
  UNKNOWN: "",
};

/**
 * A published compensation, rendered exactly as published.
 *
 * A range stays a range. A missing figure says so. The gross/net qualifier is
 * appended only when the source stated it - "€2,000/month" and "€2,000/month
 * gross" are materially different promises, and inventing the second is the
 * kind of small dishonesty that compounds.
 */
export function formatMoneyRange(money: Money): string {
  if (money.minor_min === null && money.minor_max === null) {
    return "Not published";
  }
  const suffix = BASIS_SUFFIX[money.basis] ?? "";
  const low = formatMinor(money.minor_min ?? money.minor_max, money.currency);
  const high =
    money.minor_max !== null && money.minor_max !== money.minor_min
      ? formatMinor(money.minor_max, money.currency)
      : null;
  const amount = high ? `${low}–${high}` : low;
  const treatment =
    money.tax_treatment === "GROSS" ? " gross" : money.tax_treatment === "NET" ? " net" : "";
  return `${amount}${suffix}${treatment}`;
}

export function parseMoneyInput(value: string): number | null {
  const cleaned = value.replace(/[^\d.,-]/g, "").replace(/\./g, "").replace(",", ".");
  if (!cleaned) return null;
  const parsed = Number.parseFloat(cleaned);
  return Number.isFinite(parsed) ? Math.round(parsed * 100) : null;
}

export function formatPercent(ratio: number | null | undefined, digits = 0): string {
  if (ratio === null || ratio === undefined) return "—";
  return `${(ratio * 100).toFixed(digits)}%`;
}

/**
 * Time commitment, always per week.
 *
 * The unit is fixed rather than inferred from the payment cadence, because the
 * matching engine compares this field directly against the user's stated weekly
 * availability. Rendering it as anything else would put the interface and the
 * score in disagreement about what the same number means.
 */
export function formatHours(min: number | null, max: number | null): string {
  if (min === null && max === null) return "Not published";
  const range = min !== null && max !== null && min !== max ? `${min}–${max}` : `${min ?? max}`;
  return `${range} h/week`;
}

export function formatDeadline(iso: string | null): { label: string; urgent: boolean } {
  if (!iso) return { label: "No deadline published", urgent: false };
  const deadline = new Date(`${iso}T00:00:00`);
  const days = Math.ceil((deadline.getTime() - Date.now()) / 86_400_000);
  if (days < 0) return { label: `Closed ${Math.abs(days)} days ago`, urgent: false };
  if (days === 0) return { label: "Closes today", urgent: true };
  if (days === 1) return { label: "Closes tomorrow", urgent: true };
  if (days <= 7) return { label: `Closes in ${days} days`, urgent: true };
  return {
    label: `Closes ${deadline.toLocaleDateString(LOCALE, { day: "numeric", month: "short" })}`,
    urgent: false,
  };
}

export function formatAge(days: number): string {
  if (days === 0) return "Seen today";
  if (days === 1) return "Seen yesterday";
  if (days < 30) return `Seen ${days} days ago`;
  return `Seen ${Math.round(days / 30)} months ago`;
}

export function titleCase(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export const TRUST_COPY: Record<TrustLabel, { label: string; meaning: string }> = {
  VERIFIED: {
    label: "Verified",
    meaning: "A person checked this against the source.",
  },
  SOURCE_BACKED: {
    label: "Source-backed",
    meaning: "Taken from the organisation's own published page.",
  },
  UNVERIFIED: {
    label: "Unverified",
    meaning: "Read from a page we retrieved, but not confirmed.",
  },
  DEMO: {
    label: "Demo",
    meaning: "Fictional. Shown to illustrate the product; not a real offer.",
  },
  NEEDS_REVIEW: {
    label: "Needs review",
    meaning: "Nobody has re-checked this against its source recently.",
  },
  OUTDATED: {
    label: "Outdated",
    meaning: "Past the point where we are willing to rely on it.",
  },
  UNKNOWN: {
    label: "Unknown",
    meaning: "We cannot say how well-established this is.",
  },
};

export const BAND_COPY: Record<string, { label: string; meaning: string }> = {
  HIGHLY_ACTIONABLE: {
    label: "Highly actionable",
    meaning: "Worth doing this week.",
  },
  ACTIONABLE: { label: "Actionable", meaning: "Worth doing when you have time." },
  REVIEW_FIRST: {
    label: "Review first",
    meaning: "Check something before you invest effort.",
  },
  LOW_PRIORITY: { label: "Low priority", meaning: "Something is blocking this." },
};

export const DISMISS_REASONS: { value: string; label: string }[] = [
  { value: "NOT_RELEVANT", label: "Not relevant to me" },
  { value: "TOO_LITTLE_MONEY", label: "Pays too little" },
  { value: "TOO_MUCH_TIME", label: "Takes too much time" },
  { value: "NOT_QUALIFIED", label: "I am not qualified" },
  { value: "ADMIN_BURDEN", label: "Too much admin" },
  { value: "LOCATION", label: "Wrong location" },
  { value: "DEADLINE", label: "Deadline does not work" },
  { value: "ALREADY_KNEW", label: "I already knew about it" },
  { value: "OTHER", label: "Something else" },
];
