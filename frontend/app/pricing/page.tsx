import type { Metadata } from "next";
import Link from "next/link";

import { Logo } from "@/components/Logo";

export const metadata: Metadata = { title: "Pricing" };

/**
 * Pricing.
 *
 * Deliberately framed as a hypothesis rather than a price list, because that is
 * what it is: no one has paid for this product, and presenting a Pro tier as if
 * it existed would be the same kind of dishonesty the rest of the product is
 * built to avoid. Payments are behind a feature flag and off.
 */
export default function PricingPage() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-rule">
        <div className="mx-auto max-w-4xl px-5 py-4 sm:px-8">
          <Logo />
        </div>
      </header>

      <main id="main" className="mx-auto max-w-4xl px-5 py-12 sm:px-8">
        <p className="eyebrow mb-2">Pricing</p>
        <h1 className="text-4xl">Free while we find out whether this works</h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-ink-muted">
          Everything in the product is currently free. The table below is a{" "}
          <strong className="text-ink">pricing hypothesis</strong>, not an offer: nobody has paid
          for this, so we have no evidence about willingness to pay and will not pretend
          otherwise. Payments are behind a feature flag and switched off.
        </p>

        <div className="mt-10 grid gap-px overflow-hidden rounded-[--radius-card] border border-rule bg-rule sm:grid-cols-2">
          <div className="bg-paper-raised p-6">
            <h2 className="text-xl" style={{ fontFamily: "var(--font-display)" }}>
              Free
            </h2>
            <p className="tnum mt-1 text-3xl font-semibold">€0</p>
            <p className="mt-1 text-sm text-ink-faint">What everyone has today</p>
            <ul className="mt-5 space-y-2 text-sm text-ink-muted">
              {[
                "Profile and CV extraction",
                "Your first Money Map",
                "A limited number of opportunities",
                "Germany check on every opportunity",
                "Tax & Rules with citations",
                "Goals and calculators",
              ].map((item) => (
                <li key={item} className="flex gap-2">
                  <span aria-hidden="true" className="text-verified">
                    ✓
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="bg-paper-raised p-6">
            <div className="flex items-baseline justify-between">
              <h2 className="text-xl" style={{ fontFamily: "var(--font-display)" }}>
                Pro
              </h2>
              <span className="rounded-full border border-unverified/30 bg-unverified-wash px-2.5 py-1 text-[11px] font-medium text-unverified">
                Hypothesis
              </span>
            </div>
            <p className="tnum mt-1 text-3xl font-semibold text-ink-muted">€9–€19</p>
            <p className="mt-1 text-sm text-ink-faint">a month, if it turns out to be worth it</p>
            <ul className="mt-5 space-y-2 text-sm text-ink-muted">
              {[
                "Continuous discovery rather than on demand",
                "Alerts on high-match opportunities",
                "The full action workspace and drafts",
                "Advanced Money Map and income portfolio",
                "Outcome tracking over time",
              ].map((item) => (
                <li key={item} className="flex gap-2">
                  <span aria-hidden="true" className="text-ink-faint">
                    ·
                  </span>
                  {item}
                </li>
              ))}
            </ul>
            <p className="mt-5 border-t border-rule pt-4 text-xs text-ink-faint">
              Not available, not billable, and not a commitment to this price. It exists here so
              you can tell us whether it sounds worth paying for.
            </p>
          </div>
        </div>

        <section className="mt-12">
          <h2 className="text-2xl">How we will not make money</h2>
          <ul className="mt-4 space-y-3 text-[15px] text-ink-muted">
            <li>
              <strong className="text-ink">Ranking is never sold.</strong> If a sponsored
              opportunity ever appears, it will be marked as sponsored and it will be scored by
              the same deterministic engine as everything else. The score does not have a field
              for money.
            </li>
            <li>
              <strong className="text-ink">Your data is not the product.</strong> No selling
              profiles, no selling CVs, no training models on your documents.
            </li>
            <li>
              <strong className="text-ink">No dark patterns.</strong> No pre-ticked upgrades, no
              cancellation mazes, no trial that quietly becomes a subscription.
            </li>
          </ul>
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
