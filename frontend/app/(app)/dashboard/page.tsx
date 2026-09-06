"use client";

/**
 * The Money Map. The product's home screen and its central claim.
 *
 * Structure, top to bottom: greeting, the money figures (separated by state),
 * the single Best Next Move, new opportunities, income paths, this week, recent
 * progress. The order is the order of usefulness on a Tuesday morning.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { OpportunityCard } from "@/components/OpportunityCard";
import {
  Button,
  Card,
  EmptyState,
  LinkButton,
  Notice,
  Page,
  ProgressBar,
  Section,
  Skeleton,
  Spinner,
  Stat,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatMinor } from "@/lib/format";
import type { MoneyMap } from "@/lib/types";

import { DismissDialog } from "../_components/DismissDialog";
import { FeedbackPrompt } from "../_components/FeedbackPrompt";

export default function DashboardPage() {
  const [map, setMap] = useState<MoneyMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissing, setDismissing] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setMap(await api.moneyMap());
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function refresh() {
    setRefreshing(true);
    setError(null);
    try {
      setMap(await api.refreshMoneyMap());
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        setError("Confirm your profile before we search. Nothing extracted is used until you have checked it.");
      } else {
        setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
      }
    } finally {
      setRefreshing(false);
    }
  }

  if (loading) {
    return (
      <Page>
        <Skeleton lines={6} />
      </Page>
    );
  }

  if (!map) {
    return (
      <Page>
        <Notice tone="danger" title="We could not load your Money Map">
          {error ?? copy.errors.generic}
        </Notice>
      </Page>
    );
  }

  const summary = map.summary;
  const hasOpportunities = map.opportunities.length > 0;

  return (
    <Page>
      <header className="mb-8">
        <p className="eyebrow mb-2">{map.greeting}</p>
        <h1 className="text-3xl sm:text-4xl">Your Money Map</h1>
      </header>

      {error ? (
        <div className="mb-6">
          <Notice tone="warning">{error}</Notice>
        </div>
      ) : null}

      {/* ------------------------------------------------------- the money */}
      <Card className="mb-8">
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label={copy.money.goal}
            value={
              map.goal_monthly_minor === null
                ? "Not set"
                : `${formatMinor(map.goal_monthly_minor, map.currency)}/month`
            }
            detail={map.goal_monthly_minor === null ? "Set one in your profile" : "Additional income"}
          />
          <Stat
            label={copy.money.secured}
            value={formatMinor(summary.secured_monthly_minor + summary.secured_one_time_minor, map.currency)}
            detail={`${summary.secured_count} confirmed`}
          />
          <Stat
            label={copy.money.earned}
            value={formatMinor(summary.earned_total_minor, map.currency)}
            detail={`${summary.earned_count} recorded`}
          />
          <Stat
            label={copy.money.potential}
            // The count of opportunities, not the sum of the money buckets:
            // those exclude the ones we cannot convert, so summing them
            // disagreed with the list directly below.
            value={`${map.opportunities.length}`}
            detail="opportunities found"
            tone="muted"
          />
        </div>

        <div className="mt-6 border-t border-rule pt-5">
          <ProgressBar
            ratio={map.goal_progress_ratio}
            label="Progress towards your monthly goal"
            explainer={copy.money.progressExplainer}
          />
        </div>

        {/* The potential figures, kept visually distinct from the committed
            ones above, and never summed with them. */}
        <div className="mt-6 grid gap-4 border-t border-rule pt-5 sm:grid-cols-3">
          <div>
            <p className="eyebrow mb-0.5">{copy.money.recurringPotential}</p>
            <p className="tnum text-lg">
              {summary.recurring_potential_count === 0
                ? "—"
                : `${formatMinor(summary.recurring_potential_monthly_minor, map.currency)}/month`}
            </p>
            <p className="text-xs text-ink-faint">
              across {summary.recurring_potential_count} opportunit
              {summary.recurring_potential_count === 1 ? "y" : "ies"}
            </p>
          </div>
          <div>
            <p className="eyebrow mb-0.5">{copy.money.oneTimePotential}</p>
            <p className="tnum text-lg">
              {summary.one_time_potential_count === 0
                ? "—"
                : formatMinor(summary.one_time_potential_minor, map.currency)}
            </p>
            <p className="text-xs text-ink-faint">
              across {summary.one_time_potential_count} opportunit
              {summary.one_time_potential_count === 1 ? "y" : "ies"}
            </p>
          </div>
          <div>
            <p className="eyebrow mb-0.5">{copy.money.unknownValue}</p>
            <p className="tnum text-lg text-ink-muted">
              {summary.unknown_value_count + summary.unconvertible_count}
            </p>
            <p className="text-xs text-ink-faint">excluded from the totals</p>
          </div>
        </div>

        {summary.exclusions.length > 0 ? (
          <ul className="mt-4 space-y-1 border-t border-rule pt-4">
            {summary.exclusions.map((line) => (
              <li key={line} className="text-xs text-ink-faint">
                {line}
              </li>
            ))}
          </ul>
        ) : null}
      </Card>

      {/* ------------------------------------------------ best next move */}
      <Section>
        {map.best_next_move ? (
          <Card className="border-cobalt/30 bg-cobalt-wash">
            <p className="eyebrow mb-3 text-cobalt">Best next move</p>
            <h2 className="text-2xl">{map.best_next_move.title}</h2>
            {map.best_next_move.organization ? (
              <p className="mt-1 text-sm text-ink-muted">{map.best_next_move.organization}</p>
            ) : null}
            {map.best_next_move.reasons.length > 0 ? (
              <>
                <p className="eyebrow mt-5 mb-2">Why now</p>
                <ul className="space-y-1.5">
                  {map.best_next_move.reasons.map((reason) => (
                    <li key={reason} className="flex gap-2 text-sm">
                      <span aria-hidden="true" className="text-cobalt">
                        →
                      </span>
                      <span>{reason}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            {map.best_next_move.caveat ? (
              <p className="mt-4 text-xs text-ink-faint">{map.best_next_move.caveat}</p>
            ) : null}
            <div className="mt-6">
              <LinkButton href={`/opportunities/${map.best_next_move.opportunity_id}`}>
                View opportunity
              </LinkButton>
            </div>
          </Card>
        ) : (
          <EmptyState
            title="No recommendation yet"
            body={
              hasOpportunities
                ? "Nothing currently clears the bar for a single confident recommendation. The full list is below."
                : "Build your Money Map to search for opportunities that match your profile."
            }
            action={
              <Button onClick={refresh} disabled={refreshing}>
                {refreshing ? "Searching…" : "Build my Money Map"}
              </Button>
            }
          />
        )}
      </Section>

      {/* -------------------------------------------------- opportunities */}
      <Section
        title="New money you may be missing"
        description={`${map.opportunities.length} opportunit${map.opportunities.length === 1 ? "y" : "ies"} matched to your profile.`}
        actions={
          <Button variant="secondary" onClick={refresh} disabled={refreshing}>
            {refreshing ? "Searching…" : "Search again"}
          </Button>
        }
      >
        {refreshing ? (
          <div className="mb-4">
            <Spinner label="Querying sources, extracting and scoring…" />
          </div>
        ) : null}

        {map.diagnostics.notices.length > 0 ? (
          <div className="mb-4 space-y-2">
            {map.diagnostics.notices.map((notice) => (
              <Notice key={notice} tone="info">
                {notice}
              </Notice>
            ))}
          </div>
        ) : null}

        {hasOpportunities ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {map.opportunities.slice(0, 8).map((opportunity) => (
              <OpportunityCard
                key={opportunity.id}
                opportunity={opportunity}
                onDismiss={setDismissing}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            title="Nothing found yet"
            body="Run a search to see what matches your profile."
            action={
              <Button onClick={refresh} disabled={refreshing}>
                Search now
              </Button>
            }
          />
        )}

        {map.opportunities.length > 8 ? (
          <p className="mt-4 text-sm">
            <Link href="/opportunities" className="text-cobalt underline underline-offset-4">
              See all {map.opportunities.length} opportunities
            </Link>
          </p>
        ) : null}

        {/* What the run actually did. Shown, not buried in a log. */}
        <details className="mt-6 rounded-[--radius-card] border border-rule bg-paper-sunk p-4">
          <summary className="cursor-pointer text-sm font-medium">
            How this search ran
          </summary>
          <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-3">
            {[
              ["Considered", map.diagnostics.considered],
              ["Returned", map.diagnostics.returned],
              ["Duplicates merged", map.diagnostics.duplicates_removed],
              ["Expired or stale", map.diagnostics.stale_removed],
              ["Blocked as unsafe", map.diagnostics.blocked_unsafe],
              ["Blocked as prompt injection", map.diagnostics.blocked_injection],
              ["Sources queried", map.diagnostics.sources_queried],
              ["Live web search", map.diagnostics.live_search_used ? "used" : "not configured"],
            ].map(([term, value]) => (
              <div key={String(term)}>
                <dt className="text-ink-faint">{term}</dt>
                <dd className="tnum font-medium">{value}</dd>
              </div>
            ))}
          </dl>
          {map.diagnostics.plan_rationale ? (
            <p className="mt-3 border-t border-rule pt-3 text-xs text-ink-muted">
              {map.diagnostics.plan_rationale}
            </p>
          ) : null}
          {map.diagnostics.queries.length > 0 ? (
            <ul className="mt-2 space-y-1">
              {map.diagnostics.queries.map((query) => (
                <li key={query} className="font-mono text-[11px] text-ink-faint">
                  {query}
                </li>
              ))}
            </ul>
          ) : null}
        </details>
      </Section>

      {/* --------------------------------------------------- income paths */}
      {map.income_paths.length > 0 ? (
        <Section title="Income paths" description="Where the opportunities cluster.">
          <ul className="grid gap-px overflow-hidden rounded-[--radius-card] border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-3">
            {map.income_paths.map((path) => (
              <li key={path.category} className="bg-paper-raised p-4">
                <p className="text-sm font-medium">{path.label}</p>
                <p className="mt-1 text-xs text-ink-faint">
                  {path.opportunity_count} opportunit{path.opportunity_count === 1 ? "y" : "ies"}
                  {path.best_match_score ? ` · best match ${path.best_match_score}%` : ""}
                </p>
                {path.indicative_monthly_minor !== null ? (
                  <p className="tnum mt-2 text-sm">
                    up to {formatMinor(path.indicative_monthly_minor, map.currency)}/month
                  </p>
                ) : (
                  <p className="mt-2 text-xs italic text-ink-faint">
                    No monthly-comparable figure
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {/* ---------------------------------------- this week / progress */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="This week">
          {map.this_week.length > 0 ? (
            <ul className="space-y-2">
              {map.this_week.map((line) => (
                <li key={line} className="rounded-[4px] border border-rule bg-paper-raised p-3 text-sm">
                  {line}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-muted">Nothing closes in the next seven days.</p>
          )}
        </Section>

        <Section title="Recent progress">
          {map.recent_progress.length > 0 ? (
            <ul className="space-y-2">
              {map.recent_progress.map((line) => (
                <li key={line} className="rounded-[4px] border border-rule bg-paper-raised p-3 text-sm">
                  {line}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-muted">
              Save an opportunity to start tracking it from potential through to earned.
            </p>
          )}
        </Section>
      </div>

      {hasOpportunities ? <FeedbackPrompt question="would_not_have_found" /> : null}

      {dismissing ? (
        <DismissDialog
          opportunityId={dismissing}
          onClose={() => setDismissing(null)}
          onDismissed={() => {
            setDismissing(null);
            void load();
          }}
        />
      ) : null}
    </Page>
  );
}
