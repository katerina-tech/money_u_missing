/**
 * The component system.
 *
 * Small, unopinionated primitives plus a handful of components that exist
 * specifically to make dishonesty inconvenient: `TrustBadge` cannot be rendered
 * without a label, `MoneyFigure` renders "Not published" for null rather than a
 * zero, and `UnknownList` gives absence the same visual weight as presence.
 *
 * Accessibility is built in rather than retrofitted: every control is a real
 * button or input, every icon-only control has a label, focus is never removed,
 * and colour is never the only carrier of meaning.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { BAND_COPY, TRUST_COPY, formatMoneyRange } from "@/lib/format";
import type { ActionabilityBand, Money, TrustLabel } from "@/lib/types";

function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

// ================================================================ layout

export function Page({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 sm:py-12">{children}</div>;
}

export function PageHeader({
  eyebrow,
  title,
  lead,
  actions,
}: {
  eyebrow?: string;
  title: string;
  lead?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-col gap-4 sm:mb-10 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        {eyebrow ? <p className="eyebrow mb-2">{eyebrow}</p> : null}
        <h1 className="text-3xl sm:text-4xl">{title}</h1>
        {lead ? <p className="mt-3 text-[15px] text-ink-muted">{lead}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}

export function Section({
  title,
  description,
  actions,
  children,
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="mb-10">
      {title ? (
        <div className="mb-4 flex items-baseline justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            {description ? (
              <p className="mt-1 text-sm text-ink-muted">{description}</p>
            ) : null}
          </div>
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Card({
  children,
  className,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "article" | "li";
}) {
  return (
    <Tag
      className={cx(
        "rounded-[--radius-card] border border-rule bg-paper-raised p-5 sm:p-6",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

// ================================================================ controls

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary:
    "bg-cobalt text-white hover:bg-cobalt-deep disabled:bg-rule-strong disabled:text-ink-faint",
  secondary:
    "border border-rule-strong bg-paper-raised text-ink hover:border-ink-faint disabled:text-ink-faint",
  ghost: "text-ink-muted hover:text-ink underline underline-offset-4 decoration-rule-strong",
  danger: "border border-danger text-danger hover:bg-danger-wash",
};

export function Button({
  children,
  variant = "primary",
  type = "button",
  onClick,
  disabled,
  className,
  full,
}: {
  children: ReactNode;
  variant?: ButtonVariant;
  type?: "button" | "submit";
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  full?: boolean;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-[4px] px-4 py-2.5 text-sm font-medium transition-colors",
        "disabled:cursor-not-allowed",
        BUTTON_STYLES[variant],
        full && "w-full",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function LinkButton({
  href,
  children,
  variant = "primary",
  className,
  external,
}: {
  href: string;
  children: ReactNode;
  variant?: ButtonVariant;
  className?: string;
  external?: boolean;
}) {
  const classes = cx(
    "inline-flex items-center justify-center gap-2 rounded-[4px] px-4 py-2.5 text-sm font-medium transition-colors",
    BUTTON_STYLES[variant],
    className,
  );
  if (external) {
    return (
      <a href={href} className={classes} target="_blank" rel="noopener noreferrer nofollow">
        {children}
        <span aria-hidden="true">↗</span>
      </a>
    );
  }
  return (
    <Link href={href} className={classes}>
      {children}
    </Link>
  );
}

export function Field({
  label,
  hint,
  children,
  htmlFor,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="mb-4">
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      {hint ? <p className="mb-1.5 text-xs text-ink-faint">{hint}</p> : null}
      {children}
    </div>
  );
}

const INPUT_CLASSES =
  "w-full rounded-[4px] border border-rule-strong bg-paper-raised px-3 py-2 text-sm text-ink placeholder:text-ink-faint";

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(INPUT_CLASSES, props.className)} />;
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx(INPUT_CLASSES, "min-h-32", props.className)} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(INPUT_CLASSES, props.className)} />;
}

// ============================================================== evidence

const TRUST_STYLES: Record<TrustLabel, string> = {
  VERIFIED: "bg-verified-wash text-verified border-verified/25",
  SOURCE_BACKED: "bg-sourced-wash text-sourced border-sourced/25",
  UNVERIFIED: "bg-unverified-wash text-unverified border-unverified/25",
  DEMO: "bg-demo-wash text-demo border-demo/25",
  NEEDS_REVIEW: "bg-unverified-wash text-unverified border-unverified/25",
  OUTDATED: "bg-danger-wash text-danger border-danger/25",
  UNKNOWN: "bg-unknown-wash text-unknown border-unknown/25",
};

/**
 * The evidence badge. Impossible to render without saying what it means:
 * `title` carries the explanation for a pointer, and the label itself is a
 * word rather than a colour, so it survives being printed in greyscale or read
 * by someone who cannot distinguish the palette.
 */
export function TrustBadge({ trust, size = "sm" }: { trust: TrustLabel; size?: "sm" | "xs" }) {
  const copy = TRUST_COPY[trust];
  return (
    <span
      title={copy.meaning}
      className={cx(
        "inline-flex items-center rounded-full border font-medium uppercase tracking-wide",
        TRUST_STYLES[trust],
        size === "xs" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]",
      )}
    >
      {copy.label}
    </span>
  );
}

const BAND_STYLES: Record<ActionabilityBand, string> = {
  HIGHLY_ACTIONABLE: "bg-verified-wash text-verified border-verified/25",
  ACTIONABLE: "bg-sourced-wash text-sourced border-sourced/25",
  REVIEW_FIRST: "bg-unverified-wash text-unverified border-unverified/25",
  LOW_PRIORITY: "bg-unknown-wash text-unknown border-unknown/25",
};

export function BandBadge({ band }: { band: ActionabilityBand }) {
  const copy = BAND_COPY[band] ?? { label: band, meaning: "" };
  return (
    <span
      title={copy.meaning}
      className={cx(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium",
        BAND_STYLES[band],
      )}
    >
      {copy.label}
    </span>
  );
}

/**
 * A money figure that cannot lie about absence.
 *
 * Null renders as "Not published" in muted type, never as a zero and never as
 * an empty space that a reader fills in optimistically.
 */
export function MoneyFigure({
  money,
  size = "base",
}: {
  money: Money;
  size?: "base" | "lg";
}) {
  const known = money.minor_min !== null || money.minor_max !== null;
  if (!known) {
    return (
      <span className="text-sm text-ink-faint italic">
        {money.unknown_note ?? "Not published"}
      </span>
    );
  }
  return (
    <span className={cx("tnum font-medium", size === "lg" ? "text-2xl" : "text-[15px]")}>
      {formatMoneyRange(money)}
      {!money.verified ? (
        <span
          className="ml-2 align-middle text-[11px] font-normal text-ink-faint"
          title="This figure appears in the listing but we have not confirmed it."
        >
          unconfirmed
        </span>
      ) : null}
    </span>
  );
}

/**
 * The "what we don't know" panel.
 *
 * Given equal visual weight to "what we know" on purpose. A product that lists
 * its certainties in a card and its doubts in a footnote has chosen which one
 * the reader will remember.
 */
export function UnknownList({ items, title }: { items: string[]; title: string }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="eyebrow mb-2">{title}</h3>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-sm text-ink-muted">
            <span aria-hidden="true" className="text-ink-faint">
              ?
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function KnownList({ items, title }: { items: string[]; title: string }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="eyebrow mb-2">{title}</h3>
      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-sm text-ink-muted">
            <span aria-hidden="true" className="text-verified">
              ✓
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// =============================================================== feedback

export function Notice({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warning" | "danger" | "demo";
  title?: string;
  children: ReactNode;
}) {
  const styles = {
    info: "border-rule bg-paper-sunk",
    warning: "border-unverified/30 bg-unverified-wash",
    danger: "border-danger/30 bg-danger-wash",
    demo: "border-demo/30 bg-demo-wash",
  }[tone];
  return (
    <div className={cx("rounded-[--radius-card] border p-4 text-sm", styles)}>
      {title ? <p className="mb-1 font-medium">{title}</p> : null}
      <div className="text-ink-muted">{children}</div>
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-[--radius-card] border border-dashed border-rule-strong p-10 text-center">
      <p className="font-medium">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">{body}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-hidden="true" className="space-y-3">
      {Array.from({ length: lines }, (_, index) => (
        <div
          key={index}
          className="h-4 rounded bg-paper-sunk"
          style={{ width: `${100 - index * 12}%` }}
        />
      ))}
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-ink-muted">
      <span
        aria-hidden="true"
        className="h-3 w-3 animate-spin rounded-full border-2 border-rule-strong border-t-cobalt"
      />
      {label}
    </p>
  );
}

// ================================================================= data

export function Stat({
  label,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  value: string;
  detail?: string;
  tone?: "default" | "muted";
}) {
  return (
    <div>
      <p className="eyebrow mb-1">{label}</p>
      <p
        className={cx(
          "tnum text-2xl font-semibold",
          tone === "muted" ? "text-ink-faint" : "text-ink",
        )}
      >
        {value}
      </p>
      {detail ? <p className="mt-1 text-xs text-ink-faint">{detail}</p> : null}
    </div>
  );
}

/**
 * The goal progress bar.
 *
 * Deliberately shows an empty bar when nothing has been secured, with the
 * explanation beside it. Filling it with potential would be the single most
 * misleading pixel this product could draw.
 */
export function ProgressBar({
  ratio,
  label,
  explainer,
}: {
  ratio: number | null;
  label: string;
  explainer?: string;
}) {
  const percent = Math.round((ratio ?? 0) * 100);
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between text-sm">
        <span className="text-ink-muted">{label}</span>
        <span className="tnum font-medium">{ratio === null ? "—" : `${percent}%`}</span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
        className="h-2 overflow-hidden rounded-full bg-paper-sunk"
      >
        <div className="h-full rounded-full bg-cobalt" style={{ width: `${percent}%` }} />
      </div>
      {explainer ? <p className="mt-2 text-xs text-ink-faint">{explainer}</p> : null}
    </div>
  );
}

export function ScoreDial({ score, eligible }: { score: number; eligible: boolean }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span
        className={cx("tnum text-3xl font-semibold", !eligible && "text-ink-faint line-through")}
      >
        {score}
      </span>
      <span className="text-sm text-ink-faint">% match</span>
    </div>
  );
}

export function DefinitionList({ items }: { items: { term: string; value: ReactNode }[] }) {
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {items.map((item) => (
        <div key={item.term}>
          <dt className="eyebrow mb-0.5">{item.term}</dt>
          <dd className="text-sm">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
