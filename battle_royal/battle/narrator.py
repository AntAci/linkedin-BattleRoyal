"""Thin wrapper - narration is handled by referee_agent.py."""

# The RefereeAgent in battle_royal/agents/referee_agent.py handles all
# narration. This module exists as a namespace placeholder per the
# project structure, but all narration logic lives in the referee agent.

from battle_royal.agents.referee_agent import RefereeAgent

__all__ = ["RefereeAgent"]
