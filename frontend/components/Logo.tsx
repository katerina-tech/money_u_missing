/**
 * The wordmark.
 *
 * One component, used everywhere - the brand should never be re-typed as loose
 * markup that then drifts. The mark is a small ledger rule with one line raised
 * above it: the money that is there, and the money that is not yet.
 */

import Link from "next/link";

export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      role="img"
      aria-label="Money You're Missing"
    >
      <rect x="1" y="1" width="30" height="30" rx="4" className="fill-ink" />
      {/* Three ledger lines: two settled, one raised - the one you are missing. */}
      <rect x="8" y="20" width="16" height="2.2" rx="1.1" className="fill-paper" opacity="0.55" />
      <rect x="8" y="15" width="11" height="2.2" rx="1.1" className="fill-paper" opacity="0.75" />
      <rect x="8" y="9" width="7" height="2.2" rx="1.1" className="fill-cobalt" />
      <circle cx="23" cy="10.1" r="2.4" className="fill-cobalt" />
    </svg>
  );
}

export function Logo({ href = "/", compact = false }: { href?: string; compact?: boolean }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2.5">
      <LogoMark size={compact ? 24 : 28} />
      <span className="leading-none">
        <span
          className="block font-semibold tracking-tight"
          style={{ fontFamily: "var(--font-display)", fontSize: compact ? "15px" : "17px" }}
        >
          Money You&rsquo;re Missing
        </span>
        {!compact ? (
          <span className="mt-0.5 block text-[10px] uppercase tracking-[0.16em] text-ink-faint">
            One profile. Multiple ways to earn.
          </span>
        ) : null}
      </span>
    </Link>
  );
}
