"use client";

/**
 * Importing a bank statement the user exported themselves.
 *
 * The screen is built around one rule from the parser: **a category is
 * suggested, never assigned**. So the table shows a checkbox per line, the
 * bank's own figures beside it, and the reason for any suggestion in plain
 * words. Rows the rules recognised arrive ticked; everything else arrives
 * unticked, because most of a personal statement is groceries and rent and
 * this product's categories are business costs.
 *
 * Nothing leaves this component until "Record selected" is pressed, and what
 * is sent is what the user ticked - not what the server proposed.
 */

import { useState } from "react";

import { Button, Card, Notice, Section, Select } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { formatMinor } from "@/lib/format";
import type { ExpenseCategory, StatementPreview } from "@/lib/types";

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

interface Choice {
  keep: boolean;
  category: ExpenseCategory;
}

export function StatementImport({ onImported }: { onImported: () => void }) {
  const [preview, setPreview] = useState<StatementPreview | null>(null);
  const [choices, setChoices] = useState<Choice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<number | null>(null);

  async function load(file: File) {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const result = await api.previewStatement(file);
      setPreview(result);
      // The server's suggestion becomes the starting position, not the
      // decision: a suggested row starts ticked, everything else does not.
      setChoices(
        result.rows.map((item) => ({
          keep: item.suggested,
          category: item.category ?? "OTHER",
        })),
      );
    } catch (caught) {
      setPreview(null);
      setError(
        caught instanceof ApiError ? caught.message : copy.errors.generic,
      );
    } finally {
      setBusy(false);
    }
  }

  async function record() {
    if (!preview) return;
    const items = preview.rows
      .map((item, index) => ({ item, choice: choices[index] }))
      .filter(({ choice }) => choice?.keep)
      .map(({ item, choice }) => ({
        label:
          item.row.counterparty || item.row.reference || "Bank transaction",
        // An expense is a cost, so the statement's minus sign has already done
        // its job by showing which lines were money leaving.
        amount_minor: Math.abs(item.row.amount_minor),
        category: choice!.category,
        incurred_on: item.row.booked_on,
        notes: item.row.reference || null,
      }));

    if (items.length === 0) return;

    setBusy(true);
    try {
      const result = await api.importStatement(items);
      setDone(result.imported);
      setPreview(null);
      setChoices([]);
      onImported();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : copy.errors.generic,
      );
    } finally {
      setBusy(false);
    }
  }

  const selected = choices.filter((choice) => choice.keep).length;

  return (
    <Section
      title="Import from your bank"
      description="Export a statement from your own online banking and upload the file. No bank login, no password, and nothing is recorded until you choose it."
    >
      <Card>
        <p className="mb-4 text-sm text-ink-muted">
          Upload the <strong>PDF</strong> your Sparkasse sends, or export{" "}
          <strong>Umsätze</strong> → <strong>CSV-CAMT</strong> /{" "}
          <strong>CAMT.053</strong>. Three to twelve months gives the clearest
          picture.
        </p>

        <input
          type="file"
          accept=".pdf,.csv,.xml,.txt,.camt"
          disabled={busy}
          aria-label="Statement file"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void load(file);
          }}
          className="block w-full text-sm file:mr-3 file:rounded-[4px] file:border file:border-rule file:bg-paper-sunk file:px-3 file:py-1.5 file:text-sm"
        />

        {error ? (
          <div className="mt-4">
            <Notice tone="warning">{error}</Notice>
          </div>
        ) : null}

        {done !== null ? (
          <div className="mt-4">
            <Notice tone="info">
              {done} line{done === 1 ? "" : "s"} recorded. Nothing else from the
              file was kept.
            </Notice>
          </div>
        ) : null}
      </Card>

      {preview ? (
        <div className="mt-4">
          <Card>
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
              <p className="text-sm text-ink-muted">
                {preview.total_rows} line{preview.total_rows === 1 ? "" : "s"} ·{" "}
                {preview.outgoing_rows} outgoing · {preview.suggested_rows}{" "}
                recognised
              </p>
              <p className="tnum text-sm">{selected} selected</p>
            </div>

            {/* A layout-read PDF can miss a line silently, so the parser checks
                itself against the statement's own balances and the result is
                shown rather than assumed. */}
            {preview.reconciliation?.checked ? (
              <div className="mb-4">
                {preview.reconciliation.reconciles ? (
                  <p className="text-xs text-verified">
                    ✓ These lines add up exactly to the change between the
                    opening and closing balance printed on the statement, so
                    nothing was missed.
                  </p>
                ) : (
                  <Notice tone="warning">
                    These lines do not add up to the change between the opening
                    and closing balance on the statement, so some may have been
                    missed. Check against the original before recording
                    anything.
                  </Notice>
                )}
              </div>
            ) : null}

            <div className="overflow-x-auto">
              <table className="w-full min-w-[46rem] text-left text-sm">
                <thead>
                  <tr className="border-b border-rule text-xs tracking-wide text-ink-faint uppercase">
                    <th scope="col" className="py-2 pr-3 font-medium">
                      Keep
                    </th>
                    <th scope="col" className="py-2 pr-3 font-medium">
                      Date
                    </th>
                    <th scope="col" className="py-2 pr-3 font-medium">
                      Who
                    </th>
                    <th
                      scope="col"
                      className="py-2 pr-3 text-right font-medium"
                    >
                      Amount
                    </th>
                    <th scope="col" className="py-2 font-medium">
                      Category
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((item, index) => {
                    const choice = choices[index];
                    const incoming = item.row.amount_minor > 0;
                    return (
                      <tr
                        key={`${item.row.booked_on}-${index}`}
                        className="border-b border-rule align-top last:border-0"
                      >
                        <td className="py-2.5 pr-3">
                          <input
                            type="checkbox"
                            checked={choice?.keep ?? false}
                            disabled={incoming}
                            aria-label={`Keep ${item.row.counterparty ?? "this line"}`}
                            onChange={(event) =>
                              setChoices((current) =>
                                current.map((existing, position) =>
                                  position === index
                                    ? {
                                        ...existing,
                                        keep: event.target.checked,
                                      }
                                    : existing,
                                ),
                              )
                            }
                          />
                        </td>
                        <td className="tnum py-2.5 pr-3 whitespace-nowrap text-ink-muted">
                          {item.row.booked_on}
                        </td>
                        <td className="py-2.5 pr-3">
                          <p>{item.row.counterparty ?? "—"}</p>
                          {item.row.reference ? (
                            <p className="text-xs text-ink-faint">
                              {item.row.reference}
                            </p>
                          ) : null}
                          {/* The reason a suggestion exists, stated so it can be
                              disagreed with rather than merely accepted. */}
                          {item.suggested && item.reason ? (
                            <p className="mt-0.5 text-xs text-cobalt">
                              suggested — {item.reason}
                            </p>
                          ) : null}
                        </td>
                        <td
                          className={
                            "tnum py-2.5 pr-3 text-right whitespace-nowrap " +
                            (incoming ? "text-verified" : "")
                          }
                        >
                          {formatMinor(
                            item.row.amount_minor,
                            item.row.currency,
                          )}
                        </td>
                        <td className="py-2.5">
                          {incoming ? (
                            <span className="text-xs text-ink-faint">
                              money in — not a cost
                            </span>
                          ) : (
                            <Select
                              aria-label="Category"
                              value={choice?.category ?? "OTHER"}
                              onChange={(event) =>
                                setChoices((current) =>
                                  current.map((existing, position) =>
                                    position === index
                                      ? {
                                          ...existing,
                                          category: event.target
                                            .value as ExpenseCategory,
                                        }
                                      : existing,
                                  ),
                                )
                              }
                            >
                              {(
                                Object.keys(CATEGORY_LABEL) as ExpenseCategory[]
                              ).map((option) => (
                                <option key={option} value={option}>
                                  {CATEGORY_LABEL[option]}
                                </option>
                              ))}
                            </Select>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <p className="mt-4 text-xs text-ink-faint">{preview.note}</p>

            <div className="mt-5 border-t border-rule pt-5">
              <Button disabled={busy || selected === 0} onClick={record}>
                {busy
                  ? "Recording…"
                  : `Record ${selected} selected line${selected === 1 ? "" : "s"}`}
              </Button>
            </div>
          </Card>
        </div>
      ) : null}
    </Section>
  );
}
