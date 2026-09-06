"use client";

/**
 * FAMILY: child savings.
 *
 * The account-ownership card is the point of this page. It presents parent-held
 * and child-held savings side by side with no recommendation, because which one
 * suits a family depends on things this product cannot see - and a default
 * would be read as advice.
 */

import { useEffect, useState } from "react";

import {
  Button,
  Card,
  EmptyState,
  Field,
  Notice,
  Page,
  PageHeader,
  Section,
  Skeleton,
  TextInput,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatMinor, parseMoneyInput } from "@/lib/format";
import type { ChildGoal, OwnershipCard, Projection } from "@/lib/types";

export default function FamilyPage() {
  const [goals, setGoals] = useState<ChildGoal[] | null>(null);
  const [ownership, setOwnership] = useState<OwnershipCard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.childGoals().then(setGoals).catch(() => setGoals([]));
    api.ownership().then(setOwnership).catch(() => undefined);
  }, []);

  return (
    <Page>
      <PageHeader
        eyebrow="Family"
        title="Child savings"
        lead="Optional. If you are saving for a child, this shows what your contributions imply over the years you have — and the questions that ownership raises."
      />

      {error ? <Notice tone="warning">{error}</Notice> : null}

      <Section title="Child goals">
        {goals === null ? (
          <Skeleton lines={3} />
        ) : goals.length === 0 ? (
          <EmptyState
            title="No child goals yet"
            body="Add one to see an illustrative projection over the years remaining."
          />
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2">
            {goals.map((goal) => (
              <li key={goal.id}>
                <ChildGoalCard
                  goal={goal}
                  onRemove={async () => {
                    await api.deleteChildGoal(goal.id).catch(() => undefined);
                    setGoals((current) => (current ?? []).filter((g) => g.id !== goal.id));
                  }}
                />
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Add a child goal">
        <ChildGoalForm
          onSubmit={async (payload) => {
            try {
              const created = await api.createChildGoal(payload);
              setGoals((current) => [...(current ?? []), created]);
            } catch (caught) {
              setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
            }
          }}
        />
      </Section>

      {ownership ? (
        <Section title={ownership.title}>
          <Card>
            <p className="mb-5 text-sm text-ink-muted">{ownership.note}</p>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[36rem] text-left text-sm">
                <thead>
                  <tr className="border-b border-rule text-xs uppercase tracking-wide text-ink-faint">
                    <th scope="col" className="py-2 pr-4 font-medium">
                      What changes
                    </th>
                    <th scope="col" className="py-2 pr-4 font-medium">
                      In your name
                    </th>
                    <th scope="col" className="py-2 font-medium">
                      In the child&rsquo;s name
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ownership.considerations.map((row) => (
                    <tr key={row.topic} className="border-b border-rule align-top last:border-0">
                      <th scope="row" className="py-3 pr-4 text-left font-medium">
                        {row.topic}
                      </th>
                      <td className="py-3 pr-4 text-ink-muted">{row.parent_account}</td>
                      <td className="py-3 text-ink-muted">{row.child_account}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-6 rounded-[4px] border border-rule bg-paper-sunk p-4">
              <p className="eyebrow mb-2">Questions to check</p>
              <ul className="space-y-1.5">
                {ownership.questions_to_check.map((question) => (
                  <li key={question} className="flex gap-2 text-sm">
                    <span aria-hidden="true" className="text-cobalt">
                      ?
                    </span>
                    <span>{question}</span>
                  </li>
                ))}
              </ul>
            </div>

            <p className="mt-4 text-xs text-ink-faint">
              Nothing here is a recommendation, and there is no default. Which option suits a
              family depends on facts this product cannot see.
            </p>
          </Card>
        </Section>
      ) : null}
    </Page>
  );
}

function ChildGoalCard({ goal, onRemove }: { goal: ChildGoal; onRemove: () => void }) {
  const [projection, setProjection] = useState<Projection | null>(null);
  const [returnPercent, setReturnPercent] = useState("5");

  async function project() {
    setProjection(
      await api
        .project({
          initial_minor: goal.current_minor,
          monthly_contribution_minor: goal.monthly_contribution_minor,
          annual_return: Number.parseFloat(returnPercent) / 100,
          months: goal.years_remaining * 12,
        })
        .catch(() => null),
    );
  }

  return (
    <Card>
      <h3 className="font-semibold">{goal.child_label}</h3>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <div>
          <dt className="eyebrow mb-0.5">Age now</dt>
          <dd className="tnum">{goal.child_age_years}</dd>
        </div>
        <div>
          <dt className="eyebrow mb-0.5">Target age</dt>
          <dd className="tnum">{goal.target_age_years}</dd>
        </div>
        <div>
          <dt className="eyebrow mb-0.5">Years remaining</dt>
          <dd className="tnum">{goal.years_remaining}</dd>
        </div>
        <div>
          <dt className="eyebrow mb-0.5">Current balance</dt>
          <dd className="tnum">{formatMinor(goal.current_minor, goal.currency)}</dd>
        </div>
        <div>
          <dt className="eyebrow mb-0.5">Monthly</dt>
          <dd className="tnum">{formatMinor(goal.monthly_contribution_minor, goal.currency)}</dd>
        </div>
        <div>
          <dt className="eyebrow mb-0.5">Target</dt>
          <dd className="tnum">{formatMinor(goal.target_minor, goal.currency)}</dd>
        </div>
      </dl>

      <div className="mt-4 flex items-end gap-2 border-t border-rule pt-4">
        <div className="w-32">
          <Field label="Assumed return (%)" htmlFor={`return-${goal.id}`}>
            <TextInput
              id={`return-${goal.id}`}
              inputMode="decimal"
              value={returnPercent}
              onChange={(event) => setReturnPercent(event.target.value)}
            />
          </Field>
        </div>
        <div className="mb-4">
          <Button variant="secondary" onClick={project}>
            Project
          </Button>
        </div>
      </div>

      {projection ? (
        <div className="rounded-[4px] bg-paper-sunk p-3">
          <p className="tnum text-lg font-semibold">
            {formatMinor(projection.final_balance_minor, goal.currency)}
          </p>
          <p className="text-xs text-ink-muted">
            at age {goal.target_age_years}, of which{" "}
            {formatMinor(projection.total_contributed_minor, goal.currency)} paid in
          </p>
          <p className="mt-2 text-xs text-ink-faint">{projection.disclaimer}</p>
        </div>
      ) : null}

      <button
        type="button"
        onClick={onRemove}
        className="mt-3 text-xs text-ink-faint underline underline-offset-4 hover:text-danger"
      >
        Remove
      </button>
    </Card>
  );
}

function ChildGoalForm({
  onSubmit,
}: {
  onSubmit: (payload: Record<string, unknown>) => Promise<void>;
}) {
  const [label, setLabel] = useState("");
  const [age, setAge] = useState("");
  const [targetAge, setTargetAge] = useState("18");
  const [target, setTarget] = useState("");
  const [current, setCurrent] = useState("");
  const [monthly, setMonthly] = useState("");

  const valid =
    label.trim() !== "" &&
    Number.isFinite(Number.parseInt(age, 10)) &&
    Number.parseInt(targetAge, 10) > Number.parseInt(age, 10);

  return (
    <Card>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field
          label="Name or nickname"
          htmlFor="child-label"
          hint="Whatever you want to call it. We never need a legal name."
        >
          <TextInput
            id="child-label"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
          />
        </Field>
        <Field label="Age now" htmlFor="child-age">
          <TextInput
            id="child-age"
            inputMode="numeric"
            value={age}
            onChange={(event) => setAge(event.target.value)}
          />
        </Field>
        <Field label="Target age" htmlFor="child-target-age">
          <TextInput
            id="child-target-age"
            inputMode="numeric"
            value={targetAge}
            onChange={(event) => setTargetAge(event.target.value)}
          />
        </Field>
        <Field label="Target amount (EUR)" htmlFor="child-target">
          <TextInput
            id="child-target"
            inputMode="decimal"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
          />
        </Field>
        <Field label="Already saved (EUR)" htmlFor="child-current">
          <TextInput
            id="child-current"
            inputMode="decimal"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
          />
        </Field>
        <Field label="Monthly contribution (EUR)" htmlFor="child-monthly">
          <TextInput
            id="child-monthly"
            inputMode="decimal"
            value={monthly}
            onChange={(event) => setMonthly(event.target.value)}
          />
        </Field>
      </div>
      <Button
        disabled={!valid}
        onClick={() =>
          onSubmit({
            child_label: label.trim(),
            child_age_years: Number.parseInt(age, 10),
            target_age_years: Number.parseInt(targetAge, 10),
            target_minor: parseMoneyInput(target) ?? 0,
            current_minor: parseMoneyInput(current) ?? 0,
            monthly_contribution_minor: parseMoneyInput(monthly) ?? 0,
          })
        }
      >
        Add child goal
      </Button>
    </Card>
  );
}
