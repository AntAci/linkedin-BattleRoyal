"""LangChain agent that narrates battles Pokemon-commentator style."""

from typing import List

from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate


NARRATE_TURN_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an excited Pokemon battle commentator narrating a fight "
        "between two professional fighters. Keep it fun, dramatic, and "
        "reference their real professional backgrounds. 2-3 sentences max.",
    ),
    (
        "human",
        "Turn {turn}: {attacker} used {move_name} against {defender}!\n"
        "Damage dealt: {damage} (effectiveness: {effectiveness})\n"
        "Critical hit: {critical}\n"
        "{attacker} HP: {attacker_hp}/{attacker_max_hp}\n"
        "{defender} HP: {defender_hp}/{defender_max_hp}\n"
        "Narrate this moment!",
    ),
])


FINAL_NARRATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a Pokemon battle commentator delivering the final "
        "verdict. Be dramatic and celebratory. Reference both fighters' "
        "professional backgrounds. 3-4 sentences.",
    ),
    (
        "human",
        "The battle between {fighter1} ({types1}) and {fighter2} ({types2}) "
        "is over!\n"
        "Winner: {winner}\n"
        "Total turns: {total_turns}\n"
        "Winner's remaining HP: {winner_hp}/{winner_max_hp}\n"
        "Deliver the final narration!",
    ),
])


class RefereeAgent:
    """Narrates battle turns and delivers final verdicts."""

    def __init__(self, api_key: str):
        self.llm = ChatMistralAI(
            model="mistral-large-latest",
            api_key=api_key,
            temperature=0.8,
        )

    def narrate_turn(
        self,
        turn: int,
        attacker: str,
        defender: str,
        move_name: str,
        damage: int,
        effectiveness: str,
        critical: bool,
        attacker_hp: int,
        attacker_max_hp: int,
        defender_hp: int,
        defender_max_hp: int,
    ) -> str:
        chain = NARRATE_TURN_PROMPT | self.llm
        result = chain.invoke({
            "turn": turn,
            "attacker": attacker,
            "defender": defender,
            "move_name": move_name,
            "damage": damage,
            "effectiveness": effectiveness,
            "critical": "Yes!" if critical else "No",
            "attacker_hp": attacker_hp,
            "attacker_max_hp": attacker_max_hp,
            "defender_hp": defender_hp,
            "defender_max_hp": defender_max_hp,
        })
        return result.content

    def final_narration(
        self,
        fighter1: str,
        types1: List[str],
        fighter2: str,
        types2: List[str],
        winner: str,
        total_turns: int,
        winner_hp: int,
        winner_max_hp: int,
    ) -> str:
        chain = FINAL_NARRATION_PROMPT | self.llm
        result = chain.invoke({
            "fighter1": fighter1,
            "types1": "/".join(types1),
            "fighter2": fighter2,
            "types2": "/".join(types2),
            "winner": winner,
            "total_turns": total_turns,
            "winner_hp": winner_hp,
            "winner_max_hp": winner_max_hp,
        })
        return result.content
