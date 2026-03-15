"""LangChain agent that picks moves strategically for a fighter (PS-compatible)."""

import json
import re

from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate

from battle_royal.models.profile import Fighter


STRATEGY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are the battle AI for {fighter_name} ({pokemon_species}). "
        "Pick the best move for the current turn.\n\n"
        "Your available moves:\n{moves_info}\n\n"
        "RULES:\n"
        "- Respond with ONLY a single number (1, 2, 3, or 4) for the move index\n"
        "- Prefer high-power STAB moves when possible\n"
        "- If HP is low, pick your strongest move\n"
        "- Consider type coverage\n"
        "- Status moves (basePower=0) should only be used on turn 1-2\n"
        "- No other text, just the number",
    ),
    (
        "human",
        "Turn {turn}\n"
        "Your HP: {my_hp:.0f}% | Opponent HP: {opp_hp:.0f}%\n"
        "Pick your move (1-4):",
    ),
])


def pick_move(
    fighter: Fighter,
    available_moves: list,
    my_hp_pct: float,
    opp_hp_pct: float,
    turn: int,
    api_key: str,
) -> int:
    """Pick a move index (1-4) for the current turn.

    Args:
        fighter: The fighter making the choice
        available_moves: List of move dicts from PS request (with keys: move, id, pp, disabled)
        my_hp_pct: Fighter's current HP percentage
        opp_hp_pct: Opponent's current HP percentage
        turn: Current turn number
        api_key: Mistral API key

    Returns:
        Move index (1-4) for PS command format
    """
    if not available_moves:
        return 1

    # Hard override: if HP below 30%, pick highest base power move
    if my_hp_pct < 30:
        best_idx = 1
        best_power = 0
        for i, move in enumerate(available_moves):
            # Get basePower from fighter's mapping moves
            mapping_move = _find_mapping_move(fighter, move.get("id", ""))
            power = mapping_move.basePower if mapping_move else 0
            if power > best_power and not move.get("disabled", False):
                best_power = power
                best_idx = i + 1
        return best_idx

    # Build moves info for the LLM
    moves_info_parts = []
    for i, move in enumerate(available_moves):
        mapping_move = _find_mapping_move(fighter, move.get("id", ""))
        power = mapping_move.basePower if mapping_move else "?"
        move_type = mapping_move.type if mapping_move else "?"
        category = mapping_move.category if mapping_move else "?"
        disabled = " (DISABLED)" if move.get("disabled", False) else ""
        pp = f"{move.get('pp', '?')}/{move.get('maxpp', '?')}"

        moves_info_parts.append(
            f"  {i+1}. {move.get('move', '?')} — Type: {move_type}, "
            f"Power: {power}, Category: {category}, PP: {pp}{disabled}"
        )

    moves_info = "\n".join(moves_info_parts)

    llm = ChatMistralAI(
        model="mistral-small-latest",
        api_key=api_key,
        temperature=0.3,
    )
    chain = STRATEGY_PROMPT | llm

    result = chain.invoke({
        "fighter_name": fighter.display_name,
        "pokemon_species": fighter.pokemon_species,
        "moves_info": moves_info,
        "turn": turn,
        "my_hp": my_hp_pct,
        "opp_hp": opp_hp_pct,
    })

    # Parse the response — should be just a number 1-4
    text = result.content.strip()
    match = re.search(r"[1-4]", text)
    if match:
        choice = int(match.group())
        # Validate the choice isn't disabled
        if choice <= len(available_moves) and not available_moves[choice - 1].get("disabled"):
            return choice

    # Fallback: pick first non-disabled damaging move
    for i, move in enumerate(available_moves):
        if not move.get("disabled", False):
            mapping_move = _find_mapping_move(fighter, move.get("id", ""))
            if mapping_move and mapping_move.basePower > 0:
                return i + 1

    # Last resort: pick first non-disabled move
    for i, move in enumerate(available_moves):
        if not move.get("disabled", False):
            return i + 1

    return 1


def _find_mapping_move(fighter: Fighter, move_id: str):
    """Find the BattleMove in the fighter's mapping by PS move ID."""
    for m in fighter.mapping.moves:
        if m.id.lower().replace(" ", "") == move_id.lower().replace(" ", ""):
            return m
    return None
