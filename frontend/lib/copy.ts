/**
 * Every user-facing string, in one place, in every language we ship.
 *
 * Two reasons, and localisation is only the second one.
 *
 * The first is that this product's copy carries its promises. "Potential", "not
 * published", "we could not verify this" and "questions to check" are not
 * phrasing choices - they are the difference between an honest product and a
 * confident one. Keeping them together means they can be reviewed as a set, and
 * a component cannot quietly introduce "guaranteed" on its own.
 *
 * The second is translation. `en` is the source of truth: its shape defines the
 * `Copy` type, so every other locale is checked against it at compile time and
 * a missing key is a build error rather than a blank space in the interface.
 *
 * WHAT IS NOT TRANSLATED, DELIBERATELY:
 *
 * - German statutory terms - Gewerbe, Kleinunternehmerregelung, Steuerklasse,
 *   freiberuflich, Steuerberatung. A user in Germany has to recognise these
 *   words on a form and in a letter. Translating them would read more fluently
 *   and would leave the reader less able to act.
 * - Quoted legislation and the `LegalFact` registry. Those are source text with
 *   a citation and a retrieval date. A translation is not the source, and this
 *   product does not fabricate legal text.
 * - The brand name.
 */

export const LOCALES = ["en", "ru"] as const;

export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  ru: "Русский",
};

/** BCP 47 tags, for `<html lang>` and for `Intl`. */
export const LOCALE_TAGS: Record<Locale, string> = {
  en: "en-DE",
  ru: "ru-RU",
};

export function isLocale(value: unknown): value is Locale {
  return (
    typeof value === "string" && (LOCALES as readonly string[]).includes(value)
  );
}

const en = {
  brand: "Money You're Missing",
  tagline: "One profile. Multiple ways to earn.",

  localeSwitcher: {
    label: "Language",
  },

  nav: {
    moneyMap: "Money Map",
    opportunities: "Opportunities",
    actions: "Actions",
    personal: "Your money",
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
      {
        step: "01",
        title: "Build your profile",
        body: "Upload a CV, paste it, or type it. You review everything before we use it.",
      },
      {
        step: "02",
        title: "Discover",
        body: "We search real sources across categories you would not think to check.",
      },
      {
        step: "03",
        title: "Understand",
        body: "Transparent matching, what we know, and what we don't.",
      },
      {
        step: "04",
        title: "Act",
        body: "One recommended next move, with a checklist and the questions to ask.",
      },
      {
        step: "05",
        title: "Earn",
        body: "Track it from potential through applied to actually paid.",
      },
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

  // Text computed by the backend - match explanations, the Germany check, the
  // legal answer layer - arrives in English whatever this setting says. The
  // banner states that rather than letting a reader assume the English
  // paragraphs are a bug. See docs/LOCALISATION.md for why, and what it costs
  // to fix properly.
  partialTranslation:
    "Interface translated. Match explanations, the Germany check and legal citations are computed by the backend and remain in English.",
};

/**
 * The shape every locale must satisfy. Derived from `en`, so adding a string
 * there turns every other locale into a compile error until it is translated -
 * the only mechanism that reliably stops translations from rotting.
 */
export type Copy = typeof en;

const ru: Copy = {
  brand: "Money You're Missing",
  tagline: "Один профиль. Несколько способов зарабатывать.",

  localeSwitcher: {
    label: "Язык",
  },

  nav: {
    moneyMap: "Карта дохода",
    opportunities: "Возможности",
    actions: "Действия",
    personal: "Ваши деньги",
    tax: "Налоги и правила",
    grow: "Накопления",
    family: "Семья",
    profile: "Профиль",
    settings: "Настройки",
  },

  landing: {
    heroLead:
      "Реальные возможности заработка, подобранные под ваши навыки, время и цели — вместе с контекстом, который нужен, чтобы уверенно действовать в Германии.",
    clarification:
      "Речь о возможностях заработать, которые вы упускаете: консультирование, экспертные звонки, преподавание, оплачиваемые программы, гранты. Это не невостребованные государственные выплаты, не забытые подписки и не поиск налогового возврата.",
    primaryCta: "Построить карту дохода",
    secondaryCta: "Как это работает",
    demoCta: "Открыть демо",
    categories: [
      "Консультирование",
      "Экспертные звонки",
      "Преподавание",
      "Оплачиваемые программы",
      "Гранты",
      "Профессиональные возможности",
    ],
    problemHeading: "Ваш опыт стоит больше одной зарплаты.",
    problemBody:
      "Возможности разбросаны по десяткам платформ. Вакансии в одном месте. Фриланс в другом. Экспертные сети где-то ещё. Программы и гранты — на сотнях страниц, которые никто не проверяет.",
    problemClose:
      "Money You're Missing превращает один профессиональный профиль в одну карту возможностей с расставленными приоритетами.",
    differentiationHeading: "Не больше идей. Возможности лучше.",
    howItWorks: [
      {
        step: "01",
        title: "Профиль",
        body: "Загрузите резюме, вставьте текст или заполните вручную. Вы проверяете всё, прежде чем мы это используем.",
      },
      {
        step: "02",
        title: "Поиск",
        body: "Мы ищем по реальным источникам в категориях, которые вы бы не подумали проверить.",
      },
      {
        step: "03",
        title: "Понимание",
        body: "Прозрачное совпадение: что мы знаем и чего не знаем.",
      },
      {
        step: "04",
        title: "Действие",
        body: "Один рекомендованный следующий шаг, с чек-листом и вопросами, которые стоит задать.",
      },
      {
        step: "05",
        title: "Заработок",
        body: "Отслеживайте путь от потенциала через отклик до реально полученных денег.",
      },
    ],
    germanyHeading: "Зарабатывать больше. Понимать последствия.",
    germanyBody:
      "Прежде чем действовать, разберитесь с вопросами, которые могут иметь значение: freiberuflich или Gewerbe? Уведомлять ли работодателя? НДС? Пособия? Счета?",
    germanyClose:
      "Money You're Missing связывает возможности с немецким контекстом, подтверждённым источниками.",
    layersHeading: "Зарабатывать. Сохранять. Приумножать.",
    trust: [
      "Реальные источники, а не выдуманные возможности.",
      "Неизвестное остаётся неизвестным.",
      "ИИ помогает объяснить. Правила берутся из проверенных источников.",
      "Что делать — решаете вы.",
    ],
  },

  money: {
    potential: "Потенциал",
    secured: "Закреплено",
    earned: "Заработано",
    goal: "Цель",
    notPublished: "Не указано",
    recurringPotential: "Регулярный потенциал",
    oneTimePotential: "Разовый потенциал",
    unknownValue: "Сумма не указана в источнике",
    progressExplainer:
      "Эта шкала движется только за счёт денег, которые вы действительно закрепили или получили. Потенциальные возможности показаны отдельно — намеренно.",
  },

  opportunity: {
    whyItMatches: "Почему это вам подходит",
    whatWeKnow: "Что мы знаем",
    whatWeDontKnow: "Чего мы не знаем",
    germanyCheck: "Проверка по Германии",
    nextAction: "Следующий шаг",
    source: "Источник",
    lastVerified: "Последняя проверка",
    save: "Сохранить",
    saved: "Сохранено",
    prepare: "Подготовить заявку",
    openSource: "Открыть исходный источник",
    dismiss: "Мне не подходит",
    aiWritten: "Сформулировано ИИ по вычисленной выше разбивке.",
    scoreExplainer:
      "Вычислено кодом из вашего профиля и этой публикации. Одни и те же данные всегда дают одну и ту же оценку.",
  },

  errors: {
    llmUnavailable:
      "Сейчас не удалось выполнить анализ. Ваши сохранённые данные в безопасности.",
    searchUnavailable:
      "Живой поиск возможностей временно недоступен. Показаны проверенные сохранённые возможности.",
    ragUnavailable:
      "Проверка актуальности источников недоступна, поэтому мы не будем отвечать по памяти.",
    generic: "Что-то пошло не так. Ваши сохранённые данные в безопасности.",
  },

  validation: {
    wouldNotHaveFound:
      "Показал ли вам Money You're Missing возможность, которую вы, скорее всего, не нашли бы сами?",
    wouldPursue: "Стали бы вы этим действительно заниматься?",
    yes: "Да",
    partly: "Отчасти",
    maybe: "Возможно",
    no: "Нет",
    thanks: "Спасибо. Так мы понимаем, работает ли продукт.",
  },

  disclaimers: {
    tax: "Справочная информация из указанных источников. Это не Steuerberatung и не Rechtsberatung.",
    grow: "Иллюстративное допущение — не прогноз.",
    family:
      "Универсально правильного ответа нет. Какое оформление счёта подходит семье, зависит от обстоятельств, которые этот продукт оценить не может.",
    investment:
      "Справочная информация о том, как устроены эти инструменты. Это не инвестиционная рекомендация и не совет по какому-либо продукту.",
  },

  partialTranslation:
    "Интерфейс переведён. Объяснения совпадений, проверка по Германии и юридические цитаты формируются бэкендом и остаются на английском.",
};

export const dictionaries: Record<Locale, Copy> = { en, ru };

/**
 * The English dictionary, for the places that genuinely have no locale in
 * scope: `generateMetadata`, tests, and anything rendered before the user's
 * choice is known. Anything rendered to a reader should use `useCopy()`.
 */
export const copy = en;
