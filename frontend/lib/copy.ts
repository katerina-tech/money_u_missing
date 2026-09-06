/**
 * Every user-facing string, in one place.
 *
 * Two reasons, and localisation is only the second one.
 *
 * The first is that this product's copy carries its promises. "Potential", "not
 * published", "we could not verify this" and "questions to check" are not
 * phrasing choices - they are the difference between an honest product and a
 * confident one. Keeping them together means they can be reviewed as a set, and
 * a component cannot quietly introduce "guaranteed" on its own.
 *
 * The second is that German is the launch market's language and the UI ships in
 * English. Adding `de` here is a translation task, not a refactor - which is
 * what "localisation-ready" has to mean to be worth claiming.
 */

export type Locale = "en";

export const DEFAULT_LOCALE: Locale = "en";

export const copy = {
  brand: "Money You're Missing",
  tagline: "One profile. Multiple ways to earn.",

  nav: {
    moneyMap: "Money Map",
    opportunities: "Opportunities",
    actions: "Actions",
    tax: "Tax & Rules",
    grow: "Grow",
    family: "Family",
    profile: "Profile",
    settings: "Settings",
  },

  landing: {
    heroLead:
      "Discover real income opportunities matched to your skills, time and goals — with the context you need to act confidently in Germany.",
    // The brand name is ambiguous, and the ambiguity is expensive: people
    // arrive expecting unclaimed government money or a subscription auditor.
    // This clarification sits in the first viewport, by design.
    clarification:
      "This is about earning opportunities you are overlooking — consulting, expert calls, teaching, paid programmes, grants. It is not unclaimed government money, not forgotten subscriptions, and not a tax refund finder.",
    primaryCta: "Build my Money Map",
    secondaryCta: "See how it works",
    demoCta: "Try the demo",
    categories: [
      "Consulting",
      "Expert calls",
      "Teaching",
      "Paid programmes",
      "Grants",
      "Professional opportunities",
    ],
    problemHeading: "Your experience is worth more than one paycheck.",
    problemBody:
      "Opportunities are fragmented across dozens of platforms. Jobs are in one place. Freelance work in another. Expert networks somewhere else. Programmes and grants are scattered across hundreds of pages.",
    problemClose:
      "Money You're Missing turns one professional profile into one prioritised opportunity map.",
    differentiationHeading: "Not more ideas. Better opportunities.",
    howItWorks: [
      { step: "01", title: "Build your profile", body: "Upload a CV, paste it, or type it. You review everything before we use it." },
      { step: "02", title: "Discover", body: "We search real sources across categories you would not think to check." },
      { step: "03", title: "Understand", body: "Transparent matching, what we know, and what we don't." },
      { step: "04", title: "Act", body: "One recommended next move, with a checklist and the questions to ask." },
      { step: "05", title: "Earn", body: "Track it from potential through applied to actually paid." },
    ],
    germanyHeading: "Earn more. Know what it means.",
    germanyBody:
      "Before you act, understand the questions that may matter: freelance or Gewerbe? Employer notification? VAT? Benefits? Invoices?",
    germanyClose:
      "Money You're Missing connects opportunities with source-backed German context.",
    layersHeading: "Earn. Keep. Grow.",
    trust: [
      "Real sources, not invented opportunities.",
      "Unknown means unknown.",
      "AI helps explain. Rules come from verified sources.",
      "You decide what to pursue.",
    ],
  },

  money: {
    potential: "Potential",
    secured: "Secured",
    earned: "Earned",
    goal: "Goal",
    notPublished: "Not published",
    recurringPotential: "Recurring potential",
    oneTimePotential: "One-time potential",
    unknownValue: "Value not published",
    // Rendered next to the goal bar. Without it, an empty bar next to a page
    // full of opportunities reads as a bug rather than as the truth.
    progressExplainer:
      "This bar moves only on money you have actually secured or earned. Potential opportunities are shown separately, on purpose.",
  },

  opportunity: {
    whyItMatches: "Why this matches",
    whatWeKnow: "What we know",
    whatWeDontKnow: "What we don't know",
    germanyCheck: "Germany check",
    nextAction: "Next action",
    source: "Source",
    lastVerified: "Last seen",
    save: "Save",
    saved: "Saved",
    prepare: "Prepare application",
    openSource: "Open original source",
    dismiss: "Not for me",
    aiWritten: "Written by AI from the computed breakdown above.",
    scoreExplainer:
      "Computed in code from your profile and this listing. The same inputs always give the same score.",
  },

  errors: {
    llmUnavailable:
      "We couldn't analyse this right now. Your saved data is safe.",
    searchUnavailable:
      "Live opportunity search is temporarily unavailable. Showing verified cached opportunities.",
    ragUnavailable:
      "Current source verification is unavailable, so we won't provide an answer from memory.",
    generic: "Something went wrong. Your saved data is safe.",
  },

  validation: {
    wouldNotHaveFound:
      "Did Money You're Missing show you an opportunity you probably would not have found yourself?",
    wouldPursue: "Would you actually pursue this?",
    yes: "Yes",
    partly: "Partly",
    maybe: "Maybe",
    no: "No",
    thanks: "Thank you. This is how we learn whether the product works.",
  },

  disclaimers: {
    tax: "Educational information from the sources cited. Not Steuerberatung and not Rechtsberatung.",
    grow: "Illustrative assumption — not a forecast.",
    family:
      "There is no generally correct answer. Which account ownership suits a family depends on circumstances this product cannot assess.",
    investment:
      "Educational information about how these instruments work. Not investment advice, and no recommendation of any product.",
  },
} as const;
