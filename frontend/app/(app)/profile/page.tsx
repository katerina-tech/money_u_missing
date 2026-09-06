"use client";

import { useEffect, useState } from "react";

import { ProfileForm } from "@/components/ProfileForm";
import { Card, Notice, Page, PageHeader, ProgressBar, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";
import type { Profile } from "@/lib/types";

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .profile()
      .then(setProfile)
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : copy.errors.generic),
      );
  }, []);

  async function save(updated: Profile) {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const saved = await api.saveProfile(updated);
      setProfile(saved);
      // Saving alone does not re-confirm. Re-confirming is an explicit act, so
      // an edit cannot silently re-authorise discovery on changed data.
      if (!saved.confirmed) {
        await api.confirmProfile().then(setProfile).catch(() => undefined);
      }
      setMessage("Saved.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
    } finally {
      setSaving(false);
    }
  }

  if (error && !profile) {
    return (
      <Page>
        <Notice tone="danger">{error}</Notice>
      </Page>
    );
  }
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
        eyebrow="Profile"
        title="Your profile"
        lead="Everything the matching engine uses. Every field is editable, and nothing is inferred behind your back."
      />

      <Card className="mb-6">
        <ProgressBar
          ratio={profile.completeness}
          label="Profile completeness"
          explainer="Weighted by what actually changes your ranking — skills, availability and your goal matter far more than a portfolio link."
        />
      </Card>

      {message ? (
        <div className="mb-6">
          <Notice tone="info">{message}</Notice>
        </div>
      ) : null}
      {error ? (
        <div className="mb-6">
          <Notice tone="warning">{error}</Notice>
        </div>
      ) : null}

      <ProfileForm initial={profile} onSave={save} saving={saving} />
    </Page>
  );
}
