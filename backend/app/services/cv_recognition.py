"""Reading a CV without a language model, by recognition only.

`cv_parsing.draft_from_text` deliberately extracted nothing on the no-model
path, and its reasoning still stands:

    A regex CV parser produces confident nonsense - mistaking a company for a
    job title, a postcode for a year - and the user then has to find and
    correct each error, which is worse than typing the fields themselves.

That objection is about **inferring structure**: deciding which line is a job
title, which number is a year, which organisation employed whom. Every one of
those is a judgement, and a wrong judgement is expensive because the user has
to spot it before they can fix it.

This module does something different, and narrower. It **recognises members of
a closed vocabulary** the product already maintains: the 91 skills in the
skills graph, and languages with CEFR levels. Finding the literal string
"PostgreSQL" in a document and proposing the known skill `postgresql` cannot
mistake a company for a job title, because it is not deciding anything - it is
looking words up in a list that a human wrote.

So the rule here is exact:

* **Recognised, never inferred.** A skill is proposed only if its own name
  appears in the document. No synonyms the model might invent, no "this person
  writes about pipelines so they probably know Airflow".
* **Structure is still not extracted.** Job title, employer, dates, years of
  experience, education and city remain `not_found`. The original objection
  covers all of them and nothing here answers it.
* **Everything is still a draft.** Nothing reaches the matcher until a human
  has confirmed it, exactly as with the model path.

Why bother: skills are the largest single component of the match score, and
languages another. Recognising them turns "we could not read anything, please
type it all" into "here is what we spotted, check it and add the rest" - on a
build with no API key at all, which is how the product is demonstrated.
"""

from __future__ import annotations

import re

from app.domain.enums import LanguageLevel, SkillEvidence, SkillLevel
from app.domain.profile import (
    GeneralInfo,
    Language,
    ProfessionalInfo,
    ProfileDraft,
    Skill,
    normalise_skill_name,
)
from app.services.skills_graph import _CLUSTERS

#: Languages worth recognising, with the spellings a CV written in English or
#: German would use. The ISO code is what the profile stores.
_LANGUAGES: dict[str, tuple[str, ...]] = {
    "de": ("german", "deutsch"),
    "en": ("english", "englisch"),
    "ru": ("russian", "russisch"),
    "fr": ("french", "franzoesisch", "französisch"),
    "es": ("spanish", "spanisch"),
    "it": ("italian", "italienisch"),
    "pl": ("polish", "polnisch"),
    "tr": ("turkish", "tuerkisch", "türkisch"),
    "uk": ("ukrainian", "ukrainisch"),
}

#: A language is not a skill: the profile has a field for each, and "German"
#: appearing in a Languages section should not also become a skill. The
#: skills vocabulary does contain 'german' for translation work, so the
#: overlap is removed rather than left to produce two entries from one word.
_LANGUAGE_NAMES: frozenset[str] = frozenset(
    spelling for spellings in _LANGUAGES.values() for spelling in spellings
)

#: The closed vocabulary. Taken from the skills graph rather than duplicated,
#: so recognition and matching can never drift apart: anything recognised here
#: is by construction a skill the matcher already understands.
VOCABULARY: tuple[str, ...] = tuple(
    sorted(
        {name for cluster in _CLUSTERS for name in cluster} - _LANGUAGE_NAMES,
        key=len,
        reverse=True,
    )
)

#: Spellings that appear in real documents for a vocabulary entry. Only exact
#: alternative renderings - never a related concept, which would be inference.
_ALIASES: dict[str, tuple[str, ...]] = {
    "javascript": ("js",),
    "typescript": ("ts",),
    "postgresql": ("postgres",),
    "kubernetes": ("k8s",),
    "machine learning": ("ml",),
    "node.js": ("nodejs", "node js"),
    "fp&a": ("fpa",),
    "user research": ("ux research",),
    "gdpr": ("dsgvo",),
    "german": ("deutsch",),
}

_CEFR = re.compile(r"\b([ABC][12])\b")
#: "Native" and its German equivalents. The profile has a NATIVE level of its
#: own, so the CV's own word is kept rather than flattened into C2.
_NATIVE = ("native", "mother tongue", "muttersprache", "erstsprache")

_LEVEL_BY_CEFR: dict[str, LanguageLevel] = {
    "A1": LanguageLevel.A1,
    "A2": LanguageLevel.A2,
    "B1": LanguageLevel.B1,
    "B2": LanguageLevel.B2,
    "C1": LanguageLevel.C1,
    "C2": LanguageLevel.C2,
}


def _word_present(needle: str, haystack: str) -> bool:
    """Whole-word, case-insensitive presence.

    Word boundaries matter more than they look: without them "r" matches every
    word containing the letter, and "go" matches "going", "algorithm" and
    "Google. The vocabulary contains short entries, so a substring search would
    be worse than useless.
    """
    return re.search(rf"(?<![\w+#.]){re.escape(needle)}(?![\w+#])", haystack) is not None


def recognise_skills(text: str) -> list[Skill]:
    """Vocabulary entries that literally appear in the document.

    Longest first, so "data engineering" is found before "data analysis" has a
    chance to claim part of it, and each stretch of text is consumed once.
    """
    lowered = text.lower()
    found: list[Skill] = []
    seen: set[str] = set()

    for name in VOCABULARY:
        spellings = (name, *_ALIASES.get(name, ()))
        if not any(_word_present(spelling, lowered) for spelling in spellings):
            continue
        key = normalise_skill_name(name)
        if key in seen:
            continue
        seen.add(key)
        found.append(
            Skill(
                name=name,
                key=key,
                # The document proves the word is there. It proves nothing at
                # all about how good the person is, so the level stays unknown
                # and the user sets it.
                level=SkillLevel.UNKNOWN,
                evidence=SkillEvidence.CV,
                confirmed=False,
            )
        )
    return found


def recognise_languages(text: str) -> list[Language]:
    """Languages named in the document, with a level only where one is printed.

    A CEFR level or the word "native" has to appear within the same line as the
    language name. Reading a level from two lines away is the kind of guess
    this module exists to avoid.
    """
    found: list[Language] = []
    seen: set[str] = set()

    for line in text.splitlines():
        lowered = line.lower()
        for code, spellings in _LANGUAGES.items():
            if code in seen:
                continue
            if not any(_word_present(spelling, lowered) for spelling in spellings):
                continue

            level = LanguageLevel.UNKNOWN
            cefr = _CEFR.search(line.upper())
            if cefr:
                level = _LEVEL_BY_CEFR.get(cefr.group(1), LanguageLevel.UNKNOWN)
            elif any(word in lowered for word in _NATIVE):
                level = LanguageLevel.NATIVE

            seen.add(code)
            found.append(Language(code=code, level=level))
    return found


def draft_by_recognition(text: str) -> ProfileDraft:
    """A draft containing only what could be recognised, and a note saying so.

    Structure is deliberately absent: no role, no employer, no dates, no years
    of experience, no city. Those need judgement, and a wrong judgement is more
    expensive than an empty field.
    """
    skills = recognise_skills(text)
    languages = recognise_languages(text)

    not_found = [
        "your current role",
        "years of experience",
        "city",
        "education",
        "certifications",
    ]

    notes = [
        "No language model is configured, so this document was read by "
        "recognition only: skills and languages this product already knows were "
        "matched against the text. Nothing was inferred.",
        "Roles, dates, employers and years of experience were not extracted. "
        "Working those out from a document needs judgement, and a wrong guess "
        "costs you more to find than the field costs to type.",
    ]
    if skills:
        notes.append(
            f"{len(skills)} skill(s) recognised. Each is unconfirmed and has no level "
            "set - the document shows the word, not how good you are at it."
        )
    else:
        notes.append(
            "No skills from our vocabulary appeared in this document. That means we "
            "did not recognise any, not that your CV lacks them."
        )
    notes.append(text[:4000])

    return ProfileDraft(
        general=GeneralInfo(),
        professional=ProfessionalInfo(skills=skills, languages=languages),
        not_found=not_found,
        extraction_notes=notes,
    )
