"""Pydantic models for the LinkedIn Battle Royal system."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# --- Profile Extraction Models ---

class Experience(BaseModel):
    company: str = ""
    title: str = ""
    location: str = ""
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    description: str = ""


class Education(BaseModel):
    school: str = ""
    degree: str = ""
    field_of_study: str = ""
    start_year: Optional[int] = None
    end_year: Optional[int] = None


class FighterProfile(BaseModel):
    """Structured profile extracted from a CV/LinkedIn PDF."""
    name: str
    headline: str = ""
    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    experiences: List[Experience] = Field(default_factory=list)
    educations: List[Education] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    publications: List[str] = Field(default_factory=list)
    awards: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)


# --- Battle Models ---

VALID_TYPES = [
    "ML-Research", "Full-Stack", "Data-Science", "DevOps", "Security",
    "Mobile", "Cloud", "Blockchain", "Design", "Management",
    "Education", "Consulting",
]


class FighterStats(BaseModel):
    """Pokemon-style stats derived from a profile."""
    hp: int = Field(ge=100, le=300, description="Based on total years of experience")
    attack: int = Field(ge=1, le=100, description="Technical/hard skill count & depth")
    defense: int = Field(ge=1, le=100, description="Education level + certifications")
    sp_attack: int = Field(ge=1, le=100, description="Publications, awards, notable projects")
    sp_defense: int = Field(ge=1, le=100, description="Leadership roles, languages, soft skills")
    speed: int = Field(ge=1, le=100, description="Career progression velocity")
    types: List[str] = Field(min_length=1, max_length=2)


class BattleMove(BaseModel):
    """A signature battle move for a fighter."""
    name: str
    description: str = ""
    power: int = Field(ge=0, le=120, description="0 for status moves")
    accuracy: int = Field(ge=50, le=100, default=100)
    category: str = Field(description="physical, special, or status")
    move_type: str = Field(description="One of the VALID_TYPES")
    stat_effect: Optional[str] = Field(
        default=None,
        description="e.g. '+defense', '-speed' for status moves",
    )


class Fighter(BaseModel):
    """A fully built fighter ready for battle."""
    profile: FighterProfile
    stats: FighterStats
    moves: List[BattleMove] = Field(min_length=4, max_length=4)
    current_hp: int = 0

    def model_post_init(self, _context):
        if self.current_hp == 0:
            self.current_hp = self.stats.hp

    @property
    def is_fainted(self) -> bool:
        return self.current_hp <= 0

    @property
    def display_name(self) -> str:
        return self.profile.name


class TurnResult(BaseModel):
    """Result of a single battle turn."""
    turn_number: int
    attacker: str
    defender: str
    move_used: str
    damage: int = 0
    effectiveness: str = "neutral"
    critical_hit: bool = False
    attacker_hp: int
    defender_hp: int
    narration: str = ""


class BattleLog(BaseModel):
    """Complete battle record for frontend consumption."""
    fighter_1: Dict
    fighter_2: Dict
    turns: List[TurnResult] = Field(default_factory=list)
    winner: str = ""
    final_narration: str = ""
