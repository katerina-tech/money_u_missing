"""The skills graph: a curated adjacency map, not a learned embedding.

Matching gives partial credit for a *related* skill - PySpark counts towards a
Spark requirement. The relations come from this hand-written map and from
nowhere else. That is a deliberate limitation:

* a model asked "what skills relate to Python?" will happily answer "machine
  learning", and the product would then be claiming a qualification the user
  never stated, which is exactly what it promised not to do;
* an embedding similarity would make the reason for a score unexplainable, and
  the whole matching engine is built so that every number can be justified.

The cost is coverage: the map only knows what has been written into it. That is
visible and fixable. A confidently wrong inference is neither.

Relations are symmetric and transitively closed at depth 1 only - deliberately
shallow, so credit decays rather than propagating across the graph.
"""

from __future__ import annotations

from app.domain.enums import SkillEvidence, SkillLevel
from app.domain.profile import Skill, normalise_skill_name

#: Curated clusters. Every member of a cluster is related to every other. Kept
#: as clusters rather than pairs because that is how the domain actually works
#: and it keeps the data reviewable by a human.
_CLUSTERS: tuple[tuple[str, ...], ...] = (
    ("python", "pandas", "numpy", "data engineering", "data science"),
    ("spark", "pyspark", "databricks", "data engineering", "big data"),
    ("sql", "postgresql", "mysql", "data engineering", "analytics"),
    ("airflow", "dbt", "data engineering", "etl", "data pipelines"),
    ("machine learning", "deep learning", "ai engineering", "data science", "mlops"),
    ("llm", "generative ai", "prompt engineering", "ai engineering", "rag"),
    ("aws", "azure", "gcp", "cloud architecture", "devops"),
    ("kubernetes", "docker", "devops", "platform engineering", "sre"),
    ("javascript", "typescript", "react", "frontend development", "web development"),
    ("node.js", "backend development", "api design", "javascript"),
    ("java", "spring", "backend development", "jvm"),
    ("product management", "product strategy", "roadmapping", "stakeholder management"),
    ("ux design", "ui design", "user research", "product design", "figma"),
    ("project management", "agile", "scrum", "programme management"),
    ("financial modelling", "controlling", "fp&a", "finance", "accounting"),
    ("marketing", "growth marketing", "seo", "content marketing", "performance marketing"),
    ("teaching", "training", "workshop facilitation", "mentoring", "coaching"),
    ("technical writing", "documentation", "content writing"),
    ("cybersecurity", "information security", "penetration testing", "security engineering"),
    ("data protection", "gdpr", "privacy", "compliance"),
    ("statistics", "econometrics", "data analysis", "research methods"),
    ("german", "translation", "localisation"),
)

#: Skills that imply another skill in one direction only. A Databricks user
#: certainly knows Spark; knowing Spark does not imply Databricks.
_IMPLIES: dict[str, tuple[str, ...]] = {
    "pyspark": ("spark", "python"),
    "databricks": ("spark",),
    "dbt": ("sql",),
    "pandas": ("python",),
    "react": ("javascript",),
    "typescript": ("javascript",),
    "spring": ("java",),
    "rag": ("llm",),
    "mlops": ("machine learning", "devops"),
}

_ADJACENCY: dict[str, set[str]] = {}


def _build() -> None:
    for cluster in _CLUSTERS:
        keys = [normalise_skill_name(name) for name in cluster]
        for key in keys:
            _ADJACENCY.setdefault(key, set()).update(k for k in keys if k != key)
    for source, targets in _IMPLIES.items():
        source_key = normalise_skill_name(source)
        for target in targets:
            _ADJACENCY.setdefault(source_key, set()).add(normalise_skill_name(target))


_build()


def related_keys(key: str) -> frozenset[str]:
    """Skills adjacent to ``key``. Empty when the graph does not know it."""
    return frozenset(_ADJACENCY.get(normalise_skill_name(key), frozenset()))


def implied_skills(confirmed: list[Skill]) -> list[Skill]:
    """Skills a confirmed set directly implies, returned as INFERRED and unconfirmed.

    Only the one-directional :data:`_IMPLIES` edges are used, not the whole
    cluster: cluster membership means "related", which is enough for partial
    credit in scoring but not enough to add a skill to someone's profile. Every
    result is marked inferred and unconfirmed, so the review UI shows it as a
    suggestion the user must accept.
    """
    have = {skill.key for skill in confirmed}
    suggestions: dict[str, Skill] = {}
    for skill in confirmed:
        for target in _IMPLIES.get(skill.key, ()):
            target_key = normalise_skill_name(target)
            if target_key in have or target_key in suggestions:
                continue
            suggestions[target_key] = Skill(
                name=target,
                key=target_key,
                # Level is never inherited: knowing PySpark says nothing about
                # how good someone's plain Spark is.
                level=SkillLevel.UNKNOWN,
                years=None,
                evidence=SkillEvidence.INFERRED,
                related=sorted(related_keys(target_key))[:5],
                confirmed=False,
            )
    return sorted(suggestions.values(), key=lambda s: s.key)


def enrich(skills: list[Skill]) -> list[Skill]:
    """Attach the ``related`` list to each skill, leaving everything else alone."""
    return [
        skill.model_copy(update={"related": sorted(related_keys(skill.key))[:8]})
        for skill in skills
    ]


def known_skill_count() -> int:
    """Size of the curated graph. Surfaced in docs so the limit is not hidden."""
    return len(_ADJACENCY)
