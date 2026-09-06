"use client";

/**
 * The action workspace.
 *
 * Checklist, documents, questions to verify, notes, drafts and the status
 * machine. Recording a win asks for the *actual* figure - the form does not
 * pre-fill the advertised amount, because the difference between the two is
 * the most valuable number this product collects.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  Button,
  Card,
  Field,
  LinkButton,
  Notice,
  Page,
  Section,
  Select,
  Skeleton,
  TextArea,
  TextInput,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { parseMoneyInput, titleCase } from "@/lib/format";
import type { Application, ApplicationStatus } from "@/lib/types";

const NEXT_STATUSES: Record<string, ApplicationStatus[]> = {
  SAVED: ["PREPARING", "APPLIED", "ARCHIVED"],
  PREPARING: ["APPLIED", "SAVED", "ARCHIVED"],
  APPLIED: ["INTERVIEW", "OFFERED", "WON", "LOST", "ARCHIVED"],
  INTERVIEW: ["OFFERED", "WON", "LOST", "ARCHIVED"],
  OFFERED: ["WON", "LOST", "ARCHIVED"],
  WON: ["ARCHIVED"],
  LOST: ["ARCHIVED"],
  ARCHIVED: ["SAVED"],
};

const DRAFT_KINDS = [
  { value: "bio", label: "Short professional bio" },
  { value: "cover_letter", label: "Cover letter" },
  { value: "pitch", label: "Pitch" },
  { value: "short_answer", label: "Short application answer" },
  { value: "outreach", label: "Outreach message" },
];

export default function WorkspacePage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [application, setApplication] = useState<Application | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [showOutcome, setShowOutcome] = useState(false);
  const [draftKind, setDraftKind] = useState("bio");
  const [draftError, setDraftError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await api.application(id);
      setApplication(result);
      setNotes(result.notes ?? "");
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
        <Notice tone="danger">{error}</Notice>
      </Page>
    );
  }
  if (!application) {
    return (
      <Page>
        <Skeleton lines={6} />
      </Page>
    );
  }

  async function toggle(index: number) {
    if (!application) return;
    const checklist = application.checklist.map((item, position) =>
      position === index ? { ...item, done: !item.done } : item,
    );
    setApplication({ ...application, checklist });
    await api.updateWorkspace(id, { checklist }).catch(() => undefined);
  }

  async function saveNotes() {
    setBusy(true);
    await api.updateWorkspace(id, { notes }).catch(() => undefined);
    setBusy(false);
  }

  async function move(status: ApplicationStatus) {
    if (status === "WON") {
      setShowOutcome(true);
      return;
    }
    setBusy(true);
    try {
      setApplication(await api.transition(id, status));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  async function writeDraft() {
    setDraftError(null);
    setBusy(true);
    try {
      const draft = await api.draft(id, draftKind);
      setApplication({
        ...application!,
        drafts: { ...application!.drafts, [draft.kind]: draft.text },
      });
    } catch (caught) {
      setDraftError(
        caught instanceof ApiError && caught.isDegraded
          ? caught.message
          : copy.errors.llmUnavailable,
      );
    } finally {
      setBusy(false);
    }
  }

  const done = application.checklist.filter((item) => item.done).length;

  return (
    <Page>
      <Link href="/actions" className="mb-6 inline-block text-sm text-ink-muted hover:text-ink">
        ← All actions
      </Link>

      <header className="mb-8">
        <p className="eyebrow mb-2">
          {titleCase(application.status)} · money state {titleCase(application.money_state)}
        </p>
        <h1 className="text-3xl">{application.opportunity_title}</h1>
        {application.organization ? (
          <p className="mt-1 text-ink-muted">{application.organization}</p>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          {(NEXT_STATUSES[application.status] ?? []).map((status) => (
            <Button
              key={status}
              variant={status === "WON" ? "primary" : "secondary"}
              onClick={() => move(status)}
              disabled={busy}
            >
              Mark as {titleCase(status)}
            </Button>
          ))}
          <LinkButton href={`/opportunities/${application.opportunity_id}`} variant="ghost">
            View opportunity
          </LinkButton>
        </div>
      </header>

      {showOutcome ? (
        <OutcomeForm
          onCancel={() => setShowOutcome(false)}
          onSubmit={async (outcome) => {
            setBusy(true);
            try {
              setApplication(await api.transition(id, "WON", outcome));
              setShowOutcome(false);
            } catch (caught) {
              setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
            } finally {
              setBusy(false);
            }
          }}
        />
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr] lg:items-start">
        <div>
          <Section title={`Requirements checklist (${done}/${application.checklist.length})`}>
            <Card>
              <ul className="space-y-2.5">
                {application.checklist.map((item, index) => (
                  <li key={item.label}>
                    <label className="flex cursor-pointer items-start gap-3 text-sm">
                      <input
                        type="checkbox"
                        checked={item.done}
                        onChange={() => toggle(index)}
                        className="mt-1 accent-cobalt"
                      />
                      <span className={item.done ? "text-ink-faint line-through" : ""}>
                        {item.label}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </Card>
          </Section>

          <Section title="Notes">
            <Card>
              <TextArea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="What you have done, who you spoke to, what you are waiting on."
                aria-label="Application notes"
              />
              <div className="mt-3">
                <Button variant="secondary" onClick={saveNotes} disabled={busy}>
                  {busy ? "Saving…" : "Save notes"}
                </Button>
              </div>
            </Card>
          </Section>

          <Section
            title="Drafts"
            description="Written from your profile. Review and send it yourself — this system never submits anything on your behalf."
          >
            <Card>
              <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-48 flex-1">
                  <Field label="What to draft" htmlFor="draft-kind">
                    <Select
                      id="draft-kind"
                      value={draftKind}
                      onChange={(event) => setDraftKind(event.target.value)}
                    >
                      {DRAFT_KINDS.map((kind) => (
                        <option key={kind.value} value={kind.value}>
                          {kind.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>
                <div className="mb-4">
                  <Button onClick={writeDraft} disabled={busy}>
                    {busy ? "Writing…" : "Write a draft"}
                  </Button>
                </div>
              </div>

              {draftError ? <Notice tone="warning">{draftError}</Notice> : null}

              {Object.entries(application.drafts).map(([kind, text]) => (
                <div key={kind} className="mt-4 border-t border-rule pt-4">
                  <p className="eyebrow mb-2">{titleCase(kind)}</p>
                  <p className="whitespace-pre-line rounded-[4px] bg-paper-sunk p-4 text-sm">
                    {text}
                  </p>
                  <p className="mt-2 text-xs text-ink-faint">
                    Check every claim against your own experience before sending. Anything in
                    square brackets is a gap for you to fill honestly.
                  </p>
                </div>
              ))}
            </Card>
          </Section>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-24">
          <Card>
            <p className="eyebrow mb-2">Documents needed</p>
            <ul className="space-y-1.5">
              {application.documents_needed.map((document) => (
                <li key={document} className="text-sm text-ink-muted">
                  {document}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-ink-faint">
              A starting list for this kind of opportunity, not a claim about what this
              organisation asks for. Their page is the authority.
            </p>
          </Card>

          <Card>
            <p className="eyebrow mb-2">Questions to verify</p>
            <ul className="space-y-1.5">
              {application.questions_to_verify.map((question) => (
                <li key={question} className="flex gap-2 text-sm">
                  <span aria-hidden="true" className="text-cobalt">
                    ?
                  </span>
                  <span>{question}</span>
                </li>
              ))}
            </ul>
          </Card>

          {application.status_history.length > 0 ? (
            <Card>
              <p className="eyebrow mb-2">History</p>
              <ol className="space-y-1.5">
                {application.status_history.map((entry) => (
                  <li key={entry.at} className="text-xs text-ink-muted">
                    {titleCase(entry.from)} → {titleCase(entry.to)}
                    <span className="text-ink-faint">
                      {" "}
                      · {new Date(entry.at).toLocaleDateString("en-DE")}
                    </span>
                  </li>
                ))}
              </ol>
            </Card>
          ) : null}
        </aside>
      </div>
    </Page>
  );
}

function OutcomeForm({
  onSubmit,
  onCancel,
}: {
  onSubmit: (outcome: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}) {
  const [amount, setAmount] = useState("");
  const [period, setPeriod] = useState("ONE_TIME");
  const [treatment, setTreatment] = useState("UNKNOWN");
  const [hours, setHours] = useState("");
  const [notes, setNotes] = useState("");

  const minor = parseMoneyInput(amount);

  return (
    <Card className="mb-8 border-cobalt/30 bg-cobalt-wash">
      <h2 className="text-lg font-semibold">What did it actually pay?</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Not the advertised amount — what you were actually paid or promised. The difference
        between the two is the most useful thing you can tell us, and it is what makes future
        recommendations better.
      </p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <Field label="Amount" htmlFor="outcome-amount">
          <TextInput
            id="outcome-amount"
            inputMode="decimal"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            placeholder="e.g. 850"
          />
        </Field>
        <Field label="How often" htmlFor="outcome-period">
          <Select
            id="outcome-period"
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
          >
            <option value="ONE_TIME">One-off</option>
            <option value="RECURRING">Recurring, monthly</option>
            <option value="IRREGULAR">Irregular</option>
          </Select>
        </Field>
        <Field
          label="Gross or net"
          htmlFor="outcome-treatment"
          hint="Leave as unknown if you are not sure — we will not guess."
        >
          <Select
            id="outcome-treatment"
            value={treatment}
            onChange={(event) => setTreatment(event.target.value)}
          >
            <option value="UNKNOWN">Not sure</option>
            <option value="GROSS">Gross</option>
            <option value="NET">Net</option>
          </Select>
        </Field>
        <Field
          label="Hours spent (optional)"
          htmlFor="outcome-hours"
          hint="Including unpaid preparation. This is what makes an hourly comparison honest."
        >
          <TextInput
            id="outcome-hours"
            inputMode="decimal"
            value={hours}
            onChange={(event) => setHours(event.target.value)}
          />
        </Field>
      </div>

      <Field label="Notes (optional)" htmlFor="outcome-notes">
        <TextArea
          id="outcome-notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          className="min-h-20"
        />
      </Field>

      <div className="flex gap-2">
        <Button
          disabled={minor === null}
          onClick={() =>
            onSubmit({
              amount_minor: minor ?? 0,
              currency: "EUR",
              period,
              tax_treatment: treatment,
              hours_spent: hours ? Number.parseFloat(hours) : null,
              notes: notes || null,
            })
          }
        >
          Record it
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </Card>
  );
}
