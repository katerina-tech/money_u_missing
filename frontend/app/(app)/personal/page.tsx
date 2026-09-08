"use client";

/**
 * PERSONAL: what you already earn, what it costs you, who is at home.
 *
 * The page where a person types money figures about their own life, so it
 * carries two rules that the rest of the product only has to carry once:
 *
 * **Every amount is rendered with its basis attached.** "2,850 net" and
 * "2,850 gross" are different facts, and a figure shown without the label is
 * the wrong one half the time. The gross and net totals sit side by side and
 * are never added, because no honest sum of them exists - converting between
 * them needs a Steuerklasse and this product does not calculate tax.
 *
 * **Costs are recorded, never adjudicated.** There is no "deductible" column,
 * no estimated saving and no percentage for private use. What the page shows
 * instead is the total, the count without a receipt, and specific questions
 * worth putting to a Finanzamt - the useful thing a non-adviser can do.
 */

import { useCallback, useEffect, useState } from "react";

import {
  Button,
  Card,
  EmptyState,
  Field,
  Notice,
  Page,
  PageHeader,
  Section,
  Select,
  Skeleton,
  Stat,
  TextInput,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatMinor, parseMoneyInput } from "@/lib/format";
import type {
  AmountBasis,
  ExpenseCategory,
  LeaksResponse,
  PersonalOverview,
  Tristate,
} from "@/lib/types";

const BASIS_LABEL: Record<AmountBasis, string> = {
  NET: "Net (what reaches your account)",
  GROSS: "Gross (before deductions)",
  UNKNOWN: "I'm not sure",
};

const CATEGORY_LABEL: Record<ExpenseCategory, string> = {
  EQUIPMENT: "Equipment",
  SOFTWARE_AND_SUBSCRIPTIONS: "Software and subscriptions",
  TRAVEL: "Travel",
  WORKSPACE: "Workspace",
  PROFESSIONAL_DEVELOPMENT: "Training and development",
  PROFESSIONAL_SERVICES: "Professional services",
  INSURANCE_AND_CONTRIBUTIONS: "Insurance and contributions",
  MATERIALS: "Materials",
  COMMUNICATION: "Phone and internet",
  MARKETING: "Marketing",
  FEES_AND_CHARGES: "Fees and charges",
  OTHER: "Other",
};

const TRISTATE_LABEL: Record<Tristate, string> = {
  YES: "Yes",
  NO: "No",
  UNKNOWN: "Not sure",
};

export default function PersonalPage() {
  const [overview, setOverview] = useState<PersonalOverview | null>(null);
  // Loaded alongside the overview. A failure costs the section, not the page.
  const [leaks, setLeaks] = useState<LeaksResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setOverview(await api.personalOverview());
      setError(null);
      setLeaks(await api.leaks().catch(() => null));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : copy.errors.generic,
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!overview) {
    return (
      <Page>
        {error ? (
          <Notice tone="danger">{error}</Notice>
        ) : (
          <Skeleton lines={6} />
        )}
      </Page>
    );
  }

  const { baseline, expenses, household } = overview;

  return (
    <Page>
      <PageHeader
        eyebrow="Your account"
        title="Your money, as you describe it"
        lead="Everything here is what you entered. Nothing is estimated, nothing is converted, and no tax is calculated."
      />

      {error ? (
        <div className="mb-6">
          <Notice tone="warning">{error}</Notice>
        </div>
      ) : null}

      {/* ------------------------------------------------ current income */}
      <Section
        title="What you earn now"
        description="Your existing income, so an extra few hundred a month has something to be measured against."
      >
        <Card>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="Net, monthly"
              value={
                baseline.net_monthly_minor
                  ? formatMinor(baseline.net_monthly_minor, baseline.currency)
                  : "—"
              }
              detail="after deductions"
            />
            <Stat
              label="Gross, monthly"
              value={
                baseline.gross_monthly_minor
                  ? formatMinor(baseline.gross_monthly_minor, baseline.currency)
                  : "—"
              }
              detail="before deductions"
            />
            <Stat
              label="Basis not stated"
              value={
                baseline.unlabelled_monthly_minor
                  ? formatMinor(
                      baseline.unlabelled_monthly_minor,
                      baseline.currency,
                    )
                  : "—"
              }
              detail="counted separately"
              tone="muted"
            />
            <Stat
              label="Your goal"
              value={
                overview.goal_monthly_minor === null
                  ? "Not set"
                  : `${formatMinor(overview.goal_monthly_minor, baseline.currency)}/month`
              }
              detail={
                overview.uplift_ratio === null
                  ? "additional income"
                  : `about ${Math.round(overview.uplift_ratio * 100)}% on top`
              }
            />
          </div>

          {baseline.notes.length > 0 ? (
            <ul className="mt-6 space-y-1.5 border-t border-rule pt-5">
              {baseline.notes.map((note) => (
                <li key={note} className="text-xs text-ink-faint">
                  {note}
                </li>
              ))}
            </ul>
          ) : null}
        </Card>

        {baseline.entries.length > 0 ? (
          <ul className="mt-4 grid gap-px overflow-hidden rounded-[--radius-card] border border-rule bg-rule">
            {baseline.entries.map((entry) => (
              <li
                key={entry.id}
                className="flex flex-wrap items-baseline justify-between gap-3 bg-paper-raised p-4"
              >
                <div>
                  <p className="font-medium">
                    {entry.label}
                    {entry.is_primary ? (
                      <span className="ml-2 text-xs text-ink-faint">
                        main income
                      </span>
                    ) : null}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-faint">
                    {/* The basis travels with the figure, always. */}
                    {entry.basis === "UNKNOWN"
                      ? "You have not said whether this is gross or net"
                      : entry.basis === "NET"
                        ? "Net"
                        : "Gross"}
                    {entry.monthly_minor === null ? " · one-off" : " · monthly"}
                  </p>
                </div>
                <div className="flex items-baseline gap-4">
                  <span className="tnum text-lg">
                    {formatMinor(entry.amount_minor, entry.currency)}
                  </span>
                  <Button
                    variant="ghost"
                    onClick={async () => {
                      await api
                        .deleteBaselineIncome(entry.id)
                        .catch(() => undefined);
                      void load();
                    }}
                  >
                    Remove
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="mt-4">
            <EmptyState
              title="No income recorded yet"
              body="Add what you already earn. It is never shared, and it is only used to put your goal in proportion."
            />
          </div>
        )}

        <div className="mt-6">
          <IncomeForm
            onAdded={() => {
              void load();
            }}
            onError={setError}
          />
        </div>
      </Section>

      {/* ------------------------------------------------------ expenses */}
      <Section
        title="What it costs you"
        description="Costs you have paid in order to earn. Recorded, added up, and taken no further than that."
      >
        <Card>
          <div className="grid gap-6 sm:grid-cols-3">
            <Stat
              label="Recorded costs"
              value={formatMinor(expenses.total_minor, expenses.currency)}
              detail={`${expenses.count} item${expenses.count === 1 ? "" : "s"}`}
            />
            <Stat
              label="Without a receipt"
              value={`${expenses.without_receipt_count}`}
              detail="you have not confirmed evidence"
              tone="muted"
            />
            <Stat
              label="Tax effect"
              value="Not calculated"
              detail="see below"
              tone="muted"
            />
          </div>

          {expenses.by_category.length > 0 ? (
            <div className="mt-6 overflow-x-auto border-t border-rule pt-5">
              <table className="w-full min-w-[30rem] text-left text-sm">
                <thead>
                  <tr className="border-b border-rule text-xs uppercase tracking-wide text-ink-faint">
                    <th scope="col" className="py-2 pr-4 font-medium">
                      Category
                    </th>
                    <th
                      scope="col"
                      className="py-2 pr-4 text-right font-medium"
                    >
                      Total
                    </th>
                    <th
                      scope="col"
                      className="py-2 pr-4 text-right font-medium"
                    >
                      Items
                    </th>
                    <th scope="col" className="py-2 text-right font-medium">
                      No receipt
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {expenses.by_category.map((row) => (
                    <tr
                      key={row.category}
                      className="border-b border-rule last:border-0"
                    >
                      <th
                        scope="row"
                        className="py-2.5 pr-4 text-left font-normal"
                      >
                        {CATEGORY_LABEL[row.category]}
                      </th>
                      <td className="tnum py-2.5 pr-4 text-right">
                        {formatMinor(row.total_minor, expenses.currency)}
                      </td>
                      <td className="tnum py-2.5 pr-4 text-right text-ink-muted">
                        {row.count}
                      </td>
                      <td className="tnum py-2.5 text-right text-ink-muted">
                        {row.without_receipt || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          <p className="mt-5 border-t border-rule pt-4 text-xs text-ink-faint">
            {expenses.disclaimer}
          </p>
        </Card>

        <div className="mt-6">
          <ExpenseForm
            onAdded={() => {
              void load();
            }}
            onError={setError}
          />
        </div>
      </Section>

      {/* ----------------------------------------------------- household */}
      <Section
        title="Your household"
        description="Optional, and never assumed. Telling us adds the questions it raises; it does not change any figure on this page."
      >
        <HouseholdForm
          household={household}
          onSaved={() => {
            void load();
          }}
          onError={setError}
        />
      </Section>

      {/* ------------------------------------------ money you may be losing */}
      {leaks && leaks.leaks.length > 0 ? (
        <Section
          title="Money you may be losing"
          description="Raised from what you have told us, not from a generic checklist. Each one says why it applies to you."
        >
          <ul className="grid gap-4">
            {leaks.leaks.map((leak) => (
              <li key={leak.id}>
                <Card>
                  <div className="flex flex-wrap items-baseline justify-between gap-3">
                    <h3 className="font-semibold">{leak.title}</h3>
                    {leak.stated_amount_minor !== null ? (
                      <span className="tnum rounded-[4px] border border-rule bg-paper-sunk px-2 py-0.5 text-sm">
                        {formatMinor(leak.stated_amount_minor)}
                      </span>
                    ) : null}
                  </div>

                  <p className="mt-2 text-sm text-ink-muted">
                    {leak.why_this_applies}
                  </p>

                  <div className="mt-4 rounded-[4px] border border-rule bg-paper-sunk p-3">
                    <p className="eyebrow mb-1">What to check</p>
                    <p className="text-sm">{leak.what_to_check}</p>
                  </div>

                  {/* A figure only ever appears with the note saying whose
                      figure it is. The API guarantees the pairing; this
                      renders it rather than deciding it. */}
                  {leak.amount_note ? (
                    <p className="mt-3 text-xs text-ink-faint">
                      {leak.amount_note}
                    </p>
                  ) : null}

                  {leak.fact_ids.length === 0 ? (
                    <p className="mt-3 text-xs text-ink-faint">
                      We have no verified source recorded for this one, so no
                      figure is shown — only the question.
                    </p>
                  ) : null}
                </Card>
              </li>
            ))}
          </ul>

          <p className="mt-4 text-xs text-ink-faint">{leaks.disclaimer}</p>
        </Section>
      ) : null}

      {/* ------------------------------------------- questions and sources */}
      {overview.questions_to_check.length > 0 || overview.facts.length > 0 ? (
        <Section title="What to check in Germany">
          <Card>
            {overview.questions_to_check.length > 0 ? (
              <>
                <p className="eyebrow mb-2">Questions to check</p>
                <ul className="space-y-1.5">
                  {overview.questions_to_check.map((question) => (
                    <li key={question} className="flex gap-2 text-sm">
                      <span aria-hidden="true" className="text-cobalt">
                        ?
                      </span>
                      <span>{question}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            {expenses.questions_to_check.length > 0 ? (
              <ul className="mt-3 space-y-1.5">
                {expenses.questions_to_check.map((question) => (
                  <li key={question} className="flex gap-2 text-sm">
                    <span aria-hidden="true" className="text-cobalt">
                      ?
                    </span>
                    <span>{question}</span>
                  </li>
                ))}
              </ul>
            ) : null}

            {overview.facts.length > 0 ? (
              <div className="mt-6 border-t border-rule pt-5">
                <p className="eyebrow mb-3">Sources</p>
                <ul className="space-y-3">
                  {overview.facts.map((fact) => (
                    <li key={fact.id}>
                      <p className="text-sm font-medium">{fact.title}</p>
                      <p className="mt-0.5 text-sm text-ink-muted">
                        {fact.summary}
                      </p>
                      {fact.source_url ? (
                        <a
                          href={fact.source_url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="mt-1 inline-block text-xs text-cobalt underline underline-offset-4"
                        >
                          {fact.source_name}
                        </a>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <p className="mt-6 border-t border-rule pt-4 text-xs text-ink-faint">
              {overview.disclaimer}
            </p>
          </Card>
        </Section>
      ) : null}
    </Page>
  );
}

// ============================================================== forms

function IncomeForm({
  onAdded,
  onError,
}: {
  onAdded: () => void;
  onError: (message: string) => void;
}) {
  const [label, setLabel] = useState("");
  const [amount, setAmount] = useState("");
  const [basis, setBasis] = useState<AmountBasis>("NET");
  const [oneOff, setOneOff] = useState(false);
  const [busy, setBusy] = useState(false);

  const amountMinor = parseMoneyInput(amount);
  const ready = label.trim().length > 0 && amountMinor !== null;

  return (
    <Card>
      <h3 className="mb-4 font-semibold">Add income you already have</h3>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="What is it?" htmlFor="income-label">
          <TextInput
            id="income-label"
            value={label}
            placeholder="Main job"
            onChange={(event) => setLabel(event.target.value)}
          />
        </Field>
        <Field label="Amount" htmlFor="income-amount">
          <TextInput
            id="income-amount"
            inputMode="decimal"
            value={amount}
            placeholder="2850"
            onChange={(event) => setAmount(event.target.value)}
          />
        </Field>
        <Field
          label="Gross or net?"
          htmlFor="income-basis"
          hint="We store what you choose and never convert between the two."
        >
          <Select
            id="income-basis"
            value={basis}
            onChange={(event) => setBasis(event.target.value as AmountBasis)}
          >
            {(["NET", "GROSS", "UNKNOWN"] as AmountBasis[]).map((option) => (
              <option key={option} value={option}>
                {BASIS_LABEL[option]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="How often?" htmlFor="income-period">
          <Select
            id="income-period"
            value={oneOff ? "ONE_TIME" : "RECURRING"}
            onChange={(event) => setOneOff(event.target.value === "ONE_TIME")}
          >
            <option value="RECURRING">Every month</option>
            <option value="ONE_TIME">One-off</option>
          </Select>
        </Field>
      </div>

      <div className="mt-4">
        <Button
          disabled={!ready || busy}
          onClick={async () => {
            if (amountMinor === null) return;
            setBusy(true);
            try {
              await api.addBaselineIncome({
                label: label.trim(),
                amount_minor: amountMinor,
                basis,
                period: oneOff ? "ONE_TIME" : "RECURRING",
              });
              setLabel("");
              setAmount("");
              onAdded();
            } catch (caught) {
              onError(
                caught instanceof ApiError
                  ? caught.message
                  : copy.errors.generic,
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Saving…" : "Add income"}
        </Button>
      </div>
    </Card>
  );
}

function ExpenseForm({
  onAdded,
  onError,
}: {
  onAdded: () => void;
  onError: (message: string) => void;
}) {
  const [label, setLabel] = useState("");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState<ExpenseCategory>("EQUIPMENT");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [receipt, setReceipt] = useState<Tristate>("UNKNOWN");
  const [privateUse, setPrivateUse] = useState<Tristate>("UNKNOWN");
  const [busy, setBusy] = useState(false);

  const amountMinor = parseMoneyInput(amount);
  const ready = label.trim().length > 0 && amountMinor !== null;

  return (
    <Card>
      <h3 className="mb-1 font-semibold">Record a cost</h3>
      <p className="mb-4 text-sm text-ink-muted">
        Recording a cost here is not a claim that it reduces your tax. That
        depends on facts this product cannot assess.
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="What was it?" htmlFor="expense-label">
          <TextInput
            id="expense-label"
            value={label}
            placeholder="Laptop"
            onChange={(event) => setLabel(event.target.value)}
          />
        </Field>
        <Field label="Amount" htmlFor="expense-amount">
          <TextInput
            id="expense-amount"
            inputMode="decimal"
            value={amount}
            placeholder="1200"
            onChange={(event) => setAmount(event.target.value)}
          />
        </Field>
        <Field label="Category" htmlFor="expense-category">
          <Select
            id="expense-category"
            value={category}
            onChange={(event) =>
              setCategory(event.target.value as ExpenseCategory)
            }
          >
            {(Object.keys(CATEGORY_LABEL) as ExpenseCategory[]).map(
              (option) => (
                <option key={option} value={option}>
                  {CATEGORY_LABEL[option]}
                </option>
              ),
            )}
          </Select>
        </Field>
        <Field label="Date" htmlFor="expense-date">
          <TextInput
            id="expense-date"
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </Field>
        <Field label="Do you have a receipt?" htmlFor="expense-receipt">
          <Select
            id="expense-receipt"
            value={receipt}
            onChange={(event) => setReceipt(event.target.value as Tristate)}
          >
            {(["UNKNOWN", "YES", "NO"] as Tristate[]).map((option) => (
              <option key={option} value={option}>
                {TRISTATE_LABEL[option]}
              </option>
            ))}
          </Select>
        </Field>
        <Field
          label="Partly private?"
          htmlFor="expense-private"
          hint="Recorded as you state it. We do not work out a share."
        >
          <Select
            id="expense-private"
            value={privateUse}
            onChange={(event) => setPrivateUse(event.target.value as Tristate)}
          >
            {(["UNKNOWN", "YES", "NO"] as Tristate[]).map((option) => (
              <option key={option} value={option}>
                {TRISTATE_LABEL[option]}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="mt-4">
        <Button
          disabled={!ready || busy}
          onClick={async () => {
            if (amountMinor === null) return;
            setBusy(true);
            try {
              await api.addExpense({
                label: label.trim(),
                amount_minor: amountMinor,
                category,
                incurred_on: date,
                has_receipt: receipt,
                partly_private: privateUse,
              });
              setLabel("");
              setAmount("");
              onAdded();
            } catch (caught) {
              onError(
                caught instanceof ApiError
                  ? caught.message
                  : copy.errors.generic,
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Saving…" : "Record cost"}
        </Button>
      </div>
    </Card>
  );
}

function HouseholdForm({
  household,
  onSaved,
  onError,
}: {
  household: PersonalOverview["household"];
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  const [hasChildren, setHasChildren] = useState<Tristate>(
    household.has_children,
  );
  const [jointly, setJointly] = useState<Tristate>(household.jointly_assessed);
  const [children, setChildren] = useState(household.children);
  const [childAge, setChildAge] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <Card>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Do you have children?"
          htmlFor="household-children"
          hint="Never inferred from your profile. Answer only if you want the questions it raises."
        >
          <Select
            id="household-children"
            value={hasChildren}
            onChange={(event) => setHasChildren(event.target.value as Tristate)}
          >
            <option value="UNKNOWN">Prefer not to say</option>
            <option value="YES">Yes</option>
            <option value="NO">No</option>
          </Select>
        </Field>
        <Field label="Assessed jointly?" htmlFor="household-jointly">
          <Select
            id="household-jointly"
            value={jointly}
            onChange={(event) => setJointly(event.target.value as Tristate)}
          >
            <option value="UNKNOWN">Not sure</option>
            <option value="YES">Yes</option>
            <option value="NO">No</option>
          </Select>
        </Field>
      </div>

      {hasChildren === "YES" ? (
        <div className="mt-5 border-t border-rule pt-5">
          <p className="eyebrow mb-2">Ages</p>
          <p className="mb-3 text-xs text-ink-faint">
            Ages only. We do not ask for names or dates of birth, because the
            questions this page raises do not need them.
          </p>
          {children.length > 0 ? (
            <ul className="mb-3 flex flex-wrap gap-2">
              {children.map((child, index) => (
                <li
                  key={`${child.label}-${index}`}
                  className="rounded-[4px] border border-rule bg-paper-sunk px-2.5 py-1 text-sm"
                >
                  {child.age_years} years
                  <button
                    type="button"
                    aria-label={`Remove child aged ${child.age_years}`}
                    className="ml-2 text-ink-faint hover:text-danger"
                    onClick={() =>
                      setChildren(children.filter((_, i) => i !== index))
                    }
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="flex items-end gap-2">
            <div className="w-28">
              <Field label="Age" htmlFor="child-age">
                <TextInput
                  id="child-age"
                  inputMode="numeric"
                  value={childAge}
                  onChange={(event) => setChildAge(event.target.value)}
                />
              </Field>
            </div>
            <div className="mb-4">
              <Button
                variant="secondary"
                onClick={() => {
                  const age = Number.parseInt(childAge, 10);
                  if (Number.isNaN(age) || age < 0 || age > 30) return;
                  setChildren([
                    ...children,
                    {
                      label: `Child ${children.length + 1}`,
                      age_years: age,
                      in_education_or_training: "UNKNOWN",
                    },
                  ]);
                  setChildAge("");
                }}
              >
                Add
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="mt-5 border-t border-rule pt-5">
        <Button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await api.setHousehold({
                has_children: hasChildren,
                jointly_assessed: jointly,
                // The API rejects children alongside "no children", so the
                // list is cleared here rather than sent and refused.
                children: hasChildren === "YES" ? children : [],
              });
              onSaved();
            } catch (caught) {
              onError(
                caught instanceof ApiError
                  ? caught.message
                  : copy.errors.generic,
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Saving…" : "Save household details"}
        </Button>
      </div>
    </Card>
  );
}
