"""LangChain agent that narrates Pokemon Showdown battles."""

from typing import List

from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate


NARRATE_TURN_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an excited Pokemon battle commentator narrating a fight "
        "between two professionals battling as real Pokemon. Keep it fun, dramatic, "
        "and reference both the Pokemon and the person's real name. 2-3 sentences max.",
    ),
    (
        "human",
        "Turn {turn}:\n"
        "{moves_summary}\n"
        "Damage: {damage_summary}\n"
        "Effectiveness: {effectiveness}\n"
        "Critical hit: {critical_hits}\n"
        "Faints: {faints}\n"
        "{p1_name}: {p1_hp_pct:.0f}% HP\n"
        "{p2_name}: {p2_hp_pct:.0f}% HP\n"
        "Narrate this moment!",
    ),
])


FINAL_NARRATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a Pokemon battle commentator delivering the final "
        "verdict. Be dramatic and celebratory. Reference both the Pokemon species "
        "and the person's real name. 3-4 sentences.",
    ),
    (
        "human",
        "The battle between {fighter1} and {fighter2} is over!\n"
        "Winner: {winner}\n"
        "Loser: {loser}\n"
        "Total turns: {total_turns}\n"
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
        moves_summary: str,
        damage_summary: str,
        effectiveness: str,
        critical_hits: bool,
        faints: List[str],
        p1_name: str,
        p2_name: str,
        p1_hp_pct: float,
        p2_hp_pct: float,
    ) -> str:
        chain = NARRATE_TURN_PROMPT | self.llm
        result = chain.invoke({
            "turn": turn,
            "moves_summary": moves_summary,
            "damage_summary": damage_summary,
            "effectiveness": effectiveness,
            "critical_hits": "Yes!" if critical_hits else "No",
            "faints": ", ".join(faints) if faints else "None",
            "p1_name": p1_name,
            "p2_name": p2_name,
            "p1_hp_pct": p1_hp_pct,
            "p2_hp_pct": p2_hp_pct,
        })
        return result.content

    def final_narration(
        self,
        fighter1: str,
        fighter2: str,
        winner: str,
        loser: str,
        total_turns: int,
    ) -> str:
        chain = FINAL_NARRATION_PROMPT | self.llm
        result = chain.invoke({
            "fighter1": fighter1,
            "fighter2": fighter2,
            "winner": winner,
            "loser": loser,
            "total_turns": total_turns,
        })
        return result.content
