"""Map a FighterProfile to a Pokemon species, moves, EVs, and nature via LLM."""

import json
import re

from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate

from battle_royal.models.profile import (
    FighterProfile,
    PokemonMapping,
    BattleMove,
    EVSpread,
    POKEMON_TYPES,
    POKEMON_NATURES,
)


def _extract_json(text: str) -> str:
    """Strip markdown code fences and extract JSON from LLM output."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]
    return text.strip()


MAPPER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a Pokemon expert who maps real people to Pokemon based on their "
        "professional profile. You must return valid JSON.\n\n"
        "AVAILABLE POKEMON TYPES: {types}\n"
        "AVAILABLE NATURES: {natures}\n\n"
        "Given a person's CV profile, return a JSON object with:\n"
        "1. \"species\": A real Pokemon species name (any generation, must be a real Pokemon)\n"
        "2. \"reasoning\": 1-2 sentences explaining why this Pokemon fits\n"
        "3. \"moves\": Array of exactly 4 custom signature moves. Each move:\n"
        "   - \"id\": lowercase, no spaces (e.g., \"neuralnetworkblast\")\n"
        "   - \"name\": Creative name referencing their CV (e.g., \"Neural Network Blast\")\n"
        "   - \"pp\": 5-15\n"
        "   - \"type\": One of the 18 Pokemon types\n"
        "   - \"category\": \"Physical\", \"Special\", or \"Status\"\n"
        "   - \"basePower\": 0 for Status, 40-120 for attacks (higher power = lower accuracy)\n"
        "   - \"accuracy\": 50-100\n"
        "   - \"description\": One line flavor text\n"
        "   Rules for moves:\n"
        "   - At least 3 damaging moves, at most 1 status move\n"
        "   - Make moves creative and reference real skills/experiences\n"
        "   - Vary the types to give coverage\n"
        "4. \"evs\": EV spread object with keys hp/atk/def/spa/spd/spe.\n"
        "   - Total must be exactly 510\n"
        "   - Each stat max 252\n"
        "   - Distribute based on the person's strengths\n"
        "5. \"nature\": One of the 25 Pokemon natures, matching personality\n"
        "6. \"ability\": A real ability that the chosen Pokemon can have\n\n"
        "Respond with ONLY the JSON object. No other text.",
    ),
    (
        "human",
        "Map this person to a Pokemon:\n\n"
        "Name: {name}\n"
        "Headline: {headline}\n"
        "Skills: {skills}\n"
        "Experience: {experience}\n"
        "Education: {education}\n"
        "Projects: {projects}\n"
        "Summary: {summary}",
    ),
])


def map_profile_to_pokemon(
    profile: FighterProfile,
    api_key: str,
) -> PokemonMapping:
    """Use LLM to map a CV profile to a Pokemon with custom moves and EVs."""
    llm = ChatMistralAI(
        model="mistral-small-latest",
        api_key=api_key,
        temperature=0.7,
    )
    chain = MAPPER_PROMPT | llm

    exp_highlights = "; ".join(
        f"{e.title} at {e.company}" for e in profile.experiences[:5]
    )
    edu_summary = "; ".join(
        f"{e.degree} in {e.field_of_study} from {e.school}"
        for e in profile.educations[:3]
    )

    result = chain.invoke({
        "types": ", ".join(POKEMON_TYPES),
        "natures": ", ".join(POKEMON_NATURES),
        "name": profile.name,
        "headline": profile.headline,
        "skills": ", ".join(profile.skills[:20]),
        "experience": exp_highlights or "Not specified",
        "education": edu_summary or "Not specified",
        "projects": ", ".join(profile.projects[:5]) or "Not specified",
        "summary": profile.summary[:300] or "Not specified",
    })

    raw = json.loads(_extract_json(result.content))

    # Parse moves
    moves = []
    for m in raw.get("moves", [])[:4]:
        move = BattleMove(
            id=m.get("id", m.get("name", "struggle").lower().replace(" ", "")),
            name=m.get("name", "Struggle"),
            pp=max(1, min(40, m.get("pp", 10))),
            type=m.get("type", "Normal") if m.get("type") in POKEMON_TYPES else "Normal",
            category=m.get("category", "Physical"),
            basePower=max(0, min(120, m.get("basePower", 60))),
            accuracy=max(50, min(100, m.get("accuracy", 100))),
            description=m.get("description", ""),
        )
        moves.append(move)

    # Pad to 4 moves if needed
    while len(moves) < 4:
        moves.append(BattleMove(
            id="struggle",
            name="Struggle",
            pp=10,
            type="Normal",
            category="Physical",
            basePower=50,
            accuracy=100,
            description="A desperate last resort",
        ))

    # Parse EVs
    evs_raw = raw.get("evs", {})
    evs = EVSpread(
        hp=min(252, max(0, evs_raw.get("hp", 0))),
        atk=min(252, max(0, evs_raw.get("atk", 0))),
        **{"def": min(252, max(0, evs_raw.get("def", 0)))},
        spa=min(252, max(0, evs_raw.get("spa", 0))),
        spd=min(252, max(0, evs_raw.get("spd", 0))),
        spe=min(252, max(0, evs_raw.get("spe", 0))),
    )

    # Validate nature
    nature = raw.get("nature", "Serious")
    if nature not in POKEMON_NATURES:
        nature = "Serious"

    return PokemonMapping(
        species=raw.get("species", "Ditto"),
        reasoning=raw.get("reasoning", "Default mapping"),
        moves=moves,
        evs=evs,
        nature=nature,
        ability=raw.get("ability", ""),
    )
