"use client";

/**
 * A to B: what you earn now, what you want to earn, and the two ways there.
 *
 * The product's central claim rendered as one object, so it carries the
 * product's central discipline too.
 *
 * **A and B are the user's own figures, and both are editable here.** Someone
 * looking at this should be able to say "I earn 2,000, I want 4,000" without
 * hunting through a profile form. They are sent as a pair, because the profile
 * stores the *additional* income being aimed for - raising A with B left alone
 * would otherwise silently raise the target too.
 *
 * **Two directions, given equal weight as blocks.** Earning more is the
 * product's main promise; keeping more is what is available in a week when no
 * new opportunity appears. Neither block shows a euro figure it cannot defend:
 * the earn side labels its potential as potential, and the keep side shows a
 * count of things to check, never a sum of statutory ceilings the user may not
 * qualify for.
 *
 * **The rails below are unchanged in their honesty.** The goal rail is fed by
 * `goal_progress_ratio`, computed by the backend from secured and earned money
 * only, so no front-end change can start counting potential as progress.
 * Potential sits on its own dashed track, captioned as a hypothetical. An empty
 * pipeline stage is drawn hollow rather than hidden.
 */

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatMinor, parseMoneyInput } from "@/lib/format";
import type {
  Application,
  ApplicationStatus,
  MoneyMap,
  Targets,
} from "@/lib/types";

type StageId = "found" | "applied" | "offered" | "secured" | "earned";

interface Stage {
  id: StageId;
  label: string;
  meaning: string;
  count: number;
  items: {
    id: string;
    title: string;
    organization: string | null;
    href: string;
  }[];
  committed: boolean;
}

const APPLIED_STATUSES: ApplicationStatus[] = ["APPLIED", "INTERVIEW"];

export function MoneyJourney({
  map,
  applications,
  leakCount = null,
}: {
  map: MoneyMap;
  applications: Application[] | null;
  /** How many things are worth checking on the keep side. */
  leakCount?: number | null;
}) {
  const [open, setOpen] = useState<StageId | null>(null);
  const [targets, setTargets] = useState<Targets | null>(null);

  useEffect(() => {
    void api
      .targets()
      .then(setTargets)
      .catch(() => setTargets(null));
  }, []);

  const stages = useMemo<Stage[]>(() => {
    const apps = applications ?? [];
    const byStatus = (statuses: ApplicationStatus[]) =>
      apps.filter((application) => statuses.includes(application.status));

    const toItem = (application: Application) => ({
      id: application.id,
      title: application.opportunity_title,
      organization: application.organization,
      href: `/actions/${application.id}`,
    });

    const applied = byStatus(APPLIED_STATUSES);
    const offered = byStatus(["OFFERED"]);
    const won = byStatus(["WON"]);

    return [
      {
        id: "found",
        label: "Found",
        meaning:
          "Matched to your profile from real sources. Nothing here is an offer, and nothing here is money.",
        count: map.opportunities.length,
        items: map.opportunities.slice(0, 6).map((opportunity) => ({
          id: opportunity.id,
          title: opportunity.title,
          organization: opportunity.organization,
          href: `/opportunities/${opportunity.id}`,
        })),
        committed: false,
      },
      {
        id: "applied",
        label: "Applied",
        meaning: "You have put yourself forward. Still potential, not income.",
        count: applied.length,
        items: applied.map(toItem),
        committed: false,
      },
      {
        id: "offered",
        label: "Offered",
        meaning:
          "Someone has offered you the work. Money becomes likely here, not certain.",
        count: offered.length,
        items: offered.map(toItem),
        committed: false,
      },
      {
        id: "secured",
        label: "Secured",
        meaning:
          "Agreed and committed. This is the first stage that moves the goal rail.",
        count: map.summary.secured_count || won.length,
        items: won.map(toItem),
        committed: true,
      },
      {
        id: "earned",
        label: "Earned",
        meaning:
          "Actually paid, at the figure you entered — not the figure that was advertised.",
        count: map.summary.earned_count,
        items: [],
        committed: true,
      },
    ];
  }, [map, applications]);

  const ratio = map.goal_progress_ratio;
  const percent =
    ratio === null ? 0 : Math.round(Math.min(1, Math.max(0, ratio)) * 100);

  const potentialMonthly = map.summary.recurring_potential_monthly_minor;
  const goal = map.goal_monthly_minor;
  const potentialPercent =
    goal && goal > 0 && potentialMonthly > 0
      ? Math.round(Math.min(1, potentialMonthly / goal) * 100)
      : 0;

  const openStage = stages.find((stage) => stage.id === open) ?? null;
  const lastCommittedIndex = stages.reduce(
    (last, stage, index) => (stage.count > 0 ? index : last),
    -1,
  );

  const currency = targets?.currency ?? map.currency;
  const opportunityCount = map.opportunities.length;

  async function save(current: number, target: number) {
    setTargets(await api.setTargets(current, target));
  }

  return (
    <section
      aria-label="From where you are to where you want to be"
      className="mb-8 overflow-hidden rounded-[--radius-card] border border-rule bg-paper-raised"
    >
      {/* ============================================ A and B, the poles */}
      <div className="border-b border-rule bg-cobalt-wash/50 p-6 sm:p-8">
        <div className="grid gap-8 sm:grid-cols-[1fr_auto_1fr] sm:items-center sm:gap-4">
          <Pole
            badge="A"
            label="What you earn now"
            amountMinor={targets?.current_monthly_minor ?? null}
            currency={currency}
            emptyPrompt="Add it"
            tone="ink"
            onSave={
              targets
                ? (value) => save(value, targets.target_monthly_minor)
                : undefined
            }
          />

          <div
            aria-hidden="true"
            className="hidden justify-self-center text-3xl text-cobalt/40 sm:block"
          >
            →
          </div>

          <Pole
            badge="B"
            label="What you want to earn"
            amountMinor={targets?.target_monthly_minor ?? null}
            currency={currency}
            emptyPrompt="Set it"
            tone="cobalt"
            align="right"
            onSave={
              targets
                ? (value) => save(targets.current_monthly_minor, value)
                : undefined
            }
          />
        </div>

        {/* The gap is the product's whole reason for existing, so it is stated
            once and plainly rather than left for the reader to subtract. */}
        {targets?.target_reached ? (
          <p className="mt-7 border-t border-cobalt/15 pt-5 text-center text-sm text-ink-muted">
            You are already earning at or above your target. Your figure is kept
            as you set it — raise B if you want this product to look for more.
          </p>
        ) : targets && targets.additional_needed_minor > 0 ? (
          <p className="mt-7 border-t border-cobalt/15 pt-5 text-center text-sm">
            <span className="text-ink-muted">The distance is </span>
            <span className="tnum font-semibold">
              {formatMinor(targets.additional_needed_minor, currency)} a month
            </span>
            <span className="text-ink-muted">
              . That is what this product is for.
            </span>
          </p>
        ) : null}
      </div>

      {/* ================================================ the two directions */}
      <div className="grid gap-px border-b border-rule bg-rule sm:grid-cols-2">
        <DirectionBlock
          arrow="↗"
          title="Earn more"
          href="/opportunities"
          cta="See the opportunities"
          primary
          lines={[
            `${opportunityCount} opportunit${opportunityCount === 1 ? "y" : "ies"} matched to your profile`,
            potentialMonthly > 0
              ? `${formatMinor(potentialMonthly, currency)}/month of recurring potential — none of it agreed`
              : "No recurring potential with a published figure yet",
          ]}
        />
        <DirectionBlock
          arrow="↘"
          title="Keep more"
          href="/personal"
          cta="Open your money"
          lines={[
            leakCount === null
              ? "Costs, allowances and limits worth checking"
              : `${leakCount} thing${leakCount === 1 ? "" : "s"} worth checking, raised from what you told us`,
            "Recorded and cited — never a calculated saving",
          ]}
        />
      </div>

      {/* ==================================================== the pipeline */}
      <div className="p-5 sm:p-6">
        <p className="eyebrow mb-4">How the earning side is going</p>
        <ol className="grid grid-cols-5 gap-1 sm:gap-2">
          {stages.map((stage, index) => {
            const filled = stage.count > 0;
            const isOpen = open === stage.id;
            return (
              <li key={stage.id} className="relative">
                {index > 0 ? (
                  <span
                    aria-hidden="true"
                    className={
                      "absolute top-[11px] right-1/2 left-0 h-px " +
                      (index <= lastCommittedIndex
                        ? "bg-rule-strong"
                        : "bg-rule")
                    }
                  />
                ) : null}
                {index < stages.length - 1 ? (
                  <span
                    aria-hidden="true"
                    className={
                      "absolute top-[11px] right-0 left-1/2 h-px " +
                      (index < lastCommittedIndex
                        ? "bg-rule-strong"
                        : "bg-rule")
                    }
                  />
                ) : null}

                <button
                  type="button"
                  onClick={() => setOpen(isOpen ? null : stage.id)}
                  aria-expanded={isOpen}
                  aria-controls="money-journey-detail"
                  className="group relative flex w-full flex-col items-center gap-1.5 rounded-[4px] py-1 outline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cobalt"
                >
                  <span
                    aria-hidden="true"
                    className={
                      "flex h-[22px] w-[22px] items-center justify-center rounded-full border-2 transition-colors " +
                      (isOpen
                        ? "border-cobalt bg-cobalt"
                        : filled
                          ? stage.committed
                            ? "border-verified bg-verified"
                            : "border-rule-strong bg-paper-raised"
                          : "border-rule bg-paper-raised")
                    }
                  >
                    {filled && !stage.committed && !isOpen ? (
                      <span className="h-[7px] w-[7px] rounded-full bg-rule-strong" />
                    ) : null}
                  </span>

                  <span className="tnum text-lg leading-none font-semibold sm:text-xl">
                    {stage.count}
                  </span>
                  <span
                    className={
                      "text-center text-[11px] leading-tight sm:text-xs " +
                      (filled ? "text-ink-muted" : "text-ink-faint")
                    }
                  >
                    {stage.label}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>

        <div id="money-journey-detail" className="mt-4">
          {openStage ? (
            <div className="rounded-[4px] border border-rule bg-paper-sunk p-4">
              <p className="text-sm">{openStage.meaning}</p>
              {openStage.items.length > 0 ? (
                <ul className="mt-3 space-y-1.5 border-t border-rule pt-3">
                  {openStage.items.map((item) => (
                    <li key={item.id} className="text-sm">
                      <Link
                        href={item.href}
                        className="text-cobalt underline underline-offset-4"
                      >
                        {item.title}
                      </Link>
                      {item.organization ? (
                        <span className="text-ink-faint">
                          {" "}
                          · {item.organization}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : openStage.count > 0 ? (
                <p className="mt-2 text-xs text-ink-faint">
                  {openStage.id === "earned"
                    ? "Recorded income is listed on the income page."
                    : "Nothing to list for this stage."}
                </p>
              ) : (
                <p className="mt-2 text-xs text-ink-faint">
                  Nothing has reached this stage yet.
                </p>
              )}
            </div>
          ) : (
            <p className="text-center text-xs text-ink-faint">
              Select a stage to see what is in it.
            </p>
          )}
        </div>
      </div>

      {/* ====================================================== the rails */}
      <div className="border-t border-rule bg-paper-sunk p-5 sm:p-6">
        <div className="mb-1.5 flex items-baseline justify-between text-sm">
          <span className="text-ink-muted">Progress towards B</span>
          <span className="tnum font-medium">
            {ratio === null ? "—" : `${percent}%`}
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Progress towards your monthly goal, from secured and earned money only"
          className="h-2.5 overflow-hidden rounded-full bg-paper-raised ring-1 ring-rule ring-inset"
        >
          <div
            className="h-full rounded-full bg-cobalt transition-[width] duration-500"
            style={{ width: `${percent}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-ink-faint">
          {copy.money.progressExplainer}
        </p>

        {potentialPercent > 0 ? (
          <div className="mt-4 border-t border-rule pt-4">
            <div className="mb-1.5 flex items-baseline justify-between text-sm">
              <span className="text-ink-faint">
                If the potential above converted
              </span>
              <span className="tnum text-ink-faint">{potentialPercent}%</span>
            </div>
            <div
              aria-hidden="true"
              className="h-2.5 rounded-full border border-dashed border-rule-strong"
            >
              <div
                className="h-full rounded-full bg-[repeating-linear-gradient(45deg,var(--color-rule-strong)_0_4px,transparent_4px_8px)] opacity-70"
                style={{ width: `${potentialPercent}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-ink-faint">
              Hypothetical, and not counted anywhere else on this page.
              Recurring potential of {formatMinor(potentialMonthly, currency)}
              /month across {map.summary.recurring_potential_count} opportunit
              {map.summary.recurring_potential_count === 1 ? "y" : "ies"} — none
              of it agreed, none of it paid.
            </p>
          </div>
        ) : null}
      </div>
    </section>
  );
}

/** One end of the journey. Click the figure to change it. */
function Pole({
  badge,
  label,
  amountMinor,
  currency,
  emptyPrompt,
  tone,
  align = "left",
  onSave,
}: {
  badge: string;
  label: string;
  amountMinor: number | null;
  currency: string;
  emptyPrompt: string;
  tone: "ink" | "cobalt";
  align?: "left" | "right";
  onSave?: (valueMinor: number) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const right = align === "right";
  const isSet = amountMinor !== null && amountMinor > 0;

  async function commit() {
    const parsed = parseMoneyInput(draft);
    if (parsed === null || !onSave) {
      setEditing(false);
      return;
    }
    setBusy(true);
    try {
      await onSave(parsed);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={right ? "sm:text-right" : undefined}>
      <p className={"eyebrow mb-2 " + (right ? "sm:justify-end" : "")}>
        <span
          className={
            "mr-1.5 inline-block rounded-[3px] px-1.5 py-px font-mono text-[10px] text-paper " +
            (tone === "cobalt" ? "bg-cobalt" : "bg-ink")
          }
        >
          {badge}
        </span>
        {label}
      </p>

      {editing ? (
        <div
          className={
            "flex items-center gap-1.5 " + (right ? "sm:justify-end" : "")
          }
        >
          <span className="text-3xl text-ink-faint sm:text-4xl">€</span>
          <input
            autoFocus
            inputMode="decimal"
            value={draft}
            disabled={busy}
            aria-label={label}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={() => void commit()}
            onKeyDown={(event) => {
              if (event.key === "Enter") void commit();
              if (event.key === "Escape") setEditing(false);
            }}
            className="tnum w-40 border-b-2 border-cobalt bg-transparent text-4xl leading-none font-semibold outline-none sm:text-5xl"
          />
        </div>
      ) : (
        <button
          type="button"
          disabled={!onSave}
          onClick={() => {
            setDraft(isSet ? String(Math.round((amountMinor ?? 0) / 100)) : "");
            setEditing(true);
          }}
          className={
            "group flex items-baseline gap-2 rounded-[4px] outline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cobalt " +
            (right ? "sm:ml-auto" : "")
          }
        >
          <span
            className={
              "tnum text-4xl leading-none font-semibold sm:text-5xl " +
              (tone === "cobalt" ? "text-cobalt" : "text-ink")
            }
          >
            {isSet ? formatMinor(amountMinor, currency) : emptyPrompt}
          </span>
          {onSave ? (
            <span
              aria-hidden="true"
              className="text-xs text-ink-faint opacity-60 transition-opacity group-hover:opacity-100"
            >
              edit
            </span>
          ) : null}
        </button>
      )}

      <p className="mt-2 text-xs text-ink-faint">
        {isSet ? "per month" : "click to set it"}
      </p>
    </div>
  );
}

/** One of the two ways to close the distance. */
function DirectionBlock({
  arrow,
  title,
  lines,
  href,
  cta,
  primary = false,
}: {
  arrow: string;
  title: string;
  lines: string[];
  href: string;
  cta: string;
  primary?: boolean;
}) {
  return (
    <div className="bg-paper-raised p-5 sm:p-6">
      <p className="mb-2.5 flex items-center gap-2">
        <span
          aria-hidden="true"
          className={
            "text-2xl leading-none " +
            (primary ? "text-cobalt" : "text-ink-muted")
          }
        >
          {arrow}
        </span>
        <span className="text-lg font-semibold">{title}</span>
      </p>
      <ul className="space-y-1">
        {lines.map((line) => (
          <li key={line} className="text-sm text-ink-muted">
            {line}
          </li>
        ))}
      </ul>
      <Link
        href={href}
        className="mt-4 inline-block text-sm text-cobalt underline underline-offset-4"
      >
        {cta} →
      </Link>
    </div>
  );
}
