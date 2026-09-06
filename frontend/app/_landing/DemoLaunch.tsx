"use client";

/**
 * The landing page's primary call to action.
 *
 * Starts a throwaway demo session and goes straight to the Money Map. No
 * account, no email, no form - because the thing an accelerator jury or a first
 * visitor needs is to see the product, and every field between them and it
 * loses some of them.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";

export function DemoLaunch() {
  const router = useRouter();
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function start() {
    setState("loading");
    setMessage(null);
    try {
      await api.startDemo();
      // Refresh immediately so the map is populated when the page renders,
      // rather than showing an empty dashboard for a second.
      await api.refreshMoneyMap().catch(() => undefined);
      router.push("/dashboard");
    } catch (error) {
      setState("error");
      setMessage(
        error instanceof ApiError
          ? `${error.message}${error.recovery ? ` ${error.recovery}` : ""}`
          : copy.errors.generic,
      );
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={start}
        disabled={state === "loading"}
        className="inline-flex items-center justify-center gap-2 rounded-[4px] bg-cobalt px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-cobalt-deep disabled:bg-rule-strong disabled:text-ink-faint"
      >
        {state === "loading" ? "Building your Money Map…" : copy.landing.primaryCta}
      </button>
      <p className="mt-2 text-xs text-ink-faint">
        Opens a demo with a fictional professional. No account, no email.
      </p>
      {message ? (
        <p role="alert" className="mt-2 text-xs text-danger">
          {message}
        </p>
      ) : null}
    </div>
  );
}
