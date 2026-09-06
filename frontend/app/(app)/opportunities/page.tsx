"use client";

import { useCallback, useEffect, useState } from "react";

import { OpportunityCard } from "@/components/OpportunityCard";
import {
  Button,
  EmptyState,
  Notice,
  Page,
  PageHeader,
  Skeleton,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import type { OpportunitySummary } from "@/lib/types";

import { DismissDialog } from "../_components/DismissDialog";

type Filter = "all" | "saved" | "high";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "high", label: "70% and above" },
  { value: "saved", label: "Saved" },
];

export default function OpportunitiesPage() {
  const [items, setItems] = useState<OpportunitySummary[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [error, setError] = useState<string | null>(null);
  const [dismissing, setDismissing] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(
        await api.opportunities({
          savedOnly: filter === "saved",
          minScore: filter === "high" ? 70 : undefined,
        }),
      );
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
      setItems([]);
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function refresh() {
    setRefreshing(true);
    try {
      await api.refreshMoneyMap();
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Earn"
        title="Opportunities"
        lead="Everything we have found for your profile, ranked by fit. Opportunities you do not qualify for are shown last with the reason, rather than hidden."
        actions={
          <Button variant="secondary" onClick={refresh} disabled={refreshing}>
            {refreshing ? "Searching…" : "Search again"}
          </Button>
        }
      />

      <div role="group" aria-label="Filter" className="mb-6 flex flex-wrap gap-2">
        {FILTERS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setFilter(option.value)}
            aria-pressed={filter === option.value}
            className={`rounded-full border px-3.5 py-1.5 text-sm transition-colors ${
              filter === option.value
                ? "border-ink bg-ink text-paper"
                : "border-rule-strong hover:border-ink-faint"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {error ? (
        <div className="mb-6">
          <Notice tone="warning">{error}</Notice>
        </div>
      ) : null}

      {items === null ? (
        <Skeleton lines={6} />
      ) : items.length === 0 ? (
        <EmptyState
          title={filter === "saved" ? "Nothing saved yet" : "No opportunities yet"}
          body={
            filter === "saved"
              ? "Save an opportunity to open its action workspace and start tracking it."
              : "Run a search to see what matches your profile."
          }
          action={
            filter === "all" ? (
              <Button onClick={refresh} disabled={refreshing}>
                Search now
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {items.map((opportunity) => (
            <OpportunityCard
              key={opportunity.id}
              opportunity={opportunity}
              onDismiss={setDismissing}
            />
          ))}
        </div>
      )}

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
