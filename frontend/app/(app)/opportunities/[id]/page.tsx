"use client";

/**
 * The opportunity detail page.
 *
 * The spine of the product's credibility. Order is deliberate: what it is, how
 * well it fits *and why*, what we know, what we do not know, what it might mean
 * in Germany, and only then the actions. Someone who reads top to bottom has
 * been told the weaknesses before they are asked to act.
 *
 * "What we don't know" is not collapsed, not greyed out, and not below the
 * fold on desktop.
 */

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  BandBadge,
  Button,
  Card,
  DefinitionList,
  KnownList,
  LinkButton,
  MoneyFigure,
  Notice,
  Page,
  ScoreDial,
  Skeleton,
  TrustBadge,
  UnknownList,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatAge, formatDeadline, formatHours, titleCase } from "@/lib/format";
import type { OpportunityDetail } from "@/lib/types";

import { DismissDialog } from "../../_components/DismissDialog";
import { FeedbackPrompt } from "../../_components/FeedbackPrompt";

export default function OpportunityPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [opportunity, setOpportunity] = useState<OpportunityDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [dismissing, setDismissing] = useState(false);

  const load = useCallback(async () => {
    try {
      setOpportunity(await api.opportunity(id));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <Page>
        <Notice tone="danger" title="We could not load this opportunity">
          {error}
        </Notice>
      </Page>
    );
  }

  if (!opportunity) {
    return (
      <Page>
        <Skeleton lines={8} />
      </Page>
    );
  }

  const match = opportunity.match;
  const deadline = formatDeadline(opportunity.deadline);

  async function save() {
    setSaving(true);
    try {
      const application = await api.save(id);
      router.push(`/actions/${application.id}`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
      setSaving(false);
    }
  }

  return (
    <Page>
      <Link
        href="/opportunities"
        className="mb-6 inline-block text-sm text-ink-muted hover:text-ink"
      >
        ← All opportunities
      </Link>

      {/* --------------------------------------------------------- header */}
      <header className="mb-8">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <TrustBadge trust={opportunity.trust} />
          <span className="text-xs uppercase tracking-wide text-ink-faint">
            {titleCase(opportunity.category)}
          </span>
          {opportunity.actionability ? (
            <BandBadge band={opportunity.actionability.band} />
          ) : null}
        </div>

        <h1 className="text-3xl sm:text-4xl">{opportunity.title}</h1>
        <p className="mt-2 text-ink-muted">
          {opportunity.organization ?? "Organisation not stated"}
          {opportunity.city ? ` · ${opportunity.city}` : ""}
          {opportunity.remote_type !== "UNKNOWN"
            ? ` · ${titleCase(opportunity.remote_type)}`
            : ""}
        </p>

        {opportunity.is_demo ? (
          <div className="mt-4">
            <Notice tone="demo" title="This is a demo opportunity">
              A fictional listing, shown to illustrate how the product works. The organisation
              does not exist and this is not an offer.
            </Notice>
          </div>
        ) : null}

        {opportunity.safety_verdict === "FLAGGED" ? (
          <div className="mt-4">
            <Notice tone="warning" title="Check this one carefully">
              <ul className="list-disc space-y-1 pl-4">
                {opportunity.safety_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              We are showing it rather than hiding it, because a flag is not proof of anything —
              but treat requests for upfront payment or identity documents with suspicion.
            </Notice>
          </div>
        ) : null}
      </header>

      <div className="grid gap-8 lg:grid-cols-[1.35fr_1fr] lg:items-start">
        <div>
          {/* -------------------------------------------- why it matches */}
          {match ? (
            <Card className="mb-6">
              <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
                <h2 className="text-lg font-semibold">{copy.opportunity.whyItMatches}</h2>
                <ScoreDial score={match.total_score} eligible={match.eligible} />
              </div>

              {!match.eligible ? (
                <div className="mb-4">
                  <Notice tone="danger" title="You do not meet a stated requirement">
                    <ul className="list-disc space-y-1 pl-4">
                      {match.hard_failures.map((failure) => (
                        <li key={failure.requirement}>{failure.explanation}</li>
                      ))}
                    </ul>
                  </Notice>
                </div>
              ) : null}

              <ul className="space-y-2.5">
                {match.components
                  .filter((component) => component.weight > 0)
                  .sort((a, b) => b.score * b.weight - a.score * a.weight)
                  .map((component) => (
                    <li key={component.name} className="flex gap-2.5 text-sm">
                      <span
                        aria-hidden="true"
                        className={
                          component.was_unknown
                            ? "text-ink-faint"
                            : component.score >= 0.7
                              ? "text-verified"
                              : "text-unverified"
                        }
                      >
                        {component.was_unknown ? "?" : component.score >= 0.7 ? "✓" : "–"}
                      </span>
                      <span>
                        <span className="font-medium">{titleCase(component.name)}: </span>
                        <span className="text-ink-muted">{component.detail}</span>
                      </span>
                    </li>
                  ))}
              </ul>

              {match.explanation ? (
                <div className="mt-5 border-t border-rule pt-4">
                  <p className="text-sm text-ink-muted">{match.explanation}</p>
                  <p className="mt-2 text-xs text-ink-faint">{copy.opportunity.aiWritten}</p>
                </div>
              ) : null}

              <p className="mt-4 border-t border-rule pt-3 text-xs text-ink-faint">
                {copy.opportunity.scoreExplainer} Weights version {match.weights_version}.
              </p>
            </Card>
          ) : null}

          {/* --------------------------------- know / don't know, equal weight */}
          <div className="mb-6 grid gap-4 sm:grid-cols-2">
            <Card>
              <KnownList items={opportunity.what_we_know} title={copy.opportunity.whatWeKnow} />
              {opportunity.what_we_know.length === 0 ? (
                <p className="text-sm text-ink-faint">
                  The source publishes very little about this one.
                </p>
              ) : null}
            </Card>
            <Card className="border-unverified/25 bg-unverified-wash/40">
              <UnknownList
                items={opportunity.what_we_dont_know}
                title={copy.opportunity.whatWeDontKnow}
              />
              {opportunity.what_we_dont_know.length === 0 ? (
                <p className="text-sm text-ink-muted">
                  Everything we would want to know is published.
                </p>
              ) : null}
            </Card>
          </div>

          {/* ------------------------------------------------ description */}
          {opportunity.summary || opportunity.description ? (
            <Card className="mb-6">
              <h2 className="mb-3 text-lg font-semibold">What the source says</h2>
              {opportunity.summary ? (
                <p className="mb-3 text-sm text-ink-muted">{opportunity.summary}</p>
              ) : null}
              {opportunity.description ? (
                <p className="whitespace-pre-line text-sm leading-relaxed text-ink-muted">
                  {opportunity.description.slice(0, 2400)}
                </p>
              ) : null}
            </Card>
          ) : null}

          {/* ------------------------------------------------- eligibility */}
          {opportunity.eligibility_structured.length > 0 || opportunity.eligibility_text ? (
            <Card className="mb-6">
              <h2 className="mb-3 text-lg font-semibold">Eligibility</h2>
              {opportunity.eligibility_structured.length > 0 ? (
                <ul className="mb-3 space-y-2">
                  {opportunity.eligibility_structured.map((requirement) => (
                    <li key={requirement.label} className="flex flex-wrap items-baseline gap-2 text-sm">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase ${
                          requirement.strength === "HARD"
                            ? "border-danger/30 bg-danger-wash text-danger"
                            : requirement.strength === "SOFT"
                              ? "border-rule-strong text-ink-muted"
                              : "border-unknown/25 bg-unknown-wash text-unknown"
                        }`}
                      >
                        {requirement.strength === "UNKNOWN" ? "unclear" : requirement.strength}
                      </span>
                      <span>{requirement.label}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {opportunity.eligibility_text ? (
                <p className="whitespace-pre-line text-sm text-ink-muted">
                  {opportunity.eligibility_text}
                </p>
              ) : null}
            </Card>
          ) : null}

          {/* --------------------------------------------- germany check */}
          {opportunity.germany_check ? (
            <Card className="mb-6">
              <h2 className="mb-1 text-lg font-semibold">
                What this may mean in Germany
              </h2>
              <p className="mb-4 text-xs text-ink-faint">
                {opportunity.germany_check.disclaimer}
              </p>

              {opportunity.germany_check.needs_verification ? (
                <div className="mb-4">
                  <Notice tone="warning">
                    Some of the underlying rules have not been re-checked against their source
                    recently. Confirm current figures at the official source before relying on
                    them.
                  </Notice>
                </div>
              ) : null}

              <ul className="mb-5 space-y-2">
                {opportunity.germany_check.considerations.map((line) => (
                  <li key={line} className="flex gap-2 text-sm">
                    <span aria-hidden="true" className="text-ink-faint">
                      •
                    </span>
                    <span className="text-ink-muted">{line}</span>
                  </li>
                ))}
              </ul>

              {opportunity.germany_check.employment_notes.length > 0 ? (
                <div className="mb-5 rounded-[4px] border border-rule bg-paper-sunk p-4">
                  <p className="eyebrow mb-2">Because you are employed</p>
                  {opportunity.germany_check.employment_notes.map((note) => (
                    <p key={note} className="text-sm text-ink-muted">
                      {note}
                    </p>
                  ))}
                </div>
              ) : null}

              {opportunity.germany_check.benefit_notes.length > 0 ? (
                <div className="mb-5 rounded-[4px] border border-unverified/30 bg-unverified-wash p-4">
                  <p className="eyebrow mb-2">Because you receive benefits</p>
                  <ul className="space-y-1.5">
                    {opportunity.germany_check.benefit_notes.map((note) => (
                      <li key={note} className="text-sm">
                        {note}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <p className="eyebrow mb-2">Questions to check</p>
              <ul className="mb-5 space-y-1.5">
                {opportunity.germany_check.questions_to_check.map((question) => (
                  <li key={question} className="flex gap-2 text-sm">
                    <span aria-hidden="true" className="text-cobalt">
                      ?
                    </span>
                    <span>{question}</span>
                  </li>
                ))}
              </ul>

              {opportunity.germany_check.official_sources.length > 0 ? (
                <>
                  <p className="eyebrow mb-2">Official sources</p>
                  <ul className="space-y-2">
                    {opportunity.germany_check.official_sources.map((source) => (
                      <li key={source.title} className="text-sm">
                        {source.source_url ? (
                          <a
                            href={source.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-cobalt underline underline-offset-4"
                          >
                            {source.title}
                          </a>
                        ) : (
                          <span>{source.title}</span>
                        )}
                        <span className="text-ink-faint"> · {source.source_name}</span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
            </Card>
          ) : null}
        </div>

        {/* -------------------------------------------------------- sidebar */}
        <aside className="lg:sticky lg:top-24">
          <Card className="mb-4">
            <DefinitionList
              items={[
                {
                  term: "Compensation",
                  value: <MoneyFigure money={opportunity.compensation} size="lg" />,
                },
                {
                  term: "Time commitment",
                  value:
                    opportunity.estimated_hours_min === null &&
                    opportunity.estimated_hours_max === null ? (
                      <span className="italic text-ink-faint">Not published</span>
                    ) : (
                      formatHours(
                        opportunity.estimated_hours_min,
                        opportunity.estimated_hours_max,
                      )
                    ),
                },
                {
                  term: "Deadline",
                  value: (
                    <span className={deadline.urgent ? "font-medium text-danger" : ""}>
                      {deadline.label}
                    </span>
                  ),
                },
                { term: "Employment type", value: titleCase(opportunity.employment_type) },
                {
                  term: "Experience",
                  value:
                    opportunity.experience_min_years === null ? (
                      <span className="italic text-ink-faint">Not stated</span>
                    ) : (
                      `${opportunity.experience_min_years}+ years`
                    ),
                },
                {
                  term: copy.opportunity.lastVerified,
                  value: formatAge(opportunity.last_seen_days_ago),
                },
              ]}
            />
          </Card>

          {opportunity.actionability ? (
            <Card className="mb-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold">Is this worth doing now?</h2>
                <BandBadge band={opportunity.actionability.band} />
              </div>
              <p className="text-sm text-ink-muted">
                {opportunity.actionability.headline_reason}
              </p>
              {opportunity.actionability.blockers.length > 0 ? (
                <ul className="mt-3 space-y-1">
                  {opportunity.actionability.blockers.map((blocker) => (
                    <li key={blocker} className="text-sm text-danger">
                      {blocker}
                    </li>
                  ))}
                </ul>
              ) : null}
              <details className="mt-3 border-t border-rule pt-3">
                <summary className="cursor-pointer text-xs text-ink-faint">
                  How this is calculated
                </summary>
                <ul className="mt-2 space-y-1.5">
                  {opportunity.actionability.factors.map((factor) => (
                    <li key={factor.name} className="text-xs text-ink-muted">
                      <span className="font-medium">{titleCase(factor.name)}: </span>
                      {factor.detail}
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-ink-faint">
                  This is a priority band, not a forecast of income. It answers &ldquo;is this
                  worth my time this week?&rdquo;, which is a different question from whether
                  it fits you.
                </p>
              </details>
            </Card>
          ) : null}

          <Card className="mb-4">
            <p className="eyebrow mb-2">{copy.opportunity.nextAction}</p>
            <div className="flex flex-col gap-2">
              {opportunity.application_status ? (
                <LinkButton href="/actions" variant="secondary">
                  Tracked as {titleCase(opportunity.application_status)}
                </LinkButton>
              ) : (
                <Button onClick={save} disabled={saving} full>
                  {saving ? "Saving…" : copy.opportunity.prepare}
                </Button>
              )}
              {opportunity.source_url ? (
                <LinkButton href={opportunity.source_url} variant="secondary" external>
                  {copy.opportunity.openSource}
                </LinkButton>
              ) : (
                <p className="text-xs text-ink-faint">
                  This source did not give us a link we can open.
                </p>
              )}
              <Button variant="ghost" onClick={() => setDismissing(true)}>
                {copy.opportunity.dismiss}
              </Button>
            </div>
            <p className="mt-3 border-t border-rule pt-3 text-xs text-ink-faint">
              We never apply on your behalf. Everything is prepared for you to send yourself.
            </p>
          </Card>

          <Card>
            <p className="eyebrow mb-2">{copy.opportunity.source}</p>
            <p className="text-sm">{opportunity.source_name}</p>
            {opportunity.corroborating_sources.length > 0 ? (
              <>
                <p className="eyebrow mt-3 mb-1">Also seen via</p>
                <ul className="space-y-1">
                  {opportunity.corroborating_sources.map((source) => (
                    <li key={source.name} className="text-xs text-ink-muted">
                      {source.name}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </Card>
        </aside>
      </div>

      <FeedbackPrompt question="would_pursue" opportunityId={id} />

      {dismissing ? (
        <DismissDialog
          opportunityId={id}
          onClose={() => setDismissing(false)}
          onDismissed={() => router.push("/opportunities")}
        />
      ) : null}
    </Page>
  );
}
