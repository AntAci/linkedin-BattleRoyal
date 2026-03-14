"""Deterministic stat calculation from a FighterProfile."""

from datetime import datetime

from battle_royal.models.profile import FighterProfile, FighterStats


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _total_years_experience(profile: FighterProfile) -> float:
    """Sum up years across all experiences."""
    now = datetime.now().year
    total = 0.0
    for exp in profile.experiences:
        start = exp.start_year or now
        end = exp.end_year or now
        total += max(0, end - start)
    return total


def _career_velocity(profile: FighterProfile) -> float:
    """How quickly did the person climb? Roles per year of career."""
    years = _total_years_experience(profile)
    if years <= 0:
        return 0.0
    return len(profile.experiences) / years


LEADERSHIP_KEYWORDS = {
    "lead", "head", "manager", "director", "vp", "cto", "ceo", "coo",
    "principal", "senior", "founder", "co-founder", "chief", "president",
}


def _leadership_score(profile: FighterProfile) -> int:
    """Score based on leadership titles and soft skill indicators."""
    score = 0
    for exp in profile.experiences:
        title_lower = exp.title.lower()
        for kw in LEADERSHIP_KEYWORDS:
            if kw in title_lower:
                score += 8
                break
    score += len(profile.languages) * 5
    return score


EDUCATION_SCORE = {
    "phd": 40, "doctorate": 40, "doctor": 40,
    "master": 30, "msc": 30, "mba": 30, "ma ": 30,
    "bachelor": 20, "bsc": 20, "ba ": 20, "beng": 20,
    "associate": 10, "diploma": 10, "certificate": 8,
}


def _education_score(profile: FighterProfile) -> int:
    """Score education level + certifications."""
    score = 0
    for edu in profile.educations:
        degree_lower = (edu.degree + " " + edu.field_of_study).lower()
        for keyword, points in EDUCATION_SCORE.items():
            if keyword in degree_lower:
                score += points
                break
        else:
            score += 5  # some education but unrecognized degree
    score += len(profile.certifications) * 6
    return score


def calculate_stats(profile: FighterProfile) -> FighterStats:
    """Calculate deterministic battle stats from a FighterProfile.

    Types are NOT set here — they require an LLM call (see moves.py).
    Types are temporarily set to ["Full-Stack"] as a placeholder.
    """
    years = _total_years_experience(profile)

    # HP: 100-300 based on total experience years
    hp = _clamp(int(100 + years * 12), 100, 300)

    # Attack: technical skill count & depth
    attack = _clamp(int(len(profile.skills) * 3.5), 1, 100)

    # Defense: education + certifications
    defense = _clamp(_education_score(profile), 1, 100)

    # Sp.Attack: publications, awards, notable projects
    sp_attack_raw = (
        len(profile.publications) * 12
        + len(profile.awards) * 10
        + len(profile.projects) * 6
    )
    sp_attack = _clamp(sp_attack_raw, 1, 100)

    # Sp.Defense: leadership, languages, soft skills
    sp_defense = _clamp(_leadership_score(profile), 1, 100)

    # Speed: career progression velocity
    velocity = _career_velocity(profile)
    speed = _clamp(int(velocity * 30 + 20), 1, 100)

    return FighterStats(
        hp=hp,
        attack=attack,
        defense=defense,
        sp_attack=sp_attack,
        sp_defense=sp_defense,
        speed=speed,
        types=["Full-Stack"],  # placeholder — overwritten by assign_types()
    )
