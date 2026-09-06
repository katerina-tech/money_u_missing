"use client";

/**
 * Onboarding.
 *
 * Three ways in - upload, paste, or type - and one thing they all share: what
 * comes back is a *draft* you review. The review step is not a formality; the
 * backend will refuse to run discovery until a human has confirmed the profile,
 * and the copy says so rather than implying the step is optional politeness.
 *
 * When extraction is unavailable the flow does not fail. It falls through to
 * manual entry with an honest explanation, because "we could not read your CV"
 * is a reason to offer a form, not an error page.
 */

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ProfileForm } from "@/components/ProfileForm";
import { Button, Card, Notice, Page, PageHeader, Skeleton, TextArea } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import type { Profile } from "@/lib/types";

type Step = "choose" | "paste" | "review";
type Method = "upload" | "paste" | "manual";

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("choose");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [notFound, setNotFound] = useState<string[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [pasted, setPasted] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inferredCount, setInferredCount] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.profile().then(setProfile).catch(() => undefined);
  }, []);

  async function handleUpload(file: File) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.uploadCv(file);
      setProfile(result.draft);
      setNotFound(result.not_found);
      setNotes(result.extraction_notes);
      setInferredCount(result.inferred_skill_count);
      setStep("review");
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? `${caught.message} You can paste your CV as text, or fill in the form yourself.`
          : copy.errors.generic,
      );
    } finally {
      setBusy(false);
    }
  }

  async function handlePaste() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.pasteCv(pasted);
      setProfile(result.draft);
      setNotFound(result.not_found);
      setNotes(result.extraction_notes);
      setInferredCount(result.inferred_skill_count);
      setStep("review");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
    } finally {
      setBusy(false);
    }
  }

  function startManual() {
    setNotFound([]);
    setNotes([]);
    setInferredCount(0);
    setStep("review");
  }

  async function confirm(updated: Profile) {
    setBusy(true);
    setError(null);
    try {
      await api.saveProfile(updated);
      await api.confirmProfile();
      await api.refreshMoneyMap().catch(() => undefined);
      router.push("/dashboard");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
      setBusy(false);
    }
  }

  // ------------------------------------------------------------- choose
  if (step === "choose") {
    return (
      <Page>
        <PageHeader
          eyebrow="Step 1 of 2"
          title="Tell us about your work"
          lead="However you prefer. Whatever we extract, you review it before anything uses it — that is a hard rule, not a courtesy."
        />

        {error ? (
          <div className="mb-6">
            <Notice tone="warning">{error}</Notice>
          </div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-3">
          <Card>
            <h2 className="text-lg font-semibold">Upload a CV</h2>
            <p className="mt-2 text-sm text-ink-muted">
              PDF or plain text, up to 5 MB. We extract your skills and experience, show you
              what we found, and you correct it.
            </p>
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
              className="sr-only"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void handleUpload(file);
              }}
            />
            <Button
              className="mt-4"
              onClick={() => fileInput.current?.click()}
              disabled={busy}
              full
            >
              {busy ? "Reading…" : "Choose a file"}
            </Button>
            <p className="mt-3 text-xs text-ink-faint">
              Your CV is never used to train any model, and you can delete it from settings at
              any time.
            </p>
          </Card>

          <Card>
            <h2 className="text-lg font-semibold">Paste your profile</h2>
            <p className="mt-2 text-sm text-ink-muted">
              Paste a CV or a LinkedIn-style summary. No file leaves your machine.
            </p>
            <Button
              variant="secondary"
              className="mt-4"
              onClick={() => setStep("paste")}
              full
            >
              Paste text
            </Button>
          </Card>

          <Card>
            <h2 className="text-lg font-semibold">Type it in</h2>
            <p className="mt-2 text-sm text-ink-muted">
              Five fields is enough to get a useful first Money Map: skills, experience, hours
              and your goal.
            </p>
            <Button variant="secondary" className="mt-4" onClick={startManual} full>
              Enter manually
            </Button>
          </Card>
        </div>
      </Page>
    );
  }

  // -------------------------------------------------------------- paste
  if (step === "paste") {
    return (
      <Page>
        <PageHeader
          eyebrow="Step 1 of 2"
          title="Paste your profile"
          lead="A CV, a LinkedIn summary, or just a description of what you do."
        />
        <Card>
          <TextArea
            value={pasted}
            onChange={(event) => setPasted(event.target.value)}
            className="min-h-64"
            aria-label="Your CV or profile text"
            placeholder="Senior Data Engineer, Berlin. Eight years building data platforms…"
          />
          {error ? (
            <div className="mt-4">
              <Notice tone="warning">{error}</Notice>
            </div>
          ) : null}
          <div className="mt-4 flex gap-2">
            <Button onClick={handlePaste} disabled={busy || pasted.trim().length < 40}>
              {busy ? "Reading…" : "Continue"}
            </Button>
            <Button variant="secondary" onClick={() => setStep("choose")}>
              Back
            </Button>
          </div>
          <p className="mt-3 text-xs text-ink-faint">
            By continuing you agree to this text being processed to extract your skills and
            experience. It is not used to train any model.
          </p>
        </Card>
      </Page>
    );
  }

  // ------------------------------------------------------------- review
  if (!profile) {
    return (
      <Page>
        <Skeleton lines={8} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Step 2 of 2"
        title="Check what we have"
        lead="Nothing here is used until you confirm it. Correct anything that is wrong — especially your available hours and your income goal, which change the ranking most."
      />

      {inferredCount > 0 ? (
        <div className="mb-4">
          <Notice tone="warning" title={`${inferredCount} skill${inferredCount === 1 ? "" : "s"} inferred`}>
            We inferred these from context rather than reading them directly. They count at
            reduced weight until you tick them, because we will not claim a qualification you
            have not stood behind.
          </Notice>
        </div>
      ) : null}

      {notFound.length > 0 ? (
        <div className="mb-4">
          <Notice tone="info" title="What we could not find">
            <ul className="list-disc space-y-1 pl-4">
              {notFound.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Notice>
        </div>
      ) : null}

      {notes.length > 0 ? (
        <div className="mb-6">
          <Notice tone="info" title="Notes from reading your document">
            <ul className="space-y-2">
              {notes.map((note) => (
                <li key={note} className="whitespace-pre-line">
                  {note}
                </li>
              ))}
            </ul>
          </Notice>
        </div>
      ) : null}

      {error ? (
        <div className="mb-6">
          <Notice tone="danger">{error}</Notice>
        </div>
      ) : null}

      <ProfileForm
        initial={profile}
        onSave={confirm}
        saving={busy}
        submitLabel="Confirm and build my Money Map"
      />
    </Page>
  );
}
