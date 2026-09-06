import type { Metadata } from "next";
import Link from "next/link";

import { Logo } from "@/components/Logo";

export const metadata: Metadata = { title: "Privacy" };

const ROWS: [string, string, string, string][] = [
  [
    "Email address",
    "To identify your account and let you sign in",
    "Until you delete your account",
    "Delete account",
  ],
  [
    "Password",
    "To authenticate you",
    "Stored only as an Argon2id hash, never as text",
    "Delete account",
  ],
  [
    "CV file and extracted text",
    "To extract your skills and experience, once, with your explicit consent",
    "Until you delete it; not needed after you confirm your profile",
    "Settings → Delete my CV data",
  ],
  [
    "Profile (skills, experience, city, hours, goal)",
    "To match you against opportunities and to plan searches",
    "Until you delete your account",
    "Profile page, or delete account",
  ],
  [
    "Work status and administrative answers",
    "To decide which German administrative questions to raise",
    "Until you change or delete them",
    "Profile page",
  ],
  [
    "Saved opportunities, applications, recorded income",
    "To track your progress and to improve ranking",
    "Until you delete your account",
    "Delete account",
  ],
  [
    "Dismissal reasons",
    "To adjust how future opportunities are ranked for you",
    "Until you reset them",
    "Settings → Reset what it learned",
  ],
  [
    "Analytics events",
    "To measure whether the product works, using a fixed allowlist of properties",
    "Until you delete your account",
    "Delete account",
  ],
  [
    "Audit record of deletion",
    "To evidence that a deletion happened",
    "Kept, against a one-way hash only",
    "Not deletable, and not personal data on its own",
  ],
];

export default function PrivacyPage() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-rule">
        <div className="mx-auto max-w-4xl px-5 py-4 sm:px-8">
          <Logo />
        </div>
      </header>

      <main id="main" className="mx-auto max-w-4xl px-5 py-12 sm:px-8">
        <p className="eyebrow mb-2">Privacy</p>
        <h1 className="text-4xl">What we hold, why, and how to remove it</h1>
        <p className="mt-4 text-[15px] leading-relaxed text-ink-muted">
          This product processes a CV and a professional profile, which is sensitive
          information. The short version: we collect what matching needs and nothing else, we
          never use your CV to train a model, and every deletion in the table below is a button
          that actually deletes rows.
        </p>

        <section className="mt-10">
          <h2 className="text-2xl">Principles</h2>
          <ul className="mt-4 space-y-3 text-[15px] text-ink-muted">
            <li>
              <strong className="text-ink">Data minimisation.</strong> The search planner
              receives your skills, role, languages, location and availability — not your name,
              not your email, not your portfolio link. It does not need them.
            </li>
            <li>
              <strong className="text-ink">Purpose limitation.</strong> Your CV is processed for
              one purpose: extracting skills and experience for you to review. It is not used
              for training, not shared, and not analysed for anything else.
            </li>
            <li>
              <strong className="text-ink">Nothing sensitive is inferred.</strong> Work status,
              benefit receipt and tax registration are asked explicitly and default to unknown.
              The extraction schema has no field for them, so a model cannot populate them even
              if it tried.
            </li>
            <li>
              <strong className="text-ink">Analytics cannot leak.</strong> Every analytics event
              has a fixed allowlist of property names and types. Anything else is dropped before
              it is written. Income is recorded as a bucket, never as an amount.
            </li>
            <li>
              <strong className="text-ink">Logs do not contain your documents.</strong> CV text
              and tax questions are logged as a length and a truncated hash — not even a
              preview, because the first lines of a CV are the identifying ones.
            </li>
            <li>
              <strong className="text-ink">No dark patterns.</strong> Deleting your account is
              one click and a confirmation, in the same place as everything else.
            </li>
          </ul>
        </section>

        <section className="mt-10">
          <h2 className="text-2xl">What we hold</h2>
          <div className="mt-4 overflow-x-auto rounded-[--radius-card] border border-rule">
            <table className="w-full min-w-[46rem] text-left text-sm">
              <thead className="bg-paper-sunk">
                <tr>
                  {["Data", "Purpose", "Retention", "How to remove it"].map((heading) => (
                    <th key={heading} scope="col" className="px-4 py-2.5 font-medium">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROWS.map((row) => (
                  <tr key={row[0]} className="border-t border-rule align-top">
                    <td className="px-4 py-3 font-medium">{row[0]}</td>
                    <td className="px-4 py-3 text-ink-muted">{row[1]}</td>
                    <td className="px-4 py-3 text-ink-muted">{row[2]}</td>
                    <td className="px-4 py-3 text-ink-muted">{row[3]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mt-10">
          <h2 className="text-2xl">Third parties</h2>
          <p className="mt-3 text-[15px] leading-relaxed text-ink-muted">
            When a language model is configured, the text sent to it is: your CV (once, during
            extraction), a summary of your skills and availability (for search planning), the
            content of pages we retrieved, and your tax questions. Your email address, name and
            contact details are never sent. When no model is configured — which is how the demo
            runs — nothing leaves the server at all.
          </p>
          <p className="mt-3 text-[15px] leading-relaxed text-ink-muted">
            When live web search is configured, the queries sent to the search provider are
            generated from your professional profile. They contain skills and role terms, not
            your identity.
          </p>
        </section>

        <section className="mt-10">
          <h2 className="text-2xl">Where your data lives</h2>
          <p className="mt-3 text-[15px] leading-relaxed text-ink-muted">
            The product is built for the EU market and should be deployed with an EU-region
            database. The repository documents that recommendation, and the deployment
            configuration makes the region an explicit choice rather than a default. Ask us
            which region a given deployment uses; a product about German income that stored
            German CVs outside the EU without saying so would not be worth trusting.
          </p>
        </section>

        <section className="mt-10">
          <h2 className="text-2xl">Your rights</h2>
          <p className="mt-3 text-[15px] leading-relaxed text-ink-muted">
            Access, rectification and erasure are all in the product rather than behind an email
            address: <strong>Settings → Download everything we hold</strong> returns your
            complete data as JSON, the profile page is fully editable, and{" "}
            <strong>Delete my account</strong> removes every row attached to you.
          </p>
        </section>

        <p className="mt-12 text-sm">
          <Link href="/" className="text-cobalt underline underline-offset-4">
            ← Back
          </Link>
        </p>
      </main>
    </div>
  );
}
