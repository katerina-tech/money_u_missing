"use client";

/**
 * The tracking board.
 *
 * Grouped by state rather than listed flat, because the useful question is
 * "what needs me next?" and the answer is always in one column. The money state
 * each status implies is shown beside it, so the difference between an applied
 * application and a won one is visible as money, not only as a label.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState, LinkButton, Notice, Page, PageHeader, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatMinor, titleCase } from "@/lib/format";
import type { Application, ApplicationStatus } from "@/lib/types";

const COLUMNS: { status: ApplicationStatus[]; title: string; note: string }[] = [
  { status: ["SAVED", "PREPARING"], title: "Preparing", note: "Potential" },
  { status: ["APPLIED", "INTERVIEW"], title: "Applied", note: "Applied" },
  { status: ["OFFERED"], title: "Offered", note: "Offered" },
  { status: ["WON"], title: "Won", note: "Secured" },
  { status: ["LOST", "ARCHIVED"], title: "Closed", note: "Potential" },
];

export default function ActionsPage() {
  const [applications, setApplications] = useState<Application[] | null>(null);
  const [income, setIncome] = useState<{ amount_minor: number; currency: string }[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .applications()
      .then(setApplications)
      .catch((caught) => {
        setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
        setApplications([]);
      });
    api.income().then(setIncome).catch(() => undefined);
  }, []);

  const earned = income.reduce((total, row) => total + row.amount_minor, 0);

  return (
    <Page>
      <PageHeader
        eyebrow="Earn"
        title="Actions"
        lead="Everything you are pursuing, and where it has reached. Money only becomes secured when you record what an opportunity actually paid."
      />

      {error ? (
        <div className="mb-6">
          <Notice tone="warning">{error}</Notice>
        </div>
      ) : null}

      {applications === null ? (
        <Skeleton lines={5} />
      ) : applications.length === 0 ? (
        <EmptyState
          title="Nothing tracked yet"
          body="Save an opportunity and it appears here with a requirements checklist, the documents you will need, and the questions worth asking before you apply."
          action={<LinkButton href="/opportunities">Browse opportunities</LinkButton>}
        />
      ) : (
        <>
          <div className="mb-8 grid gap-4 sm:grid-cols-3">
            <div className="rounded-[--radius-card] border border-rule bg-paper-raised p-4">
              <p className="eyebrow mb-1">Tracked</p>
              <p className="tnum text-2xl font-semibold">{applications.length}</p>
            </div>
            <div className="rounded-[--radius-card] border border-rule bg-paper-raised p-4">
              <p className="eyebrow mb-1">Applied</p>
              <p className="tnum text-2xl font-semibold">
                {applications.filter((a) => a.applied_at !== null).length}
              </p>
            </div>
            <div className="rounded-[--radius-card] border border-rule bg-paper-raised p-4">
              <p className="eyebrow mb-1">Recorded income</p>
              <p className="tnum text-2xl font-semibold">{formatMinor(earned)}</p>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-5">
            {COLUMNS.map((column) => {
              const rows = applications.filter((application) =>
                column.status.includes(application.status),
              );
              return (
                <section key={column.title}>
                  <div className="mb-3 flex items-baseline justify-between border-b border-rule pb-2">
                    <h2 className="text-sm font-semibold">{column.title}</h2>
                    <span className="tnum text-xs text-ink-faint">{rows.length}</span>
                  </div>
                  {rows.length === 0 ? (
                    <p className="text-xs text-ink-faint">Nothing here.</p>
                  ) : (
                    <ul className="space-y-2">
                      {rows.map((application) => (
                        <li key={application.id}>
                          <Link
                            href={`/actions/${application.id}`}
                            className="block rounded-[4px] border border-rule bg-paper-raised p-3 transition-colors hover:border-rule-strong"
                          >
                            <p className="text-sm font-medium leading-snug">
                              {application.opportunity_title}
                            </p>
                            {application.organization ? (
                              <p className="mt-0.5 truncate text-xs text-ink-faint">
                                {application.organization}
                              </p>
                            ) : null}
                            <p className="mt-2 text-[11px] uppercase tracking-wide text-ink-faint">
                              {titleCase(application.money_state)}
                            </p>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        </>
      )}
    </Page>
  );
}
