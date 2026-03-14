# LinkedIn Battle Royal

A Pokemon-style battle system where professionals fight each other based on their CV/LinkedIn PDF data. Drop in two PDF resumes, and the system extracts profiles, calculates battle stats, generates signature moves, and runs a fully narrated turn-based battle — all powered by Mistral AI via LangChain.

## How It Works

The system follows a 4-stage pipeline for each fighter, then runs a battle engine:

```
PDF  -->  Raw Text  -->  Structured Profile  -->  Stats + Types + Moves  -->  Fighter
                pdfplumber        Mistral LLM           Deterministic +          Battle!
                                                         Mistral LLM
```

### Stage 1: PDF Text Extraction

`battle_royal/extraction/pdf_parser.py` uses **pdfplumber** to pull raw text from any CV or LinkedIn-exported PDF. Handles multi-column layouts, different formatting styles, and varying PDF structures.

### Stage 2: LLM Profile Extraction

`battle_royal/extraction/profile_extractor.py` sends the raw text to **Mistral** (via LangChain's `PydanticOutputParser`) and gets back a structured `FighterProfile` containing:

- Name, headline, summary
- Skills, experiences (with years), education
- Certifications, languages, publications, awards, projects

No brittle regex — the LLM handles all format variations between traditional CVs and LinkedIn exports.

### Stage 3: Stats, Types, and Moves

**Stats** (`battle_royal/battle/stats.py`) — deterministic calculation, no LLM needed:

| Stat | Range | Source |
|------|-------|--------|
| HP | 100-300 | Total years of experience |
| Attack | 1-100 | Technical/hard skill count |
| Defense | 1-100 | Education level + certifications |
| Sp. Attack | 1-100 | Publications, awards, notable projects |
| Sp. Defense | 1-100 | Leadership roles, languages |
| Speed | 1-100 | Career progression velocity (roles per year) |

**Types** (`battle_royal/battle/moves.py`) — Mistral picks 2 types from:

`ML-Research`, `Full-Stack`, `Data-Science`, `DevOps`, `Security`, `Mobile`, `Cloud`, `Blockchain`, `Design`, `Management`, `Education`, `Consulting`

**Moves** (`battle_royal/battle/moves.py`) — Mistral generates 4 signature moves per fighter, each referencing real skills/projects from their CV. Moves have power, accuracy, category (physical/special/status), and a type for effectiveness calculations.

Example moves generated from a real CV:
```
- DeepMind Dive        (pow:85  acc:85  special)
- Graph Neural Strike   (pow:75  acc:90  physical)
- Variational Volley    (pow:95  acc:75  special)
- Explainable Aura      (pow:0   acc:100 status, +sp_attack)
```

### Stage 4: Battle Engine

`battle_royal/battle/engine.py` runs the turn-based fight:

1. **Speed** determines who goes first
2. Each turn: **Fighter Agent** (LangChain + Mistral) picks a move strategically based on HP, type matchups, and battle state
3. **Damage calculation** uses a simplified Pokemon formula factoring in attack/defense stats, type effectiveness (1.5x super effective, 0.5x not very effective), critical hits (6.25% chance, 1.5x), and a random factor (0.85-1.0)
4. **Accuracy check** — high-power moves can miss
5. **Status moves** apply stat buffs/debuffs (capped to early turns)
6. **Referee Agent** (LangChain + Mistral Large) narrates each turn in Pokemon-commentator style
7. Battle ends when a fighter hits 0 HP (or after 50 turns, highest HP% wins)
8. Referee delivers a final verdict

### Type Effectiveness

A full type chart is implemented. Each type has 2 types it's super effective against and 2 it's not very effective against. Examples:

- `ML-Research` is super effective vs `Data-Science` and `Education`
- `DevOps` is super effective vs `Full-Stack` and `Cloud`
- `Security` is super effective vs `DevOps` and `Blockchain`

### LangChain Agents

| Agent | Model | Role |
|-------|-------|------|
| Profile Extractor | `mistral-small-latest` | PDF text -> structured profile |
| Type Assigner | `mistral-small-latest` | Pick 2 types from profile |
| Move Generator | `mistral-small-latest` | Create 4 signature moves |
| Fighter Agent (x2) | `mistral-small-latest` | Strategic move selection each turn |
| Referee Agent | `mistral-large-latest` | Battle narration + final verdict |

## Project Structure

```
Linkdin-BattleRoyal/
├── main.py                              # CLI entry point
├── .env                                 # MISTRAL_API_KEY=your-key
├── .env.example
├── requirements.txt
├── battle_log.json                      # Output from last battle
│
├── cvs/                                 # Drop PDF resumes here
│   ├── AntAci CV.pdf
│   ├── kiranlinkedincv.pdf
│   └── Profile (1).pdf
│
└── battle_royal/                        # Main package
    ├── models/
    │   └── profile.py                   # Pydantic models (FighterProfile,
    │                                    #   FighterStats, BattleMove, Fighter,
    │                                    #   TurnResult, BattleLog)
    ├── extraction/
    │   ├── pdf_parser.py                # pdfplumber text extraction
    │   └── profile_extractor.py         # Mistral structured extraction
    ├── battle/
    │   ├── stats.py                     # Deterministic stat calculation
    │   ├── moves.py                     # Type effectiveness + LLM move generation
    │   ├── engine.py                    # Turn-based battle loop
    │   └── narrator.py                  # Re-exports RefereeAgent
    └── agents/
        ├── fighter_agent.py             # LangChain agent — picks moves
        └── referee_agent.py             # LangChain agent — narrates battles
```

## Setup

**Requirements**: Python 3.9+, a [Mistral API key](https://console.mistral.ai/)

```bash
# Install dependencies
pip3 install -r requirements.txt

# Set your API key
cp .env.example .env
# Edit .env and add your MISTRAL_API_KEY
```

## Usage

```bash
# Battle the first 2 PDFs in cvs/ automatically
python3 main.py

# Battle two specific PDFs
python3 main.py "cvs/AntAci CV.pdf" "cvs/kiranlinkedincv.pdf"

# Just extract and display a fighter's profile, stats, and moves (no battle)
python3 main.py --extract "cvs/AntAci CV.pdf"
```

Add your own CVs by dropping PDF files into the `cvs/` folder.

## Output

The battle prints a full narrated log to the console and saves a structured JSON to `battle_log.json`:

```json
{
  "fighter_1": {
    "name": "Antonio Aciobanitei",
    "types": ["ML-Research", "Data-Science"],
    "hp": 136, "attack": 70, "defense": 25,
    "sp_attack": 54, "sp_defense": 8, "speed": 60,
    "moves": ["DeepMind Dive", "Graph Neural Strike", "Variational Volley", "Explainable Aura"]
  },
  "fighter_2": { ... },
  "turns": [
    {
      "turn_number": 1,
      "attacker": "Antonio Aciobanitei",
      "defender": "Kiran Ruby",
      "move_used": "Explainable Aura",
      "damage": 0,
      "effectiveness": "status",
      "critical_hit": false,
      "attacker_hp": 136,
      "defender_hp": 208,
      "narration": "What a tactical play from the data-driven dynamo..."
    }
  ],
  "winner": "Kiran Ruby",
  "final_narration": "Ladies and gentlemen, what an electrifying clash..."
}
```

This JSON is designed for a future Pokemon Showdown-style frontend visualization.

## Dependencies

| Package | Purpose |
|---------|---------|
| `pdfplumber` | PDF text extraction |
| `langchain` | LLM orchestration framework |
| `langchain-mistralai` | Mistral AI integration for LangChain |
| `pydantic` | Data models and structured LLM output parsing |
| `python-dotenv` | Load API key from `.env` |
