"use client";

/**
 * The dismiss dialog.
 *
 * A reason is required, and that is not friction for its own sake: the reason
 * is the entire learning signal. A dismissal with no reason teaches the ranking
 * nothing, and the user can see exactly what it taught it on the settings page.
 */

import { useEffect, useRef, useState } from "react";

import { Button, TextArea } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { DISMISS_REASONS } from "@/lib/format";

export function DismissDialog({
  opportunityId,
  onClose,
  onDismissed,
}: {
  opportunityId: string;
  onClose: () => void;
  onDismissed: () => void;
}) {
  const [reason, setReason] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    dialogRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit() {
    if (!reason) return;
    setBusy(true);
    try {
      await api.dismiss(opportunityId, reason, note || undefined);
      onDismissed();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save that.");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-4 sm:items-center">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dismiss-title"
        tabIndex={-1}
        className="w-full max-w-md rounded-[--radius-card] border border-rule bg-paper-raised p-6"
      >
        <h2 id="dismiss-title" className="text-lg font-semibold">
          Why is this not for you?
        </h2>
        <p className="mt-1 text-sm text-ink-muted">
          Your answer changes how future opportunities are ranked. You can see and reset that in
          settings.
        </p>

        <fieldset className="mt-4">
          <legend className="sr-only">Reason</legend>
          <div className="grid gap-1.5">
            {DISMISS_REASONS.map((option) => (
              <label
                key={option.value}
                className={`flex cursor-pointer items-center gap-2.5 rounded-[4px] border px-3 py-2 text-sm ${
                  reason === option.value
                    ? "border-cobalt bg-cobalt-wash"
                    : "border-rule hover:border-rule-strong"
                }`}
              >
                <input
                  type="radio"
                  name="dismiss-reason"
                  value={option.value}
                  checked={reason === option.value}
                  onChange={() => setReason(option.value)}
                  className="accent-cobalt"
                />
                {option.label}
              </label>
            ))}
          </div>
        </fieldset>

        {reason === "OTHER" ? (
          <div className="mt-3">
            <label htmlFor="dismiss-note" className="mb-1 block text-sm font-medium">
              Tell us more (optional)
            </label>
            <TextArea
              id="dismiss-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              className="min-h-20"
            />
          </div>
        ) : null}

        {error ? (
          <p role="alert" className="mt-3 text-sm text-danger">
            {error}
          </p>
        ) : null}

        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!reason || busy}>
            {busy ? "Saving…" : "Dismiss"}
          </Button>
        </div>
      </div>
    </div>
  );
}
