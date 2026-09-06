"use client";

/**
 * Settings: your data, and what the ranking has learned.
 *
 * Both of these are consequences of promises made elsewhere. "You can delete
 * your CV" and "we do not train on your data" are only meaningful if there is a
 * button; "the ranking learns from your dismissals" is only acceptable if you
 * can read what it learned and clear it.
 */

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, Card, Notice, Page, PageHeader, Section, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import type { Capabilities } from "@/lib/types";

interface Preferences {
  signals: number;
  minimum_signals: number;
  active: boolean;
  statements: string[];
  reasons: Record<string, number>;
}

interface CvRecord {
  id: string;
  filename: string;
  uploaded_at: string;
  deleted_at: string | null;
  file_present: boolean;
  extracted_text_present: boolean;
}

export default function SettingsPage() {
  const router = useRouter();
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [documents, setDocuments] = useState<CvRecord[] | null>(null);
  const [consents, setConsents] = useState<
    { purpose: string; statement: string; granted_at: string; withdrawn_at: string | null }[] | null
  >(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  function reload() {
    api.preferences().then((value) => setPreferences(value as unknown as Preferences)).catch(() => undefined);
    api.listCv().then(setDocuments).catch(() => setDocuments([]));
    api.consents().then(setConsents).catch(() => setConsents([]));
    api.capabilities().then(setCapabilities).catch(() => undefined);
  }

  useEffect(reload, []);

  return (
    <Page>
      <PageHeader
        eyebrow="Settings"
        title="Your data and your ranking"
        lead="What we hold, what the ranking has learned from you, and how to remove both."
      />

      {message ? (
        <div className="mb-6">
          <Notice tone="info">{message}</Notice>
        </div>
      ) : null}

      {/* ------------------------------------------------- learned ranking */}
      <Section
        title="What your ranking has learned"
        description="Derived only from the reasons you gave when dismissing opportunities. No model is trained on your data."
      >
        {preferences === null ? (
          <Skeleton lines={3} />
        ) : (
          <Card>
            <ul className="space-y-2">
              {preferences.statements.map((statement) => (
                <li key={statement} className="text-sm">
                  {statement}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-ink-faint">
              {preferences.signals} dismissal
              {preferences.signals === 1 ? "" : "s"} with a reason. Nothing is adjusted below{" "}
              {preferences.minimum_signals}, because fewer than that is noise rather than a
              preference.
            </p>
            {preferences.active ? (
              <Button
                variant="secondary"
                className="mt-4"
                onClick={async () => {
                  await api.resetPreferences().catch(() => undefined);
                  setMessage("Your ranking adjustments have been cleared.");
                  reload();
                }}
              >
                Reset what it learned
              </Button>
            ) : null}
          </Card>
        )}
      </Section>

      {/* ---------------------------------------------------------- CV data */}
      <Section
        title="Uploaded CVs"
        description="Deleting removes both the file and the text we extracted from it. Your profile stays as you confirmed it."
      >
        {documents === null ? (
          <Skeleton lines={2} />
        ) : documents.length === 0 ? (
          <p className="text-sm text-ink-muted">No CV has been uploaded from this account.</p>
        ) : (
          <Card>
            <ul className="space-y-2">
              {documents.map((document) => (
                <li
                  key={document.id}
                  className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-2 text-sm last:border-0"
                >
                  <span>{document.filename}</span>
                  <span className="text-xs text-ink-faint">
                    {document.deleted_at
                      ? "Deleted"
                      : `${document.file_present ? "file stored" : "file removed"} · ${
                          document.extracted_text_present ? "text stored" : "text removed"
                        }`}
                  </span>
                </li>
              ))}
            </ul>
            <Button
              variant="secondary"
              className="mt-4"
              onClick={async () => {
                await api.deleteCv().catch(() => undefined);
                setMessage("Your CV files and extracted text have been deleted.");
                reload();
              }}
            >
              Delete my CV data
            </Button>
          </Card>
        )}
      </Section>

      {/* --------------------------------------------------------- consents */}
      <Section title="What you agreed to">
        {consents === null ? (
          <Skeleton lines={2} />
        ) : (
          <Card>
            <ul className="space-y-4">
              {consents.map((consent) => (
                <li key={consent.purpose}>
                  <p className="text-sm font-medium">{consent.purpose.replace(/_/g, " ")}</p>
                  <p className="mt-1 text-sm text-ink-muted">{consent.statement}</p>
                  <p className="mt-1 text-xs text-ink-faint">
                    Given {new Date(consent.granted_at).toLocaleDateString("en-DE")}
                    {consent.withdrawn_at ? " · withdrawn" : ""}
                  </p>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </Section>

      {/* ------------------------------------------------------- export etc */}
      <Section title="Your data">
        <Card>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="secondary"
              onClick={async () => {
                const data = await api.exportData();
                const blob = new Blob([JSON.stringify(data, null, 2)], {
                  type: "application/json",
                });
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement("a");
                anchor.href = url;
                anchor.download = "money-youre-missing-export.json";
                anchor.click();
                URL.revokeObjectURL(url);
              }}
            >
              Download everything we hold
            </Button>
            {confirmDelete ? (
              <>
                <Button
                  variant="danger"
                  onClick={async () => {
                    try {
                      await api.deleteAccount();
                      router.push("/");
                    } catch (caught) {
                      setMessage(
                        caught instanceof ApiError ? caught.message : copy.errors.generic,
                      );
                    }
                  }}
                >
                  Yes, delete my account permanently
                </Button>
                <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </Button>
              </>
            ) : (
              <Button variant="danger" onClick={() => setConfirmDelete(true)}>
                Delete my account
              </Button>
            )}
          </div>
          <p className="mt-3 text-xs text-ink-faint">
            Deleting removes your profile, skills, saved opportunities, applications, recorded
            income, goals and analytics. A record that a deletion occurred is kept against a
            one-way hash, which is not personal data on its own.
          </p>
        </Card>
      </Section>

      {/* ---------------------------------------------------- capabilities */}
      {capabilities ? (
        <Section
          title="What this deployment can do"
          description="Shown so you know which parts are running fully and which are degraded."
        >
          <Card>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              {[
                ["Language model", capabilities.llm_available ? capabilities.llm_provider : "not configured"],
                ["Live web search", capabilities.live_search_available ? capabilities.search_provider : "not configured"],
                ["Retrieval", capabilities.retrieval_mode],
                ["Knowledge corpus", `${capabilities.knowledge_documents} documents, ${capabilities.knowledge_chunks} passages`],
                ["Legal facts verified", `${capabilities.legal_facts_verified} of ${capabilities.legal_facts_total}`],
                ["Database", capabilities.database],
              ].map(([term, value]) => (
                <div key={String(term)} className="flex justify-between gap-4 border-b border-rule pb-2">
                  <dt className="text-ink-muted">{term}</dt>
                  <dd className="text-right font-medium">{value}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </Section>
      ) : null}
    </Page>
  );
}
