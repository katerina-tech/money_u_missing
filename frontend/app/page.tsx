import Link from "next/link";

import { Logo } from "@/components/Logo";
import { copy } from "@/lib/copy";

import { DemoLaunch } from "./_landing/DemoLaunch";
import { MoneyMapPreview } from "./_landing/MoneyMapPreview";

const DIFFERENTIATORS = [
  { title: "Real sources", body: "Every opportunity comes from a page we retrieved and can link you to." },
  { title: "Personal match", body: "Scored in code against your skills, hours, languages and goal." },
  { title: "Eligibility", body: "Stated requirements, checked — and unknowns named as unknowns." },
  { title: "Time", body: "What it asks of you per week, when the source says." },
  { title: "Compensation", body: "Exactly as published. Never estimated, never annualised." },
  { title: "Germany check", body: "The administrative questions this kind of work raises here." },
  { title: "Next action", body: "One recommendation at a time, with a checklist." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-rule">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <Logo />
          <nav className="flex items-center gap-5 text-sm">
            <Link href="/about" className="hidden text-ink-muted hover:text-ink sm:inline">
              About
            </Link>
            <Link href="/privacy" className="hidden text-ink-muted hover:text-ink sm:inline">
              Privacy
            </Link>
            <Link href="/login" className="text-ink-muted hover:text-ink">
              Sign in
            </Link>
          </nav>
        </div>
      </header>

      <main id="main">
        {/* ------------------------------------------------------- hero */}
        <section className="border-b border-rule">
          <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
            <div className="grid gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
              <div className="rise">
                <p className="eyebrow mb-5">Personal opportunity-to-income engine · Germany</p>
                <h1 className="text-[2.75rem] leading-[1.05] sm:text-6xl">
                  Money
                  <br />
                  You&rsquo;re Missing
                </h1>
                <p
                  className="mt-6 text-xl text-ink-muted sm:text-2xl"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  One profile.
                  <br />
                  Multiple ways to earn.
                </p>
                <p className="mt-6 max-w-xl text-[15px] leading-relaxed text-ink-muted">
                  {copy.landing.heroLead}
                </p>

                {/* The name is ambiguous and the ambiguity costs us the wrong
                    visitors. Saying what this is not, in the first viewport. */}
                <p className="mt-6 max-w-xl border-l-2 border-rule-strong pl-4 text-sm text-ink-faint">
                  {copy.landing.clarification}
                </p>

                <div className="mt-9 flex flex-wrap items-center gap-3">
                  <DemoLaunch />
                  <Link
                    href="#how-it-works"
                    className="inline-flex items-center justify-center rounded-[4px] border border-rule-strong bg-paper-raised px-5 py-3 text-sm font-medium hover:border-ink-faint"
                  >
                    {copy.landing.secondaryCta}
                  </Link>
                </div>
              </div>

              <div className="rise" style={{ animationDelay: "120ms" }}>
                <MoneyMapPreview />
              </div>
            </div>
          </div>
        </section>

        {/* --------------------------------------------------- category strip */}
        <section className="border-b border-rule bg-paper-sunk">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-3 px-5 py-5 sm:px-8">
            <span className="eyebrow">Categories we search</span>
            {copy.landing.categories.map((category) => (
              <span key={category} className="text-sm text-ink-muted">
                {category}
              </span>
            ))}
          </div>
        </section>

        {/* -------------------------------------------------------- problem */}
        <section className="border-b border-rule">
          <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-20">
            <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr]">
              <h2 className="max-w-md text-3xl sm:text-4xl">{copy.landing.problemHeading}</h2>
              <div className="max-w-xl space-y-4 text-[15px] leading-relaxed text-ink-muted">
                <p>{copy.landing.problemBody}</p>
                <p className="text-ink">{copy.landing.problemClose}</p>
              </div>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------- differentiation */}
        <section className="border-b border-rule">
          <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-20">
            <h2 className="mb-3 text-3xl sm:text-4xl">{copy.landing.differentiationHeading}</h2>
            <p className="mb-10 max-w-2xl text-[15px] text-ink-muted">
              An idea generator can produce a hundred plausible sentences about earning money.
              None of them is an opportunity you can apply to. Everything below is a property of
              a real listing, or an honest statement that the listing does not say.
            </p>
            <ol className="grid gap-px overflow-hidden rounded-[--radius-card] border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-4">
              {DIFFERENTIATORS.map((item, index) => (
                <li key={item.title} className="bg-paper-raised p-5">
                  <span className="tnum text-xs text-ink-faint">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3 className="mt-1 text-base font-semibold">{item.title}</h3>
                  <p className="mt-1.5 text-sm text-ink-muted">{item.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ---------------------------------------------------- how it works */}
        <section id="how-it-works" className="scroll-mt-8 border-b border-rule bg-paper-sunk">
          <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-20">
            <h2 className="mb-10 text-3xl sm:text-4xl">How it works</h2>
            <ol className="grid gap-8 sm:grid-cols-2 lg:grid-cols-5">
              {copy.landing.howItWorks.map((step) => (
                <li key={step.step} className="relative">
                  <div className="mb-3 flex items-center gap-3">
                    <span
                      className="tnum text-2xl font-semibold text-cobalt"
                      style={{ fontFamily: "var(--font-display)" }}
                    >
                      {step.step}
                    </span>
                    <span className="h-px flex-1 bg-rule-strong" aria-hidden="true" />
                  </div>
                  <h3 className="text-base font-semibold">{step.title}</h3>
                  <p className="mt-1.5 text-sm text-ink-muted">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ---------------------------------------------------- germany layer */}
        <section className="border-b border-rule">
          <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-20">
            <div className="grid gap-10 lg:grid-cols-2 lg:items-start">
              <div>
                <h2 className="text-3xl sm:text-4xl">{copy.landing.germanyHeading}</h2>
                <p className="mt-5 max-w-lg text-[15px] leading-relaxed text-ink-muted">
                  {copy.landing.germanyBody}
                </p>
                <p className="mt-4 max-w-lg text-[15px] text-ink">{copy.landing.germanyClose}</p>
                <p className="mt-6 text-sm text-ink-faint">
                  We do not calculate your taxes, and we do not tell you which legal form to
                  choose. Those depend on facts we cannot see. We give you the questions, and
                  the official sources they come from.
                </p>
              </div>
              <div className="rounded-[--radius-card] border border-rule bg-paper-raised p-6">
                <p className="eyebrow mb-4">Questions a listing can raise</p>
                <ul className="space-y-3 text-sm">
                  {[
                    ["Freiberuflich or Gewerbe?", "§ 18 EStG, § 14 GewO"],
                    ["Do I need to notify my employer?", "Nebentätigkeit clause"],
                    ["Does Kleinunternehmerregelung apply?", "§ 19 UStG"],
                    ["What must my invoice contain?", "§ 14 Abs. 4 UStG"],
                    ["Does this affect my benefits?", "§§ 138, 155 SGB III"],
                  ].map(([question, source]) => (
                    <li
                      key={question}
                      className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-3 last:border-0 last:pb-0"
                    >
                      <span>{question}</span>
                      <span className="text-xs text-ink-faint">{source}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-4 text-xs text-ink-faint">
                  Every one of these is answered from legislation we retrieved and stored with
                  its source URL and retrieval date — never from a model&rsquo;s memory.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ------------------------------------------------- earn / keep / grow */}
        <section className="border-b border-rule bg-paper-sunk">
          <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-20">
            <h2 className="mb-10 text-3xl sm:text-4xl">{copy.landing.layersHeading}</h2>
            <div className="grid gap-px overflow-hidden rounded-[--radius-card] border border-rule bg-rule sm:grid-cols-3">
              {[
                {
                  title: "Earn",
                  lead: "Find more ways to earn.",
                  body: "Discovery, matching, prioritisation and tracking. This is the product; the other two support it.",
                },
                {
                  title: "Keep",
                  lead: "Understand the rules.",
                  body: "Source-backed German tax and administrative context, with the specific questions to put to your Finanzamt.",
                },
                {
                  title: "Grow",
                  lead: "Connect income with your goals.",
                  body: "Deterministic calculators for goals and family savings. Education, never a recommendation.",
                },
              ].map((layer) => (
                <div key={layer.title} className="bg-paper-raised p-6">
                  <h3 className="text-xl" style={{ fontFamily: "var(--font-display)" }}>
                    {layer.title}
                  </h3>
                  <p className="mt-1 text-sm font-medium">{layer.lead}</p>
                  <p className="mt-2 text-sm text-ink-muted">{layer.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------- trust */}
        <section className="border-b border-rule">
          <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-20">
            <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {copy.landing.trust.map((line) => (
                <p
                  key={line}
                  className="border-t-2 border-ink pt-4 text-lg leading-snug"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {line}
                </p>
              ))}
            </div>
          </div>
        </section>

        {/* ----------------------------------------------------------- close */}
        <section>
          <div className="mx-auto max-w-6xl px-5 py-16 text-center sm:px-8 sm:py-20">
            <h2 className="mx-auto max-w-2xl text-3xl sm:text-4xl">
              One professional profile becomes a personalised map of real earning opportunities.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-[15px] text-ink-muted">
              Starting in Germany. Free while we are validating whether this actually helps.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <DemoLaunch />
              <Link
                href="/signup"
                className="inline-flex items-center justify-center rounded-[4px] border border-rule-strong bg-paper-raised px-5 py-3 text-sm font-medium hover:border-ink-faint"
              >
                Create an account
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-rule bg-paper-sunk">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-5 py-8 sm:flex-row sm:items-start sm:justify-between sm:px-8">
          <div>
            <Logo compact />
            <p className="mt-3 max-w-md text-xs text-ink-faint">
              A validation-stage product. Opportunities marked <strong>Demo</strong> are
              fictional and exist to show how the product works. Nothing here is tax, legal or
              investment advice.
            </p>
          </div>
          <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-muted">
            <Link href="/about" className="hover:text-ink">
              About
            </Link>
            <Link href="/privacy" className="hover:text-ink">
              Privacy
            </Link>
            <Link href="/pricing" className="hover:text-ink">
              Pricing
            </Link>
            <Link href="/login" className="hover:text-ink">
              Sign in
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
