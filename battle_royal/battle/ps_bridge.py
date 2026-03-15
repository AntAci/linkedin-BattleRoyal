"""Bridge between Python and Pokemon Showdown's Node.js battle engine."""

import json
import subprocess
from pathlib import Path
from typing import Optional

from battle_royal.models.profile import (
    Fighter,
    BattleConfig,
    BattleMove,
    PokemonMapping,
)

PS_DIR = Path(__file__).resolve().parent.parent.parent / "pokemon-showdown"
CUSTOM_BATTLE_SCRIPT = PS_DIR / "custom-battle.js"


def _move_id(move: BattleMove) -> str:
    """Convert move name to PS move ID format."""
    return move.id.lower().replace(" ", "").replace("-", "").replace("_", "")


def build_packed_team(fighter: Fighter) -> str:
    """Build a PS packed team string for a single fighter.

    Format: NICKNAME|SPECIES|ITEM|ABILITY|MOVES|NATURE|EVS|GENDER|IVS|SHINY|LEVEL|...
    """
    mapping = fighter.mapping
    species = mapping.species
    nickname = fighter.profile.name
    move_ids = ",".join(_move_id(m) for m in mapping.moves)
    evs = mapping.evs
    ev_str = f"{evs.hp},{evs.atk},{evs.def_},{evs.spa},{evs.spd},{evs.spe}"
    ability = mapping.ability or ""
    nature = mapping.nature
    level = fighter.level

    packed = f"{nickname}|{species}||{ability}|{move_ids}|{nature}|{ev_str}|||||{level}|"
    return packed


def build_custom_moves_data(mapping: PokemonMapping) -> list:
    """Convert mapping moves to the format expected by custom-battle.js."""
    moves_data = []
    for move in mapping.moves:
        moves_data.append({
            "id": _move_id(move),
            "name": move.name,
            "type": move.type,
            "category": move.category,
            "basePower": move.basePower,
            "accuracy": move.accuracy,
            "pp": move.pp,
            "description": move.description,
        })
    return moves_data


class PSBattleProcess:
    """Manages a Pokemon Showdown battle subprocess.

    Protocol (matches custom-battle.js):
      Python sends: start command, then turn commands (both moves at once)
      Node sends: init (protocol + requests), then turn_result per turn
    """

    def __init__(self, config: Optional[BattleConfig] = None):
        self.config = config or BattleConfig()
        self.process: Optional[subprocess.Popen] = None
        self._all_protocol_lines: list = []

    def start_battle(self, fighter1: Fighter, fighter2: Fighter) -> dict:
        """Start a PS battle subprocess and return initial state.

        Returns dict with keys: p1_request, p2_request, protocol_lines
        """
        if not CUSTOM_BATTLE_SCRIPT.exists():
            raise FileNotFoundError(
                f"custom-battle.js not found at {CUSTOM_BATTLE_SCRIPT}. "
                "Make sure Pokemon Showdown is cloned and built."
            )

        self.process = subprocess.Popen(
            ["node", str(CUSTOM_BATTLE_SCRIPT)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(PS_DIR),
        )

        team1 = build_packed_team(fighter1)
        team2 = build_packed_team(fighter2)

        start_cmd = {
            "type": "start",
            "format": self.config.format_id,
            "p1": {
                "name": fighter1.profile.name,
                "team": team1,
                "customMoves": build_custom_moves_data(fighter1.mapping),
            },
            "p2": {
                "name": fighter2.profile.name,
                "team": team2,
                "customMoves": build_custom_moves_data(fighter2.mapping),
            },
        }

        self._send(start_cmd)

        # Read the init response
        msg = self._read()
        if msg is None or msg.get("type") == "error":
            error_msg = msg.get("message", "Unknown error") if msg else "No response from PS"
            raise RuntimeError(f"PS start error: {error_msg}")

        if msg["type"] != "init":
            raise RuntimeError(f"Expected init, got: {msg['type']}")

        protocol_lines = msg.get("protocol", [])
        self._all_protocol_lines.extend(protocol_lines)

        return {
            "p1_request": msg.get("p1_request"),
            "p2_request": msg.get("p2_request"),
            "protocol_lines": protocol_lines,
        }

    def send_turn(self, p1_choice: str, p2_choice: str) -> dict:
        """Send move choices for both players and return turn results.

        Args:
            p1_choice: e.g., "move 1", "move 2"
            p2_choice: e.g., "move 1", "move 2"

        Returns dict with keys: protocol_lines, p1_request, p2_request,
                                ended, winner
        """
        self._send({
            "type": "turn",
            "p1": p1_choice,
            "p2": p2_choice,
        })

        msg = self._read()
        if msg is None:
            return {"protocol_lines": [], "p1_request": None,
                    "p2_request": None, "ended": True, "winner": ""}

        if msg.get("type") == "error":
            raise RuntimeError(f"PS error: {msg.get('message')}")

        protocol_lines = msg.get("protocol", [])
        self._all_protocol_lines.extend(protocol_lines)

        return {
            "protocol_lines": protocol_lines,
            "p1_request": msg.get("p1_request"),
            "p2_request": msg.get("p2_request"),
            "ended": msg.get("ended", False),
            "winner": msg.get("winner", ""),
        }

    def close(self):
        """Terminate the subprocess."""
        if self.process:
            try:
                self.process.stdin.close()
            except Exception:
                pass
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    @property
    def all_protocol(self) -> list:
        return self._all_protocol_lines

    def _send(self, data: dict):
        line = json.dumps(data) + "\n"
        self.process.stdin.write(line)
        self.process.stdin.flush()

    def _read(self) -> Optional[dict]:
        try:
            line = self.process.stdout.readline()
            if not line:
                return None
            return json.loads(line.strip())
        except (json.JSONDecodeError, ValueError):
            return None


def parse_protocol_lines(lines: list) -> dict:
    """Parse PS protocol lines into structured battle events."""
    events = {
        "moves": [],
        "damage": [],
        "effectiveness": [],
        "crits": [],
        "faint": [],
        "winner": "",
        "turn": 0,
        "boost": [],
    }

    for line in lines:
        parts = line.split("|")
        if len(parts) < 2:
            continue

        event_type = parts[1] if len(parts) > 1 else ""

        if event_type == "move" and len(parts) >= 4:
            events["moves"].append({
                "pokemon": parts[2].strip(),
                "move": parts[3].strip(),
                "target": parts[4].strip() if len(parts) > 4 else "",
            })
        elif event_type == "-damage" and len(parts) >= 4:
            events["damage"].append({
                "pokemon": parts[2].strip(),
                "hp": parts[3].strip(),
            })
        elif event_type == "-supereffective":
            events["effectiveness"].append("super effective")
        elif event_type == "-resisted":
            events["effectiveness"].append("not very effective")
        elif event_type == "-crit":
            events["crits"].append(parts[2].strip() if len(parts) > 2 else "")
        elif event_type == "faint" and len(parts) >= 3:
            events["faint"].append(parts[2].strip())
        elif event_type == "win" and len(parts) >= 3:
            events["winner"] = parts[2].strip()
        elif event_type == "turn" and len(parts) >= 3:
            try:
                events["turn"] = int(parts[2].strip())
            except ValueError:
                pass
        elif event_type in ("-boost", "-unboost") and len(parts) >= 5:
            events["boost"].append({
                "pokemon": parts[2].strip(),
                "stat": parts[3].strip(),
                "amount": parts[4].strip(),
                "type": event_type,
            })

    return events


def extract_hp_pct(request: Optional[dict]) -> float:
    """Extract HP percentage from a PS request object."""
    if not request:
        return 100.0
    try:
        pokemon = request["side"]["pokemon"][0]
        condition = pokemon["condition"]
        if condition == "0 fnt":
            return 0.0
        hp_parts = condition.split("/")
        current = float(hp_parts[0])
        maximum = float(hp_parts[1].split(" ")[0])
        return (current / maximum) * 100.0
    except (KeyError, IndexError, ValueError, ZeroDivisionError):
        return 100.0


def extract_available_moves(request: Optional[dict]) -> list:
    """Extract available moves from a PS request object."""
    if not request:
        return []
    try:
        return request["active"][0]["moves"]
    except (KeyError, IndexError):
        return []
