"use client";

/**
 * GROW: goals, a savings calculator, ETF education.
 *
 * The calculator takes the user's own return assumption and shows what it
 * implies. It does not suggest a rate, and there is no default that could be
 * read as a recommendation - the field starts empty-ish at a neutral value the
 * user is expected to change, and every output carries the illustrative label.
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
  ProgressBar,
  Section,
  Select,
  Skeleton,
  TextInput,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatMinor, parseMoneyInput, titleCase } from "@/lib/format";
import type { Goal, Projection } from "@/lib/types";

const GOAL_TYPES = ["EMERGENCY_FUND", "HOME", "EDUCATION", "RETIREMENT", "CHILD", "OTHER"];

export default function GrowPage() {
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .goals()
      .then(setGoals)
      .catch(() => setGoals([]));
  }, []);

  async function addGoal(payload: Record<string, unknown>) {
    try {
      const created = await api.createGoal(payload);
      setGoals((current) => [...(current ?? []), created]);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
    }
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Grow"
        title="Goals and projections"
        lead="Connect additional income to what you actually want it for. Every figure here is arithmetic over assumptions you choose — nothing is forecast, and nothing is recommended."
      />

      <Notice tone="info">{copy.disclaimers.investment}</Notice>

      {error ? (
        <div className="mt-4">
          <Notice tone="warning">{error}</Notice>
        </div>
      ) : null}

      <Section title="Your goals">
        {goals === null ? (
          <Skeleton lines={3} />
        ) : goals.length === 0 ? (
          <EmptyState
            title="No goals yet"
            body="A goal turns 'earn more' into something you can measure. Add one below."
          />
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2">
            {goals.map((goal) => (
              <li key={goal.id}>
                <Card>
                  <div className="mb-2 flex items-baseline justify-between gap-2">
                    <h3 className="font-semibold">{goal.name}</h3>
                    <span className="text-xs text-ink-faint">{titleCase(goal.goal_type)}</span>
                  </div>
                  <p className="tnum text-sm text-ink-muted">
                    {formatMinor(goal.current_minor, goal.currency)} of{" "}
                    {formatMinor(goal.target_minor, goal.currency)}
                  </p>
                  <div className="mt-3">
                    <ProgressBar ratio={goal.progress_ratio} label="Progress" />
                  </div>
                  <p className="mt-3 text-xs text-ink-faint">
                    {goal.months_at_current_contribution === null
                      ? "Add a monthly contribution to see how long this takes."
                      : goal.months_at_current_contribution === 0
                        ? "Target reached."
                        : `${goal.months_at_current_contribution} months at ${formatMinor(goal.monthly_contribution_minor, goal.currency)}/month, ignoring any growth.`}
                  </p>
                  <button
                    type="button"
                    onClick={async () => {
                      await api.deleteGoal(goal.id).catch(() => undefined);
                      setGoals((current) => (current ?? []).filter((g) => g.id !== goal.id));
                    }}
                    className="mt-3 text-xs text-ink-faint underline underline-offset-4 hover:text-danger"
                  >
                    Remove
                  </button>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Add a goal">
        <GoalForm onSubmit={addGoal} />
      </Section>

      <Section
        title="Savings calculator"
        description="You choose the assumptions. We do the arithmetic and label it as illustrative, because that is what it is."
      >
        <Calculator />
      </Section>

      <Section title="ETF terminology">
        <EtfEducation />
      </Section>
    </Page>
  );
}

function GoalForm({ onSubmit }: { onSubmit: (payload: Record<string, unknown>) => Promise<void> }) {
  const [name, setName] = useState("");
  const [type, setType] = useState("EMERGENCY_FUND");
  const [target, setTarget] = useState("");
  const [current, setCurrent] = useState("");
  const [monthly, setMonthly] = useState("");

  const targetMinor = parseMoneyInput(target);

  return (
    <Card>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Name" htmlFor="goal-name">
          <TextInput
            id="goal-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Emergency fund"
          />
        </Field>
        <Field label="Type" htmlFor="goal-type">
          <Select id="goal-type" value={type} onChange={(event) => setType(event.target.value)}>
            {GOAL_TYPES.map((option) => (
              <option key={option} value={option}>
                {titleCase(option)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Target amount (EUR)" htmlFor="goal-target">
          <TextInput
            id="goal-target"
            inputMode="decimal"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            placeholder="6000"
          />
        </Field>
        <Field label="Already saved (EUR)" htmlFor="goal-current">
          <TextInput
            id="goal-current"
            inputMode="decimal"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            placeholder="0"
          />
        </Field>
        <Field label="Monthly contribution (EUR)" htmlFor="goal-monthly">
          <TextInput
            id="goal-monthly"
            inputMode="decimal"
            value={monthly}
            onChange={(event) => setMonthly(event.target.value)}
            placeholder="200"
          />
        </Field>
      </div>
      <Button
        disabled={!name.trim() || targetMinor === null}
        onClick={() =>
          onSubmit({
            goal_type: type,
            name: name.trim(),
            target_minor: targetMinor ?? 0,
            current_minor: parseMoneyInput(current) ?? 0,
            monthly_contribution_minor: parseMoneyInput(monthly) ?? 0,
          })
        }
      >
        Add goal
      </Button>
    </Card>
  );
}

function Calculator() {
  const [initial, setInitial] = useState("0");
  const [monthly, setMonthly] = useState("200");
  const [returnPercent, setReturnPercent] = useState("5");
  const [years, setYears] = useState("10");
  const [inflation, setInflation] = useState("");
  const [result, setResult] = useState<Projection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(
        await api.project({
          initial_minor: parseMoneyInput(initial) ?? 0,
          monthly_contribution_minor: parseMoneyInput(monthly) ?? 0,
          annual_return: Number.parseFloat(returnPercent) / 100,
          months: Math.round(Number.parseFloat(years) * 12),
          annual_inflation: inflation ? Number.parseFloat(inflation) / 100 : null,
        }),
      );
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Those assumptions are outside what we will render.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Field label="Starting amount (EUR)" htmlFor="calc-initial">
          <TextInput
            id="calc-initial"
            inputMode="decimal"
            value={initial}
            onChange={(event) => setInitial(event.target.value)}
          />
        </Field>
        <Field label="Monthly (EUR)" htmlFor="calc-monthly">
          <TextInput
            id="calc-monthly"
            inputMode="decimal"
            value={monthly}
            onChange={(event) => setMonthly(event.target.value)}
          />
        </Field>
        <Field
          label="Assumed return (% a year)"
          htmlFor="calc-return"
          hint="Your assumption. We do not suggest one."
        >
          <TextInput
            id="calc-return"
            inputMode="decimal"
            value={returnPercent}
            onChange={(event) => setReturnPercent(event.target.value)}
          />
        </Field>
        <Field label="Years" htmlFor="calc-years">
          <TextInput
            id="calc-years"
            inputMode="decimal"
            value={years}
            onChange={(event) => setYears(event.target.value)}
          />
        </Field>
        <Field label="Inflation (%, optional)" htmlFor="calc-inflation">
          <TextInput
            id="calc-inflation"
            inputMode="decimal"
            value={inflation}
            onChange={(event) => setInflation(event.target.value)}
            placeholder="2"
          />
        </Field>
      </div>

      <Button onClick={run} disabled={busy}>
        {busy ? "Calculating…" : "Calculate"}
      </Button>

      {error ? (
        <div className="mt-4">
          <Notice tone="warning">{error}</Notice>
        </div>
      ) : null}

      {result ? (
        <div className="mt-6 border-t border-rule pt-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <p className="eyebrow mb-0.5">You would pay in</p>
              <p className="tnum text-xl font-semibold">
                {formatMinor(result.total_contributed_minor)}
              </p>
            </div>
            <div>
              <p className="eyebrow mb-0.5">Illustrative balance</p>
              <p className="tnum text-xl font-semibold">
                {formatMinor(result.final_balance_minor)}
              </p>
            </div>
            <div>
              <p className="eyebrow mb-0.5">
                {result.final_real_balance_minor !== null
                  ? "In today's money"
                  : "Growth"}
              </p>
              <p className="tnum text-xl font-semibold text-ink-muted">
                {formatMinor(
                  result.final_real_balance_minor ?? result.growth_minor,
                )}
              </p>
            </div>
          </div>

          {/* A plain table rather than a chart. At this many points a chart
              would add visual authority the numbers have not earned. */}
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[30rem] text-left text-sm">
              <thead className="text-xs text-ink-faint">
                <tr>
                  <th scope="col" className="py-1.5 font-medium">
                    Year
                  </th>
                  <th scope="col" className="py-1.5 font-medium">
                    Paid in
                  </th>
                  <th scope="col" className="py-1.5 font-medium">
                    Illustrative balance
                  </th>
                  {result.annual_inflation !== null ? (
                    <th scope="col" className="py-1.5 font-medium">
                      In today&rsquo;s money
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {result.points
                  .filter((point) => point.month > 0)
                  .map((point) => (
                    <tr key={point.month} className="border-t border-rule">
                      <td className="tnum py-1.5">{Math.round(point.month / 12)}</td>
                      <td className="tnum py-1.5 text-ink-muted">
                        {formatMinor(point.contributed_minor)}
                      </td>
                      <td className="tnum py-1.5">{formatMinor(point.balance_minor)}</td>
                      {result.annual_inflation !== null ? (
                        <td className="tnum py-1.5 text-ink-muted">
                          {formatMinor(point.real_balance_minor)}
                        </td>
                      ) : null}
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>

          <p className="mt-4 rounded-[4px] bg-paper-sunk p-3 text-xs text-ink-muted">
            {result.disclaimer}
          </p>
        </div>
      ) : null}
    </Card>
  );
}

function EtfEducation() {
  const [terms, setTerms] = useState<{ term: string; explanation: string }[] | null>(null);
  const [disclaimer, setDisclaimer] = useState("");

  useEffect(() => {
    api
      .etfEducation()
      .then((payload) => {
        setTerms(payload.terms);
        setDisclaimer(payload.disclaimer);
      })
      .catch(() => setTerms([]));
  }, []);

  if (terms === null) return <Skeleton lines={4} />;

  return (
    <Card>
      <p className="mb-4 text-xs text-ink-faint">{disclaimer}</p>
      <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
        {terms.map((entry) => (
          <div key={entry.term}>
            <dt className="text-sm font-semibold">{entry.term}</dt>
            <dd className="mt-1 text-sm text-ink-muted">{entry.explanation}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-5 border-t border-rule pt-4 text-xs text-ink-faint">
        We explain how these instruments work. We do not tell you which to buy, do not rank
        products, and do not produce a personal allocation — those are regulated activities.
        See the regulatory boundaries note in the repository.
      </p>
    </Card>
  );
}
