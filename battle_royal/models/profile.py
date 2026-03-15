"""Pydantic models for the LinkedIn Battle Royal system (Pokemon Showdown integration)."""

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


# --- Pokemon Showdown-Compatible Battle Models ---

POKEMON_TYPES = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic",
    "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
]

POKEMON_NATURES = [
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky",
]


class EVSpread(BaseModel):
    """EV distribution for a Pokemon (max 510 total, max 252 per stat)."""
    hp: int = Field(ge=0, le=252, default=0)
    atk: int = Field(ge=0, le=252, default=0)
    def_: int = Field(ge=0, le=252, default=0, alias="def")
    spa: int = Field(ge=0, le=252, default=0)
    spd: int = Field(ge=0, le=252, default=0)
    spe: int = Field(ge=0, le=252, default=0)

    model_config = {"populate_by_name": True}


class BattleMove(BaseModel):
    """A custom battle move in Pokemon Showdown format."""
    id: str = Field(description="PS move ID (lowercase, no spaces)")
    name: str = Field(description="Display name of the move")
    pp: int = Field(ge=1, le=40, default=10)
    type: str = Field(description="One of the 18 Pokemon types")
    category: str = Field(description="Physical, Special, or Status")
    basePower: int = Field(ge=0, le=120, default=0, description="0 for status moves")
    accuracy: int = Field(ge=50, le=100, default=100)
    description: str = ""


class PokemonMapping(BaseModel):
    """Maps a person's profile to a Pokemon species."""
    species: str = Field(description="Pokemon species name (e.g., 'Alakazam')")
    reasoning: str = Field(description="Why this Pokemon was chosen for this person")
    moves: List[BattleMove] = Field(min_length=4, max_length=4)
    evs: EVSpread
    nature: str = Field(description="One of 25 Pokemon natures")
    ability: str = Field(default="", description="Pokemon ability (blank for default)")


class Fighter(BaseModel):
    """A fully built fighter ready for PS battle."""
    profile: FighterProfile
    pokemon_species: str = Field(description="Pokemon species (e.g., 'Alakazam')")
    mapping: PokemonMapping
    level: int = Field(default=50, ge=1, le=100)

    @property
    def display_name(self) -> str:
        return self.profile.name

    @property
    def pokemon_display(self) -> str:
        return f"{self.profile.name}'s {self.pokemon_species}"


class BattleConfig(BaseModel):
    """Pokemon Showdown battle format configuration."""
    format_id: str = "gen9customgame"
    level: int = 50


class PSEvent(BaseModel):
    """A parsed Pokemon Showdown protocol event."""
    type: str = Field(description="Event type (e.g., 'move', 'damage', 'win')")
    player: str = ""
    pokemon: str = ""
    details: str = ""
    extra: Dict = Field(default_factory=dict)


class PSTurnAction(BaseModel):
    """A single action within a turn (move, damage, etc.)."""
    action: str = Field(description="'move', 'damage', 'supereffective', 'resisted', 'crit', 'faint', 'miss'")
    player: str = ""
    move_name: str = ""
    move_type: str = ""
    target: str = ""
    hp_text: str = ""
    message: str = ""


class PSTurnResult(BaseModel):
    """Parsed results from a single PS turn."""
    turn_number: int
    actions: List[PSTurnAction] = Field(default_factory=list)
    p1_hp_pct: float = 100.0
    p2_hp_pct: float = 100.0
    narration: str = ""
    raw_output: str = ""


class PSBattleLog(BaseModel):
    """Complete battle record from a PS battle."""
    fighter_1: Dict
    fighter_2: Dict
    turns: List[PSTurnResult] = Field(default_factory=list)
    winner: str = ""
    winner_player: str = ""
    final_narration: str = ""
    raw_protocol: str = ""
