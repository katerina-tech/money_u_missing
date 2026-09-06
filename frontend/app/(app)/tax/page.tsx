"use client";

/**
 * KEEP: Tax & Rules.
 *
 * Every answer arrives with its sources, or does not arrive at all. The refusal
 * is not an error state - it is the correct output for a question the corpus
 * does not cover, and it is styled as an answer rather than as a failure.
 */

import { useEffect, useState } from "react";

import {
  Button,
  Card,
  Notice,
  Page,
  PageHeader,
  Section,
  Skeleton,
  TextInput,
  TrustBadge,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { titleCase } from "@/lib/format";
import type { LegalFact, TaxAnswer } from "@/lib/types";

const SUGGESTIONS = [
  "Do I need to register a Gewerbe for freelance consulting?",
  "What is the Kleinunternehmerregelung threshold?",
  "What must a Rechnung contain?",
  "How much can I earn while receiving Arbeitslosengeld?",
  "When must I submit the Fragebogen zur steuerlichen Erfassung?",
];

export default function TaxPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<TaxAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [facts, setFacts] = useState<LegalFact[] | null>(null);

  useEffect(() => {
    api.legalFacts().then(setFacts).catch(() => setFacts([]));
  }, []);

  async function ask(text: string) {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    setAnswer(null);
    try {
      setAnswer(await api.askTax(text));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.ragUnavailable);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Keep"
        title="Tax & Rules"
        lead="Source-backed information about earning additional income in Germany. Every answer cites the legislation it comes from. Questions we have no verified source for are declined rather than answered from memory."
      />

      <Notice tone="info">{copy.disclaimers.tax}</Notice>

      <Section>
        <form
          className="mt-6"
          onSubmit={(event) => {
            event.preventDefault();
            void ask(question);
          }}
        >
          <label htmlFor="tax-question" className="mb-2 block text-sm font-medium">
            Ask a question
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <TextInput
              id="tax-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="e.g. Do I need to register a Gewerbe?"
              className="flex-1"
            />
            <Button type="submit" disabled={busy || !question.trim()}>
              {busy ? "Searching sources…" : "Ask"}
            </Button>
          </div>
        </form>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => {
                setQuestion(suggestion);
                void ask(suggestion);
              }}
              className="rounded-full border border-rule-strong px-3 py-1.5 text-xs text-ink-muted hover:border-ink-faint hover:text-ink"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </Section>

      {error ? <Notice tone="warning">{error}</Notice> : null}

      {answer ? (
        <Section>
          <Card>
            {answer.answered ? (
              <>
                {answer.staleness_warnings.length > 0 ? (
                  <div className="mb-4">
                    <Notice tone="warning" title="Some of this needs re-checking">
                      <ul className="list-disc space-y-1 pl-4">
                        {answer.staleness_warnings.map((warning) => (
                          <li key={warning}>{warning}</li>
                        ))}
                      </ul>
                    </Notice>
                  </div>
                ) : null}

                <p className="whitespace-pre-line text-[15px] leading-relaxed">
                  {answer.answer}
                </p>

                <div className="mt-6 border-t border-rule pt-5">
                  <p className="eyebrow mb-3">Sources</p>
                  <ol className="space-y-4">
                    {answer.citations.map((citation, index) => (
                      <li key={`${citation.title}-${index}`}>
                        <p className="text-sm font-medium">
                          {citation.source_url ? (
                            <a
                              href={citation.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-cobalt underline underline-offset-4"
                            >
                              {citation.title}
                            </a>
                          ) : (
                            citation.title
                          )}
                        </p>
                        <p className="text-xs text-ink-faint">
                          {citation.source_name}
                          {citation.effective_year ? ` · ${citation.effective_year}` : ""}
                          {citation.retrieved_at
                            ? ` · retrieved ${new Date(citation.retrieved_at).toLocaleDateString("en-DE")}`
                            : ""}
                        </p>
                        <blockquote className="mt-2 border-l-2 border-rule-strong pl-3 text-sm text-ink-muted">
                          {citation.excerpt}
                        </blockquote>
                      </li>
                    ))}
                  </ol>
                </div>
              </>
            ) : (
              <>
                <p className="eyebrow mb-2">We are not going to answer this</p>
                <p className="text-[15px] leading-relaxed">{answer.refusal}</p>
                <p className="mt-4 text-sm text-ink-faint">
                  This is deliberate. Answering a regulatory question we cannot cite would give
                  you something that sounds authoritative and might be a year out of date.
                </p>
              </>
            )}

            {answer.questions_to_verify.length > 0 ? (
              <div className="mt-6 rounded-[4px] border border-rule bg-paper-sunk p-4">
                <p className="eyebrow mb-2">Questions to put to your Finanzamt or Steuerberater</p>
                <ul className="space-y-1.5">
                  {answer.questions_to_verify.map((item) => (
                    <li key={item} className="flex gap-2 text-sm">
                      <span aria-hidden="true" className="text-cobalt">
                        ?
                      </span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-xs text-ink-faint">
                  Specific questions rather than &ldquo;consult a professional&rdquo; — these
                  are what make the appointment short and useful.
                </p>
              </div>
            ) : null}
          </Card>
        </Section>
      ) : null}

      {/* --------------------------------------------- the fact registry */}
      <Section
        title="What we hold"
        description="Every rule and threshold in the system, with where it came from and when it was last checked. Entries we could not populate are listed too."
      >
        {facts === null ? (
          <Skeleton lines={4} />
        ) : (
          <div className="overflow-x-auto rounded-[--radius-card] border border-rule">
            <table className="w-full min-w-[42rem] text-left text-sm">
              <thead className="bg-paper-sunk">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-medium">
                    Rule
                  </th>
                  <th scope="col" className="px-4 py-2.5 font-medium">
                    Topic
                  </th>
                  <th scope="col" className="px-4 py-2.5 font-medium">
                    Status
                  </th>
                  <th scope="col" className="px-4 py-2.5 font-medium">
                    Source
                  </th>
                </tr>
              </thead>
              <tbody>
                {facts.map((fact) => (
                  <tr key={fact.id} className="border-t border-rule align-top">
                    <td className="px-4 py-3">
                      <p className="font-medium">{fact.title}</p>
                      <p className="mt-0.5 max-w-md text-xs text-ink-muted">{fact.summary}</p>
                    </td>
                    <td className="px-4 py-3 text-xs text-ink-muted">
                      {titleCase(fact.category)}
                    </td>
                    <td className="px-4 py-3">
                      <TrustBadge trust={fact.trust} size="xs" />
                    </td>
                    <td className="px-4 py-3 text-xs">
                      {fact.source_url ? (
                        <a
                          href={fact.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-cobalt underline underline-offset-4"
                        >
                          {fact.source_name}
                        </a>
                      ) : (
                        fact.source_name
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </Page>
  );
}
