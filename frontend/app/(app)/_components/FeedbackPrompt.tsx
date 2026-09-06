"use client";

/**
 * The validation instrument.
 *
 * This is the startup's actual evidence, so it appears in the product rather
 * than in a separate survey nobody opens. Two questions, both about whether the
 * product did the thing it claims:
 *
 *   - Did we show you something you would not have found yourself? (H1)
 *   - Would you actually pursue this? (the gap between interest and action)
 *
 * A "no" asks why, using the same reason vocabulary as a dismissal, so the two
 * signals are comparable.
 */

import { useState } from "react";

import { Button, Card } from "@/components/ui";
import { api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { DISMISS_REASONS } from "@/lib/format";

type Question = "would_not_have_found" | "would_pursue";

const OPTIONS: Record<Question, { value: string; label: string }[]> = {
  would_not_have_found: [
    { value: "YES", label: copy.validation.yes },
    { value: "PARTLY", label: copy.validation.partly },
    { value: "NO", label: copy.validation.no },
  ],
  would_pursue: [
    { value: "YES", label: copy.validation.yes },
    { value: "MAYBE", label: copy.validation.maybe },
    { value: "NO", label: copy.validation.no },
  ],
};

export function FeedbackPrompt({
  question,
  opportunityId,
}: {
  question: Question;
  opportunityId?: string;
}) {
  const [answer, setAnswer] = useState<string | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const prompt =
    question === "would_not_have_found"
      ? copy.validation.wouldNotHaveFound
      : copy.validation.wouldPursue;

  async function send(value: string, why?: string) {
    setAnswer(value);
    try {
      await api.feedback({
        question,
        answer: value,
        reason: why ?? null,
        opportunity_id: opportunityId ?? null,
      });
      if (value !== "NO" || why) setDone(true);
    } catch {
      // Feedback is additive. Failing to record it must not interrupt the user,
      // and telling them it failed helps nobody.
      setDone(true);
    }
  }

  if (done) {
    return (
      <Card className="mt-8 bg-paper-sunk">
        <p className="text-sm text-ink-muted">{copy.validation.thanks}</p>
      </Card>
    );
  }

  return (
    <Card className="mt-8 bg-paper-sunk">
      <p className="text-sm font-medium">{prompt}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {OPTIONS[question].map((option) => (
          <Button
            key={option.value}
            variant={answer === option.value ? "primary" : "secondary"}
            onClick={() => void send(option.value)}
          >
            {option.label}
          </Button>
        ))}
      </div>

      {answer === "NO" ? (
        <div className="mt-4 border-t border-rule pt-4">
          <p className="mb-2 text-sm">What was the main reason?</p>
          <div className="flex flex-wrap gap-1.5">
            {DISMISS_REASONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  setReason(option.value);
                  void send("NO", option.value);
                }}
                className={`rounded-full border px-3 py-1.5 text-xs ${
                  reason === option.value
                    ? "border-cobalt bg-cobalt-wash"
                    : "border-rule-strong hover:border-ink-faint"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </Card>
  );
}
