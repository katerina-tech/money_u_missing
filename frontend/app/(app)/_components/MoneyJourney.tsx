"use client";

/**
 * A to B: where your money is now, where you want it, and what sits between.
 *
 * This is the product's central claim rendered as one object, so it has to
 * carry the product's central discipline too. Three rules are structural here,
 * not stylistic:
 *
 * 1. The goal rail is fed by `goal_progress_ratio`, which the backend computes
 *    from secured and earned money only. This component never derives it, so a
 *    front-end change cannot quietly start counting potential towards a goal.
 * 2. Potential is drawn on its own track, dashed, below the rail, and captioned
 *    as a hypothetical. It is never added to the rail and never shares its
 *    colour. Someone glancing at this for two seconds must not come away
 *    believing they have earned money they have not.
 * 3. A stage with nothing in it is drawn hollow rather than hidden. An empty
 *    pipeline is information; a pipeline that hides its empty stages is a
 *    picture of progress that has not happened.
 *
 * Interactive: selecting a stage lists what is actually in it. The counts are
 * the claim; the list is the evidence for it.
 */

import Link from "next/link";
import { useMemo, useState } from "react";

import { copy } from "@/lib/copy";
import { formatMinor } from "@/lib/format";
import type { Application, ApplicationStatus, MoneyMap } from "@/lib/types";

type StageId = "found" | "applied" | "offered" | "secured" | "earned";

interface Stage {
  id: StageId;
  label: string;
  /** What being in this stage actually means. Shown when the stage is open. */
  meaning: string;
  count: number;
  items: {
    id: string;
    title: string;
    organization: string | null;
    href: string;
  }[];
  /** Committed stages are drawn solid; potential ones are drawn muted. */
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
  /** How many things are worth checking on the keep side. `null` while it
   *  loads or if it fails - the band renders either way. */
  leakCount?: number | null;
}) {
  const [open, setOpen] = useState<StageId | null>(null);

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

  const goal = map.goal_monthly_minor;
  const ratio = map.goal_progress_ratio;
  const percent =
    ratio === null ? 0 : Math.round(Math.min(1, Math.max(0, ratio)) * 100);

  // The hypothetical track. Deliberately computed separately and never mixed
  // into `percent` above.
  const potentialMonthly = map.summary.recurring_potential_monthly_minor;
  const potentialPercent =
    goal && goal > 0 && potentialMonthly > 0
      ? Math.round(Math.min(1, potentialMonthly / goal) * 100)
      : 0;

  const openStage = stages.find((stage) => stage.id === open) ?? null;
  const lastCommittedIndex = stages.reduce(
    (last, stage, index) => (stage.count > 0 ? index : last),
    -1,
  );

  return (
    <section
      aria-label="From where you are to where you want to be"
      className="mb-8 overflow-hidden rounded-[--radius-card] border border-rule bg-paper-raised"
    >
      {/* ------------------------------------------------ A and B, the poles */}
      <div className="grid gap-6 border-b border-rule p-5 sm:grid-cols-[1fr_auto_1fr] sm:items-center sm:gap-4 sm:p-6">
        <div>
          <p className="eyebrow mb-1.5">
            <span className="mr-1.5 inline-block rounded-[3px] bg-ink px-1.5 py-px font-mono text-[10px] text-paper">
              A
            </span>
            Where you are
          </p>
          <p className="tnum text-3xl leading-none sm:text-4xl">
            {formatMinor(map.summary.earned_total_minor, map.currency)}
          </p>
          <p className="mt-1.5 text-xs text-ink-faint">
            earned so far · {map.summary.earned_count} recorded
          </p>
        </div>

        {/* Two ways to close the distance, drawn as two arrows rather than
            described in a paragraph. The upper one is the product's main
            promise; the lower one is what is available on a week when no new
            opportunity appears. Neither carries a figure here - the earn side
            is counted below, and the keep side deliberately has no total. */}
        <div aria-hidden="true" className="hidden text-rule-strong sm:block">
          <div className="flex flex-col gap-1.5 text-[11px] leading-none">
            <span className="flex items-center gap-1.5">
              <span className="text-lg">↗</span>
              <span className="text-ink-faint">earn</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-lg">↘</span>
              <span className="text-ink-faint">
                {leakCount === null ? "keep" : `keep · ${leakCount} to check`}
              </span>
            </span>
          </div>
        </div>

        <div className="sm:text-right">
          <p className="eyebrow mb-1.5 sm:justify-end">
            <span className="mr-1.5 inline-block rounded-[3px] bg-cobalt px-1.5 py-px font-mono text-[10px] text-paper">
              B
            </span>
            Where you want to be
          </p>
          <p className="tnum text-3xl leading-none text-cobalt sm:text-4xl">
            {goal === null ? "Not set" : `${formatMinor(goal, map.currency)}`}
          </p>
          <p className="mt-1.5 text-xs text-ink-faint">
            {goal === null ? (
              <>
                <Link
                  href="/profile"
                  className="text-cobalt underline underline-offset-4"
                >
                  Set a monthly goal
                </Link>{" "}
                to see the distance
              </>
            ) : (
              "per month, additional income"
            )}
          </p>
        </div>
      </div>

      {/* ------------------------------------------------------- the pipeline */}
      <div className="p-5 sm:p-6">
        <ol className="grid grid-cols-5 gap-1 sm:gap-2">
          {stages.map((stage, index) => {
            const filled = stage.count > 0;
            const reached = index <= lastCommittedIndex;
            const isOpen = open === stage.id;
            return (
              <li key={stage.id} className="relative">
                {/* The rail segment leading into this node. Drawn behind the
                    node so the node always sits on top of the join. */}
                {index > 0 ? (
                  <span
                    aria-hidden="true"
                    className={
                      "absolute top-[11px] right-1/2 left-0 h-px " +
                      (reached ? "bg-rule-strong" : "bg-rule")
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

        {/* --------------------------------------------- the selected stage */}
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

      {/* ------------------------------------------------------- the two rails */}
      <div className="border-t border-rule bg-paper-sunk p-5 sm:p-6">
        <div className="mb-1.5 flex items-baseline justify-between text-sm">
          <span className="text-ink-muted">Distance from A to B</span>
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
        {/* The one sentence that keeps this graphic honest. It lives in
            `copy` and is rendered exactly once on the page - the dashboard
            card used to carry its own progress bar and explainer, and two
            copies of a promise is one copy too many. */}
        <p className="mt-2 text-xs text-ink-faint">
          {copy.money.progressExplainer}
        </p>

        {/* The hypothetical. Separate track, dashed, muted, and captioned - so
            that it can be read as ambition without being mistaken for money. */}
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
              Recurring potential of{" "}
              {formatMinor(potentialMonthly, map.currency)}/month across{" "}
              {map.summary.recurring_potential_count} opportunit
              {map.summary.recurring_potential_count === 1 ? "y" : "ies"} — none
              of it agreed, none of it paid.
            </p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
