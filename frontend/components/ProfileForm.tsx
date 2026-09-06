"use client";

/**
 * The profile form.
 *
 * Shared between onboarding review and the profile page, so the fields a user
 * confirms are literally the same component as the fields they later edit -
 * there is no path where one has something the other does not.
 *
 * Two properties matter here:
 *
 * - **Every field is editable**, including everything extraction produced.
 * - **Inferred skills are visibly inferred** and unconfirmed until the user
 *   ticks them. The form says what that costs them in matching, so the choice
 *   is informed rather than decorative.
 */

import { useState } from "react";

import { Button, Card, Field, Notice, Select, TextArea, TextInput } from "@/components/ui";
import { formatMinor, parseMoneyInput } from "@/lib/format";
import type { Profile, Skill } from "@/lib/types";

const WORK_STATUS = [
  ["UNKNOWN", "Prefer not to say"],
  ["EMPLOYEE", "Employed"],
  ["SELF_EMPLOYED", "Self-employed"],
  ["EMPLOYEE_AND_SELF_EMPLOYED", "Employed and self-employed"],
  ["STUDENT", "Student"],
  ["JOB_SEEKING", "Looking for work"],
  ["PARENTAL_LEAVE", "Parental leave"],
  ["OTHER", "Something else"],
] as const;

const REMOTE = [
  ["UNKNOWN", "No preference"],
  ["REMOTE", "Remote"],
  ["HYBRID", "Hybrid"],
  ["ONSITE", "Onsite"],
] as const;

const SCHEDULE = [
  ["UNKNOWN", "No preference"],
  ["EVENINGS", "Evenings"],
  ["WEEKENDS", "Weekends"],
  ["WEEKDAY_HOURS", "Weekday hours"],
  ["FLEXIBLE", "Flexible"],
] as const;

const TRISTATE = [
  ["UNKNOWN", "I don't know"],
  ["YES", "Yes"],
  ["NO", "No"],
] as const;

const BENEFITS = [
  ["UNKNOWN", "Not answered"],
  ["NO", "No"],
  ["YES", "Yes"],
  ["PREFER_NOT_TO_SAY", "Prefer not to say"],
] as const;

const LEVELS = ["UNKNOWN", "BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT"] as const;

export function ProfileForm({
  initial,
  onSave,
  saving,
  submitLabel = "Save profile",
}: {
  initial: Profile;
  onSave: (profile: Profile) => void;
  saving?: boolean;
  submitLabel?: string;
}) {
  const [profile, setProfile] = useState<Profile>(initial);
  const [newSkill, setNewSkill] = useState("");

  function patch(update: Partial<Profile>) {
    setProfile((current) => ({ ...current, ...update }));
  }

  function patchSkill(index: number, update: Partial<Skill>) {
    setProfile((current) => ({
      ...current,
      skills: current.skills.map((skill, position) =>
        position === index ? { ...skill, ...update } : skill,
      ),
    }));
  }

  const inferred = profile.skills.filter((skill) => skill.evidence === "INFERRED");
  const unconfirmedInferred = inferred.filter((skill) => !skill.confirmed);

  return (
    <div className="space-y-6">
      {/* ------------------------------------------------------- general */}
      <Card>
        <h2 className="mb-4 text-lg font-semibold">About you</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" htmlFor="p-name" hint="Used only to greet you.">
            <TextInput
              id="p-name"
              value={profile.display_name ?? ""}
              onChange={(event) => patch({ display_name: event.target.value || null })}
            />
          </Field>
          <Field label="Current role" htmlFor="p-role">
            <TextInput
              id="p-role"
              value={profile.current_role ?? ""}
              onChange={(event) => patch({ current_role: event.target.value || null })}
            />
          </Field>
          <Field label="City" htmlFor="p-city">
            <TextInput
              id="p-city"
              value={profile.city ?? ""}
              onChange={(event) => patch({ city: event.target.value || null })}
            />
          </Field>
          <Field label="Federal state" htmlFor="p-state">
            <TextInput
              id="p-state"
              value={profile.federal_state ?? ""}
              onChange={(event) => patch({ federal_state: event.target.value || null })}
            />
          </Field>
          <Field label="Years of experience" htmlFor="p-years">
            <TextInput
              id="p-years"
              inputMode="decimal"
              value={profile.years_experience ?? ""}
              onChange={(event) =>
                patch({
                  years_experience: event.target.value
                    ? Number.parseFloat(event.target.value)
                    : null,
                })
              }
            />
          </Field>
          <Field label="Industries" htmlFor="p-industries" hint="Comma separated.">
            <TextInput
              id="p-industries"
              value={profile.industries.join(", ")}
              onChange={(event) =>
                patch({
                  industries: event.target.value
                    .split(",")
                    .map((value) => value.trim())
                    .filter(Boolean),
                })
              }
            />
          </Field>
        </div>
      </Card>

      {/* -------------------------------------------------------- skills */}
      <Card>
        <h2 className="mb-1 text-lg font-semibold">Skills</h2>
        <p className="mb-4 text-sm text-ink-muted">
          These drive matching more than anything else. Anything marked{" "}
          <em>inferred</em> was implied by your CV rather than stated in it — it counts at
          reduced weight until you confirm it.
        </p>

        {unconfirmedInferred.length > 0 ? (
          <div className="mb-4">
            <Notice tone="warning">
              {unconfirmedInferred.length} skill
              {unconfirmedInferred.length === 1 ? " was" : "s were"} inferred and not yet
              confirmed. We will not claim them on your behalf.
            </Notice>
          </div>
        ) : null}

        <ul className="space-y-2">
          {profile.skills.map((skill, index) => (
            <li
              key={skill.key || skill.name}
              className="flex flex-wrap items-center gap-2 border-b border-rule pb-2 last:border-0"
            >
              <span className="min-w-40 flex-1 text-sm font-medium">{skill.name}</span>

              <Select
                aria-label={`${skill.name} level`}
                value={skill.level}
                onChange={(event) =>
                  patchSkill(index, { level: event.target.value as Skill["level"] })
                }
                className="w-40"
              >
                {LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level === "UNKNOWN" ? "Level not set" : level.toLowerCase()}
                  </option>
                ))}
              </Select>

              {skill.evidence === "INFERRED" ? (
                <label className="flex items-center gap-1.5 text-xs">
                  <input
                    type="checkbox"
                    checked={skill.confirmed}
                    onChange={(event) => patchSkill(index, { confirmed: event.target.checked })}
                    className="accent-cobalt"
                  />
                  <span className={skill.confirmed ? "" : "text-unverified"}>
                    {skill.confirmed ? "confirmed" : "inferred — confirm?"}
                  </span>
                </label>
              ) : (
                <span className="text-xs text-ink-faint">{skill.evidence.toLowerCase()}</span>
              )}

              <button
                type="button"
                onClick={() =>
                  patch({ skills: profile.skills.filter((_, position) => position !== index) })
                }
                className="text-xs text-ink-faint underline underline-offset-4 hover:text-danger"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>

        <div className="mt-4 flex gap-2">
          <TextInput
            aria-label="Add a skill"
            value={newSkill}
            onChange={(event) => setNewSkill(event.target.value)}
            placeholder="Add a skill"
            className="max-w-xs"
          />
          <Button
            variant="secondary"
            onClick={() => {
              const name = newSkill.trim();
              if (!name) return;
              patch({
                skills: [
                  ...profile.skills,
                  {
                    name,
                    key: name.toLowerCase(),
                    level: "UNKNOWN",
                    years: null,
                    evidence: "USER_STATED",
                    related: [],
                    confirmed: true,
                  },
                ],
              });
              setNewSkill("");
            }}
          >
            Add
          </Button>
        </div>
      </Card>

      {/* -------------------------------------------------------- income */}
      <Card>
        <h2 className="mb-4 text-lg font-semibold">Income</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Additional income goal (EUR per month)"
            htmlFor="p-goal"
            hint="What you are aiming for on top of what you already earn."
          >
            <TextInput
              id="p-goal"
              inputMode="decimal"
              value={
                profile.desired_additional_monthly_minor === null
                  ? ""
                  : String(profile.desired_additional_monthly_minor / 100)
              }
              onChange={(event) =>
                patch({ desired_additional_monthly_minor: parseMoneyInput(event.target.value) })
              }
            />
          </Field>
          <Field
            label="Minimum worth pursuing (EUR)"
            htmlFor="p-minimum"
            hint="Below this, an opportunity is not worth your time."
          >
            <TextInput
              id="p-minimum"
              inputMode="decimal"
              value={
                profile.minimum_worthwhile_minor === null
                  ? ""
                  : String(profile.minimum_worthwhile_minor / 100)
              }
              onChange={(event) =>
                patch({ minimum_worthwhile_minor: parseMoneyInput(event.target.value) })
              }
            />
          </Field>
          <Field label="Current main income" htmlFor="p-primary">
            <TextInput
              id="p-primary"
              value={profile.current_primary_income_type ?? ""}
              onChange={(event) =>
                patch({ current_primary_income_type: event.target.value || null })
              }
              placeholder="e.g. full-time employment"
            />
          </Field>
          <Field label="Prefer recurring or one-off?" htmlFor="p-preference">
            <Select
              id="p-preference"
              value={profile.income_preference}
              onChange={(event) =>
                patch({ income_preference: event.target.value as Profile["income_preference"] })
              }
            >
              <option value="NO_PREFERENCE">No preference</option>
              <option value="RECURRING">Recurring</option>
              <option value="ONE_TIME">One-off</option>
            </Select>
          </Field>
        </div>
      </Card>

      {/* ---------------------------------------------------------- time */}
      <Card>
        <h2 className="mb-4 text-lg font-semibold">Time and working style</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Hours available per week"
            htmlFor="p-hours"
            hint="Be realistic. This is what stops us recommending things you cannot fit in."
          >
            <TextInput
              id="p-hours"
              inputMode="decimal"
              value={profile.hours_per_week ?? ""}
              onChange={(event) =>
                patch({
                  hours_per_week: event.target.value
                    ? Number.parseFloat(event.target.value)
                    : null,
                })
              }
            />
          </Field>
          <Field label="Preferred schedule" htmlFor="p-schedule">
            <Select
              id="p-schedule"
              value={profile.schedule_preference}
              onChange={(event) =>
                patch({
                  schedule_preference: event.target.value as Profile["schedule_preference"],
                })
              }
            >
              {SCHEDULE.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Remote, hybrid or onsite" htmlFor="p-remote">
            <Select
              id="p-remote"
              value={profile.remote_preference}
              onChange={(event) =>
                patch({ remote_preference: event.target.value as Profile["remote_preference"] })
              }
            >
              {REMOTE.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Willing to travel" htmlFor="p-travel">
            <Select
              id="p-travel"
              value={profile.willing_to_travel}
              onChange={(event) =>
                patch({ willing_to_travel: event.target.value as Profile["willing_to_travel"] })
              }
            >
              {TRISTATE.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>

      {/* -------------------------------------------- work status & admin */}
      <Card>
        <h2 className="mb-1 text-lg font-semibold">Work status and admin</h2>
        <p className="mb-4 text-sm text-ink-muted">
          Optional, and never inferred from anything else. These change which questions the
          Germany check raises. &ldquo;I don&rsquo;t know&rdquo; is a real answer and produces a
          question rather than an assumption.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Work status" htmlFor="p-status">
            <Select
              id="p-status"
              value={profile.work_status}
              onChange={(event) =>
                patch({ work_status: event.target.value as Profile["work_status"] })
              }
            >
              {WORK_STATUS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Do you have a Gewerbe?" htmlFor="p-gewerbe">
            <Select
              id="p-gewerbe"
              value={profile.has_gewerbe}
              onChange={(event) =>
                patch({ has_gewerbe: event.target.value as Profile["has_gewerbe"] })
              }
            >
              {TRISTATE.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Registered for tax as a freelancer?" htmlFor="p-freelance">
            <Select
              id="p-freelance"
              value={profile.has_freelance_tax_registration}
              onChange={(event) =>
                patch({
                  has_freelance_tax_registration: event.target
                    .value as Profile["has_freelance_tax_registration"],
                })
              }
            >
              {TRISTATE.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <Field
            label="Do you know your employer's Nebentätigkeit rules?"
            htmlFor="p-employer"
          >
            <Select
              id="p-employer"
              value={profile.knows_employer_rules}
              onChange={(event) =>
                patch({
                  knows_employer_rules: event.target.value as Profile["knows_employer_rules"],
                })
              }
            >
              {TRISTATE.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <Field
            label="Do you receive employment-related benefits?"
            htmlFor="p-benefits"
            hint="Only asked so we can show the reporting rules that apply. Never inferred, and you can decline."
          >
            <Select
              id="p-benefits"
              value={profile.receives_employment_benefits}
              onChange={(event) =>
                patch({
                  receives_employment_benefits: event.target
                    .value as Profile["receives_employment_benefits"],
                })
              }
            >
              {BENEFITS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => onSave(profile)} disabled={saving}>
          {saving ? "Saving…" : submitLabel}
        </Button>
        {profile.desired_additional_monthly_minor !== null ? (
          <p className="text-sm text-ink-faint">
            Goal: {formatMinor(profile.desired_additional_monthly_minor)}/month
          </p>
        ) : null}
      </div>
    </div>
  );
}
