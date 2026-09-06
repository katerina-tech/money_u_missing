import type { Metadata } from "next";
import Link from "next/link";

import { Logo } from "@/components/Logo";

export const metadata: Metadata = { title: "About" };

export default function AboutPage() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-rule">
        <div className="mx-auto max-w-3xl px-5 py-4 sm:px-8">
          <Logo />
        </div>
      </header>

      <main id="main" className="mx-auto max-w-3xl px-5 py-12 sm:px-8">
        <p className="eyebrow mb-2">About</p>
        <h1 className="text-4xl">What this is, and what it is not</h1>

        <div className="mt-8 space-y-6 text-[15px] leading-relaxed text-ink-muted">
          <p>
            Money You&rsquo;re Missing turns one professional profile into a prioritised map of
            real earning opportunities, with the German administrative context you need to act
            on them. It is built for skilled professionals living in Germany who want to
            increase or diversify their income without spending hours searching across a dozen
            unrelated platforms.
          </p>

          <h2 className="text-2xl text-ink">What it is not</h2>
          <p>
            It is not an idea generator. A model can produce a hundred plausible sentences about
            ways to make money, and not one of them is something you can apply to. Every
            opportunity here exists because a source published it, and every card links back to
            that source.
          </p>
          <p>
            It is not a job board. Jobs are one category among a dozen — expert networks,
            teaching, paid research, workshops, grants, fellowships and founder programmes are
            where most of the missed money actually is, precisely because they are scattered.
          </p>
          <p>
            It is not a tax adviser. The Tax &amp; Rules section is source-backed education: it
            cites the legislation, tells you which questions to put to your Finanzamt, and
            declines to answer anything it cannot cite. It does not classify your activity and
            does not calculate what you owe.
          </p>
          <p>
            It is not an investment adviser. The Grow section calculates what your own
            assumptions imply and explains what an ETF is. It does not recommend products, does
            not produce an allocation, and does not execute anything.
          </p>

          <h2 className="text-2xl text-ink">How the AI is used, and where it is not</h2>
          <p>
            A language model does three things here: it reads a CV into a structured draft you
            review, it plans search queries, and it phrases explanations of scores that were
            already computed. That is the whole list.
          </p>
          <p>
            Everything that decides something is ordinary code. Match scores, actionability
            bands, eligibility checks, safety classification, de-duplication and every money
            figure are computed in Python. The same profile and the same listing always produce
            the same score, and every component of that score can be shown to you as a sentence.
            A listing cannot argue its way up the ranking, because nothing in the ranking reads
            its persuasion.
          </p>

          <h2 className="text-2xl text-ink">Why so much of the interface is about doubt</h2>
          <p>
            Most listings do not publish what they pay. Most do not state their time commitment.
            Many state requirements ambiguously. A product that filled those gaps with plausible
            numbers would be more satisfying to use and worth considerably less, because you
            would have no way to tell which figures were real.
          </p>
          <p>
            So unknown stays unknown: it is rendered as &ldquo;not published&rdquo;, counted
            separately, excluded from totals, and given the same visual weight as the things we
            do know.
          </p>

          <h2 className="text-2xl text-ink">Current status</h2>
          <p>
            This is a validation-stage product. The demo dataset is fictional and labelled as
            such throughout. The curated dataset holds a small number of real programmes recorded
            by hand from their own pages — including their compensation fields left empty,
            because those pages do not state the amounts.
          </p>
          <p>
            We are trying to find out one thing: whether this shows people opportunities they
            would not have found themselves, and whether they act on them. That is what the two
            questions at the bottom of the Money Map are for.
          </p>
        </div>

        <p className="mt-12 text-sm">
          <Link href="/" className="text-cobalt underline underline-offset-4">
            ← Back
          </Link>
        </p>
      </main>
    </div>
  );
}
