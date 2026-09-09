"""Reading a CV without a model: what it must find, and what it must not.

The second half matters more. This module exists because a previous decision
refused to parse CVs heuristically at all, on the grounds that a wrong guess
costs the user more than an empty field. These tests hold the narrowed version
to that same standard: recognition of a closed vocabulary, and no inference.
"""

from __future__ import annotations

from app.domain.enums import LanguageLevel, SkillEvidence, SkillLevel
from app.services.cv_recognition import (
    VOCABULARY,
    draft_by_recognition,
    recognise_languages,
    recognise_skills,
)

CV = """Katerina Kuznetsova
Senior Data Engineer at Hansa Logistik Werke, Berlin

EXPERIENCE
2019 - 2024   Data Engineer
  Built ETL pipelines with Airflow and dbt on Databricks.
  PostgreSQL, Python, PySpark. Led the migration to AWS.

LANGUAGES
German C1
English C2
Russian - native
"""


def names(text: str) -> set[str]:
    return {skill.name for skill in recognise_skills(text)}


# ------------------------------------------------------- what it finds


def test_it_recognises_skills_that_are_literally_written_down() -> None:
    found = names(CV)
    assert {"airflow", "dbt", "databricks", "postgresql", "python", "pyspark", "aws"} <= found


def test_a_recognised_skill_is_unconfirmed_and_has_no_level() -> None:
    """The document proves the word is there, not how good anyone is at it."""
    skill = next(s for s in recognise_skills(CV) if s.name == "python")
    assert skill.confirmed is False
    assert skill.level is SkillLevel.UNKNOWN
    assert skill.evidence is SkillEvidence.CV


def test_levels_are_read_only_where_they_are_printed() -> None:
    by_code = {language.code: language.level for language in recognise_languages(CV)}
    assert by_code["de"] is LanguageLevel.C1
    assert by_code["en"] is LanguageLevel.C2
    # The profile has its own NATIVE level, so the CV's word is kept rather
    # than flattened into C2.
    assert by_code["ru"] is LanguageLevel.NATIVE


def test_a_language_with_no_stated_level_stays_unknown() -> None:
    assert recognise_languages("Languages: Spanish")[0].level is LanguageLevel.UNKNOWN


def test_a_level_on_another_line_is_not_borrowed() -> None:
    """Reading a level from two lines away is the guess this module avoids."""
    found = recognise_languages("LANGUAGES\nSpanish\n\nCertificate: C2 in something else")
    assert found[0].level is LanguageLevel.UNKNOWN


# --------------------------------------------------- what it refuses to do


def test_structure_is_never_extracted() -> None:
    """The original objection, still standing: no role, employer, dates, city."""
    draft = draft_by_recognition(CV)
    assert draft.professional.current_role is None
    assert draft.professional.years_experience is None
    assert draft.general.city is None
    assert draft.professional.education == []
    assert "your current role" in draft.not_found
    assert "years of experience" in draft.not_found


def test_it_does_not_invent_a_skill_from_a_related_word() -> None:
    """"Pipelines" does not make somebody an Airflow user."""
    assert "airflow" not in names("I have built data pipelines for years.")


def test_a_word_inside_another_word_is_not_a_match() -> None:
    assert names("Our goal was to reorganise the algorithm.") == set()


def test_a_language_name_is_not_also_proposed_as_a_skill() -> None:
    """The profile has a field for each; one word must not fill both."""
    draft = draft_by_recognition("LANGUAGES\nGerman C1\n")
    assert "german" not in {skill.name for skill in draft.professional.skills}
    assert [language.code for language in draft.professional.languages] == ["de"]


def test_the_vocabulary_is_the_matchers_own() -> None:
    """Recognition and matching cannot drift apart if they share a list."""
    from app.services.skills_graph import _CLUSTERS

    known = {name for cluster in _CLUSTERS for name in cluster}
    assert set(VOCABULARY) <= known


# ------------------------------------------------------------ the draft


def test_the_draft_says_how_it_was_produced() -> None:
    notes = " ".join(draft_by_recognition(CV).extraction_notes).lower()
    assert "no language model" in notes
    assert "nothing was inferred" in notes
    assert "were not extracted" in notes


def test_recognising_nothing_is_stated_as_recognising_nothing() -> None:
    """Not "your CV is empty" - a different and false claim about the document."""
    notes = " ".join(draft_by_recognition("A document about gardening.").extraction_notes)
    assert "did not recognise any" in notes
    assert "not that your CV lacks them" in notes


def test_the_original_text_is_kept_for_the_user_to_work_from() -> None:
    assert any("Hansa Logistik" in note for note in draft_by_recognition(CV).extraction_notes)


def test_recognition_is_deterministic() -> None:
    assert draft_by_recognition(CV) == draft_by_recognition(CV)
