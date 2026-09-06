import type { Metadata, Viewport } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Money You're Missing — one profile, multiple ways to earn",
    template: "%s · Money You're Missing",
  },
  description:
    "Discover real income opportunities matched to your skills, time and goals — with the source-backed German context you need to act. Not idea generation: real, cited opportunities.",
  applicationName: "Money You're Missing",
  // The product is not indexed while it is a validation MVP with demo data on
  // the landing page; a search result promising real opportunities would be
  // making a claim the current build cannot keep.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfaf7" },
    { media: "(prefers-color-scheme: dark)", color: "#14161a" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
