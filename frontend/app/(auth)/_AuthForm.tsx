"use client";

/**
 * Sign in and sign up, sharing one component.
 *
 * The password rule is length only. Composition rules push people towards
 * `Password1!`, and a length floor is both stronger and easier to meet with a
 * passphrase.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/Logo";
import { Button, Card, Field, Notice, TextInput } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { copy } from "@/lib/copy";

const MIN_PASSWORD = 10;

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isSignup = mode === "signup";
  const canSubmit =
    email.includes("@") && password.length >= MIN_PASSWORD && (!isSignup || accepted);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (isSignup) {
        await api.signup(email, password);
        router.push("/onboarding");
      } else {
        await api.login(email, password);
        router.push("/dashboard");
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : copy.errors.generic);
      setBusy(false);
    }
  }

  return (
    <main id="main" className="flex min-h-screen flex-col items-center justify-center px-5 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>

        <Card>
          <h1 className="mb-1 text-2xl">{isSignup ? "Create your account" : "Sign in"}</h1>
          <p className="mb-6 text-sm text-ink-muted">
            {isSignup
              ? "Free while we are validating whether this actually helps people earn more."
              : "Welcome back."}
          </p>

          <form onSubmit={submit}>
            <Field label="Email" htmlFor="auth-email">
              <TextInput
                id="auth-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>

            <Field
              label="Password"
              htmlFor="auth-password"
              hint={
                isSignup
                  ? `At least ${MIN_PASSWORD} characters. A passphrase is easier to remember and harder to guess than a short complicated one.`
                  : undefined
              }
            >
              <TextInput
                id="auth-password"
                type="password"
                autoComplete={isSignup ? "new-password" : "current-password"}
                required
                minLength={MIN_PASSWORD}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>

            {isSignup ? (
              <label className="mb-5 flex items-start gap-2.5 text-sm">
                <input
                  type="checkbox"
                  checked={accepted}
                  onChange={(event) => setAccepted(event.target.checked)}
                  className="mt-1 accent-cobalt"
                  required
                />
                <span className="text-ink-muted">
                  I have read the{" "}
                  <Link href="/privacy" className="text-cobalt underline underline-offset-4">
                    privacy notice
                  </Link>{" "}
                  and agree to my profile information being processed to find and rank income
                  opportunities for me. My CV is never used to train any model.
                </span>
              </label>
            ) : null}

            {error ? (
              <div className="mb-4">
                <Notice tone="danger">{error}</Notice>
              </div>
            ) : null}

            <Button type="submit" disabled={!canSubmit || busy} full>
              {busy ? "Please wait…" : isSignup ? "Create account" : "Sign in"}
            </Button>
          </form>
        </Card>

        <p className="mt-6 text-center text-sm text-ink-muted">
          {isSignup ? (
            <>
              Already have an account?{" "}
              <Link href="/login" className="text-cobalt underline underline-offset-4">
                Sign in
              </Link>
            </>
          ) : (
            <>
              No account?{" "}
              <Link href="/signup" className="text-cobalt underline underline-offset-4">
                Create one
              </Link>
            </>
          )}
        </p>
        <p className="mt-2 text-center text-sm">
          <Link href="/" className="text-ink-faint underline underline-offset-4 hover:text-ink">
            Or try the demo without an account
          </Link>
        </p>
      </div>
    </main>
  );
}
