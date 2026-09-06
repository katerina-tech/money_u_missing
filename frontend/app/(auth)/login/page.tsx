import type { Metadata } from "next";

import { AuthForm } from "../_AuthForm";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return <AuthForm mode="login" />;
}
