"""LangChain agent that picks moves strategically for a fighter."""

import json

from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate

from battle_royal.models.profile import Fighter, BattleMove


STRATEGY_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are the battle AI for {fighter_name}, a {fighter_types} type fighter. "
        "You must pick the best move for the current situation.\n\n"
        "Your moves:\n{moves_info}\n\n"
        "RULES (follow strictly):\n"
        "- You MUST pick a damaging move (power > 0) most of the time\n"
        "- Status moves (power=0) can only be used ONCE per battle, on turn 1 or 2\n"
        "- If your HP is below 50%, ALWAYS pick your highest-power damaging move\n"
        "- Consider type effectiveness against opponent's types ({opponent_types})\n"
        "- High power moves have lower accuracy — use them when desperate\n"
        "- NEVER pick the same move more than 3 times in a row\n\n"
        "Respond with ONLY the exact move name as a string. No other text.",
    ),
    (
        "human",
        "Turn {turn}: Your HP: {my_hp}/{my_max_hp} | "
        "Opponent ({opponent_name}) HP: {opp_hp}/{opp_max_hp}\n"
        "{extra_context}"
        "Pick your move.",
    ),
])


def pick_move(
    fighter: Fighter,
    opponent: Fighter,
    turn: int,
    api_key: str,
) -> BattleMove:
    """Have the fighter agent pick the best move for this turn."""
    # Hard override: if HP is below 50%, always pick highest-power move
    hp_pct = fighter.current_hp / fighter.stats.hp
    damaging_moves = [m for m in fighter.moves if m.power > 0]

    if hp_pct < 0.5 and damaging_moves:
        return max(damaging_moves, key=lambda m: m.power)

    llm = ChatMistralAI(
        model="mistral-small-latest",
        api_key=api_key,
        temperature=0.5,
    )
    chain = STRATEGY_PROMPT | llm

    moves_info = "\n".join(
        f"- {m.name}: power={m.power}, accuracy={m.accuracy}, "
        f"category={m.category}, type={m.move_type}"
        + (f", effect={m.stat_effect}" if m.stat_effect else "")
        for m in fighter.moves
    )

    extra = ""
    if turn > 2:
        extra = "IMPORTANT: Do NOT pick a status move (power=0). Pick a damaging move.\n"

    result = chain.invoke({
        "fighter_name": fighter.display_name,
        "fighter_types": "/".join(fighter.stats.types),
        "moves_info": moves_info,
        "opponent_types": "/".join(opponent.stats.types),
        "turn": turn,
        "my_hp": fighter.current_hp,
        "my_max_hp": fighter.stats.hp,
        "opponent_name": opponent.display_name,
        "opp_hp": opponent.current_hp,
        "opp_max_hp": opponent.stats.hp,
        "extra_context": extra,
    })

    chosen_name = result.content.strip().strip('"').strip("'")

    # Match to actual move
    for move in fighter.moves:
        if move.name.lower() == chosen_name.lower():
            # Don't allow status moves after turn 2
            if move.power == 0 and turn > 2 and damaging_moves:
                break
            return move

    # Fallback: pick a random damaging move for variety
    if damaging_moves:
        import random
        return random.choice(damaging_moves)
    return fighter.moves[0]
