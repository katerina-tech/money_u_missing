"use client";

/**
 * The application shell.
 *
 * Navigation is by product area - Money Map, Opportunities, Actions, Tax &
 * Rules, Grow, Family. Chat is deliberately absent: this is a structured
 * product, and a chat box as the primary surface would make the user do the
 * work of knowing what to ask.
 *
 * The shell also renders two honesty affordances that appear on every page: the
 * demo banner, and the capability notice when something is degraded.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/Logo";
import { api, tokens } from "@/lib/api";
import { copy } from "@/lib/copy";
import type { Capabilities } from "@/lib/types";

const NAV = [
  { href: "/dashboard", label: copy.nav.moneyMap },
  { href: "/opportunities", label: copy.nav.opportunities },
  { href: "/actions", label: copy.nav.actions },
  { href: "/tax", label: copy.nav.tax },
  { href: "/grow", label: copy.nav.grow },
  { href: "/family", label: copy.nav.family },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!tokens.isSignedIn) {
      router.replace("/login");
      return;
    }
    setIsDemo(tokens.read().isDemo);
    setReady(true);
    api.capabilities().then(setCapabilities).catch(() => undefined);
  }, [router]);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-ink-muted">Checking your session…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      {isDemo ? (
        <div className="bg-demo px-5 py-2 text-center text-[13px] font-medium text-white">
          Demo session · a fictional professional, fictional opportunities. Nothing here is a
          real offer.
        </div>
      ) : null}

      <header className="sticky top-0 z-40 border-b border-rule bg-paper/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-3 sm:px-8">
          <Logo href="/dashboard" compact />

          <nav aria-label="Primary" className="hidden items-center gap-1 lg:flex">
            {NAV.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-[4px] px-3 py-2 text-sm transition-colors ${
                    active
                      ? "bg-paper-sunk font-medium text-ink"
                      : "text-ink-muted hover:text-ink"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-2">
            <Link
              href="/profile"
              className="hidden rounded-[4px] px-3 py-2 text-sm text-ink-muted hover:text-ink sm:inline"
            >
              {copy.nav.profile}
            </Link>
            <Link
              href="/settings"
              className="hidden rounded-[4px] px-3 py-2 text-sm text-ink-muted hover:text-ink sm:inline"
            >
              {copy.nav.settings}
            </Link>
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              className="rounded-[4px] border border-rule-strong px-3 py-2 text-sm lg:hidden"
            >
              Menu
            </button>
          </div>
        </div>

        {menuOpen ? (
          <nav
            id="mobile-nav"
            aria-label="Primary, mobile"
            className="border-t border-rule bg-paper-raised lg:hidden"
          >
            <ul className="mx-auto max-w-6xl px-5 py-2 sm:px-8">
              {[...NAV, { href: "/profile", label: copy.nav.profile }, { href: "/settings", label: copy.nav.settings }].map(
                (item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="block border-b border-rule py-3 text-sm last:border-0"
                    >
                      {item.label}
                    </Link>
                  </li>
                ),
              )}
            </ul>
          </nav>
        ) : null}
      </header>

      {capabilities && capabilities.degradations.length > 0 ? (
        <div className="border-b border-unverified/25 bg-unverified-wash">
          <div className="mx-auto max-w-6xl px-5 py-2.5 text-xs text-unverified sm:px-8">
            <details>
              <summary className="cursor-pointer font-medium">
                {capabilities.degradations.length} feature
                {capabilities.degradations.length === 1 ? " is" : "s are"} running in a reduced
                mode
              </summary>
              <ul className="mt-2 space-y-1.5 pl-4">
                {capabilities.degradations.map((line) => (
                  <li key={line} className="list-disc">
                    {line}
                  </li>
                ))}
              </ul>
            </details>
          </div>
        </div>
      ) : null}

      <main id="main" className="flex-1">
        {children}
      </main>

      <footer className="border-t border-rule">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-6 text-xs text-ink-faint sm:px-8">
          <p>
            Not tax, legal or investment advice. Opportunity data carries the source it came
            from.
          </p>
          <div className="flex gap-4">
            <Link href="/privacy" className="hover:text-ink">
              Privacy
            </Link>
            <Link href="/about" className="hover:text-ink">
              About
            </Link>
            <button
              type="button"
              onClick={async () => {
                await api.logout();
                router.push("/");
              }}
              className="hover:text-ink"
            >
              Sign out
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
