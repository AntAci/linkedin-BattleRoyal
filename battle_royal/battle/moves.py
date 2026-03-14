"""LLM-based move generation and type effectiveness for battle."""

import json
import re
from typing import Dict, List

from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate

from battle_royal.models.profile import (
    FighterProfile,
    FighterStats,
    BattleMove,
    VALID_TYPES,
)

# --- Type effectiveness chart (attacker -> defender -> multiplier) ---
# Super effective = 1.5, not very effective = 0.5, neutral = 1.0

def _extract_json(text: str) -> str:
    """Strip markdown code fences and extract JSON from LLM output."""
    # Try to find JSON inside ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    # Try to find a JSON array or object directly
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]
    return text.strip()


SUPER_EFFECTIVE: Dict[str, List[str]] = {
    "ML-Research": ["Data-Science", "Education"],
    "Full-Stack": ["Mobile", "Design"],
    "Data-Science": ["Consulting", "Management"],
    "DevOps": ["Full-Stack", "Cloud"],
    "Security": ["DevOps", "Blockchain"],
    "Mobile": ["Design", "Consulting"],
    "Cloud": ["Full-Stack", "Data-Science"],
    "Blockchain": ["Cloud", "Security"],
    "Design": ["Management", "Education"],
    "Management": ["DevOps", "Security"],
    "Education": ["ML-Research", "Consulting"],
    "Consulting": ["Management", "Mobile"],
}

NOT_VERY_EFFECTIVE: Dict[str, List[str]] = {
    "ML-Research": ["Security", "Blockchain"],
    "Full-Stack": ["DevOps", "Cloud"],
    "Data-Science": ["ML-Research", "Security"],
    "DevOps": ["Security", "Management"],
    "Security": ["ML-Research", "Education"],
    "Mobile": ["Full-Stack", "Cloud"],
    "Cloud": ["DevOps", "Blockchain"],
    "Blockchain": ["Data-Science", "Consulting"],
    "Design": ["Full-Stack", "Mobile"],
    "Management": ["Consulting", "Education"],
    "Education": ["Design", "Management"],
    "Consulting": ["Data-Science", "Education"],
}


def get_type_effectiveness(attack_type: str, defender_types: List[str]) -> float:
    """Calculate type effectiveness multiplier."""
    multiplier = 1.0
    for def_type in defender_types:
        if def_type in SUPER_EFFECTIVE.get(attack_type, []):
            multiplier *= 1.5
        elif def_type in NOT_VERY_EFFECTIVE.get(attack_type, []):
            multiplier *= 0.5
    return multiplier


# --- LLM type assignment ---

TYPE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You assign professional 'types' to fighters based on their profile. "
        "Pick exactly 2 types from this list: {valid_types}\n\n"
        "Respond with ONLY a JSON array of 2 strings, e.g. [\"ML-Research\", \"Education\"]. "
        "No other text.",
    ),
    (
        "human",
        "Name: {name}\nHeadline: {headline}\nSkills: {skills}",
    ),
])


def assign_types(profile: FighterProfile, api_key: str) -> List[str]:
    """Use LLM to pick 2 types for a fighter based on their profile."""
    llm = ChatMistralAI(
        model="mistral-small-latest",
        api_key=api_key,
        temperature=0,
    )
    chain = TYPE_PROMPT | llm

    result = chain.invoke({
        "valid_types": ", ".join(VALID_TYPES),
        "name": profile.name,
        "headline": profile.headline,
        "skills": ", ".join(profile.skills[:20]),
    })

    types = json.loads(_extract_json(result.content))
    # Validate
    types = [t for t in types if t in VALID_TYPES][:2]
    if not types:
        types = ["Full-Stack"]
    return types


# --- LLM move generation ---

MOVES_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You create Pokemon-style battle moves for professional fighters. "
        "Each move should reference real skills, projects, or experiences "
        "from the fighter's CV.\n\n"
        "Generate exactly 4 moves. For each move provide:\n"
        "- name: creative move name referencing their CV\n"
        "- description: one line flavor text\n"
        "- power: 0-120 (0 for status/buff moves, 60-90 for normal attacks, 90-120 for signature moves)\n"
        "- accuracy: 50-100 (higher power = lower accuracy)\n"
        "- category: 'physical' (uses Attack stat), 'special' (uses Sp.Attack), or 'status' (buff/debuff)\n"
        "- move_type: one of {valid_types}\n"
        "- stat_effect: null for damaging moves, or '+defense'/'-speed'/'+attack' etc for status moves\n\n"
        "Rules:\n"
        "- At least 2 damaging moves and at most 1 status move\n"
        "- move_type should match the fighter's types when possible\n"
        "- Make moves creative and fun!\n\n"
        "Respond with ONLY a JSON array of 4 move objects. No other text.",
    ),
    (
        "human",
        "Fighter: {name}\n"
        "Types: {types}\n"
        "Headline: {headline}\n"
        "Skills: {skills}\n"
        "Experience highlights: {experience}\n"
        "Education: {education}\n"
        "Projects: {projects}",
    ),
])


def generate_moves(
    profile: FighterProfile,
    stats: FighterStats,
    api_key: str,
) -> List[BattleMove]:
    """Generate 4 signature battle moves for a fighter using LLM."""
    llm = ChatMistralAI(
        model="mistral-small-latest",
        api_key=api_key,
        temperature=0.7,
    )
    chain = MOVES_PROMPT | llm

    # Summarize experience for the prompt
    exp_highlights = "; ".join(
        f"{e.title} at {e.company}" for e in profile.experiences[:5]
    )
    edu_summary = "; ".join(
        f"{e.degree} in {e.field_of_study} from {e.school}"
        for e in profile.educations[:3]
    )

    result = chain.invoke({
        "valid_types": ", ".join(VALID_TYPES),
        "name": profile.name,
        "types": ", ".join(stats.types),
        "headline": profile.headline,
        "skills": ", ".join(profile.skills[:15]),
        "experience": exp_highlights or "Not specified",
        "education": edu_summary or "Not specified",
        "projects": ", ".join(profile.projects[:5]) or "Not specified",
    })

    raw_moves = json.loads(_extract_json(result.content))
    moves = [BattleMove(**m) for m in raw_moves[:4]]

    # Ensure we have exactly 4
    while len(moves) < 4:
        moves.append(BattleMove(
            name="Struggle",
            description="A desperate attack",
            power=50,
            accuracy=100,
            category="physical",
            move_type=stats.types[0],
        ))

    return moves[:4]
