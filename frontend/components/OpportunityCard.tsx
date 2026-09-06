"use client";

/**
 * The opportunity card.
 *
 * Every card carries, without exception: a trust badge, the compensation as
 * published (or "not published"), the time commitment, the deadline, and the
 * match score. A card that omitted one because it was unknown would let the
 * reader assume the missing thing was fine.
 *
 * Blocked opportunities are shown, greyed, with the reason - not hidden.
 * Hiding them would leave someone wondering where last week's listing went.
 */

import Link from "next/link";

import { BandBadge, MoneyFigure, TrustBadge } from "@/components/ui";
import { formatAge, formatDeadline, formatHours, titleCase } from "@/lib/format";
import type { OpportunitySummary } from "@/lib/types";

export function OpportunityCard({
  opportunity,
  onDismiss,
}: {
  opportunity: OpportunitySummary;
  onDismiss?: (id: string) => void;
}) {
  const match = opportunity.match;
  const blocked = match !== null && !match.eligible;
  const deadline = formatDeadline(opportunity.deadline);

  return (
    <article
      className={`rounded-[--radius-card] border bg-paper-raised p-5 transition-colors ${
        blocked ? "border-rule opacity-70" : "border-rule hover:border-rule-strong"
      }`}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <TrustBadge trust={opportunity.trust} size="xs" />
        <span className="text-[11px] uppercase tracking-wide text-ink-faint">
          {titleCase(opportunity.category)}
        </span>
        {opportunity.actionability ? (
          <BandBadge band={opportunity.actionability.band} />
        ) : null}
        {opportunity.is_sponsored ? (
          <span className="rounded-full border border-rule-strong px-2 py-0.5 text-[10px] uppercase tracking-wide text-ink-faint">
            Sponsored
          </span>
        ) : null}
        {opportunity.safety_verdict === "FLAGGED" ? (
          <span
            className="rounded-full border border-unverified/30 bg-unverified-wash px-2 py-0.5 text-[10px] font-medium text-unverified"
            title={opportunity.safety_reasons.join(" ")}
          >
            Check carefully
          </span>
        ) : null}
      </div>

      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-base font-semibold leading-snug">
            <Link href={`/opportunities/${opportunity.id}`} className="hover:underline">
              {opportunity.title}
            </Link>
          </h3>
          <p className="mt-0.5 text-sm text-ink-muted">
            {opportunity.organization ?? "Organisation not stated"}
            {opportunity.city ? ` · ${opportunity.city}` : ""}
            {opportunity.remote_type !== "UNKNOWN"
              ? ` · ${titleCase(opportunity.remote_type)}`
              : ""}
          </p>
        </div>
        {match ? (
          <div className="shrink-0 text-right">
            <p className={`tnum text-2xl font-semibold ${blocked ? "text-ink-faint" : ""}`}>
              {match.total_score}%
            </p>
            <p className="text-[11px] text-ink-faint">match</p>
          </div>
        ) : null}
      </div>

      {blocked && match ? (
        <p className="mt-3 rounded-[4px] border border-danger/25 bg-danger-wash px-3 py-2 text-xs text-danger">
          {match.hard_failures[0]?.explanation ?? "You do not meet a stated requirement."}
        </p>
      ) : null}

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="eyebrow mb-0.5">Pay</dt>
          <dd>
            <MoneyFigure money={opportunity.compensation} />
          </dd>
        </div>
        <div>
          <dt className="eyebrow mb-0.5">Time</dt>
          <dd className={opportunity.estimated_hours_min === null ? "text-ink-faint italic" : ""}>
            {formatHours(opportunity.estimated_hours_min, opportunity.estimated_hours_max)}
          </dd>
        </div>
        <div>
          <dt className="eyebrow mb-0.5">Deadline</dt>
          <dd className={deadline.urgent ? "font-medium text-danger" : "text-ink-muted"}>
            {deadline.label}
          </dd>
        </div>
      </dl>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-3">
        <p className="text-xs text-ink-faint">
          {opportunity.source_name} · {formatAge(opportunity.last_seen_days_ago)}
        </p>
        <div className="flex items-center gap-3">
          {opportunity.application_status ? (
            <span className="text-xs font-medium text-cobalt">
              {titleCase(opportunity.application_status)}
            </span>
          ) : null}
          {onDismiss ? (
            <button
              type="button"
              onClick={() => onDismiss(opportunity.id)}
              className="text-xs text-ink-faint underline underline-offset-4 hover:text-ink"
            >
              Not for me
            </button>
          ) : null}
          <Link
            href={`/opportunities/${opportunity.id}`}
            className="text-xs font-medium text-cobalt underline underline-offset-4"
          >
            View opportunity
          </Link>
        </div>
      </div>
    </article>
  );
}
