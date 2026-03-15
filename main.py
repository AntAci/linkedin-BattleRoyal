#!/usr/bin/env python3
"""LinkedIn Battle Royal — CLI entry point (Pokemon Showdown edition).

Usage:
    python3 main.py                          # Battle first 2 PDFs in cvs/
    python3 main.py "cvs/A.pdf" "cvs/B.pdf"  # Battle specific PDFs
    python3 main.py --extract "cvs/A.pdf"    # Just extract & show profile + Pokemon mapping
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from battle_royal.extraction.pdf_parser import extract_text_from_pdf
from battle_royal.extraction.profile_extractor import extract_profile
from battle_royal.extraction.pokemon_mapper import map_profile_to_pokemon
from battle_royal.battle.engine import run_battle
from battle_royal.models.profile import Fighter

CVS_DIR = Path("cvs")
PS_DIR = Path(__file__).resolve().parent / "pokemon-showdown"


def get_api_key() -> str:
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        print("ERROR: Set MISTRAL_API_KEY in .env or environment")
        sys.exit(1)
    return key


def check_ps_installation():
    """Verify Pokemon Showdown is cloned and built."""
    if not PS_DIR.exists():
        print("Pokemon Showdown not found. Cloning...")
        subprocess.run(
            ["git", "clone", "https://github.com/smogon/pokemon-showdown.git",
             str(PS_DIR)],
            check=True,
        )

    dist_dir = PS_DIR / "dist" / "sim"
    if not dist_dir.exists():
        print("Building Pokemon Showdown...")
        subprocess.run(["npm", "install"], cwd=str(PS_DIR), check=True)
        subprocess.run(["node", "build"], cwd=str(PS_DIR), check=True)

    custom_script = PS_DIR / "custom-battle.js"
    if not custom_script.exists():
        print(f"ERROR: {custom_script} not found!")
        sys.exit(1)


def build_fighter(pdf_path: str, api_key: str) -> Fighter:
    """Full pipeline: PDF -> profile -> Pokemon mapping -> Fighter."""
    print(f"\n{'='*50}")
    print(f"Loading fighter from: {pdf_path}")
    print(f"{'='*50}")

    # Step 1: Extract text
    print("  [1/3] Extracting text from PDF...")
    text = extract_text_from_pdf(pdf_path)
    print(f"  Extracted {len(text)} characters")

    # Step 2: LLM profile extraction
    print("  [2/3] Extracting structured profile (Mistral)...")
    profile = extract_profile(text, api_key)
    print(f"  Name: {profile.name}")
    print(f"  Headline: {profile.headline}")
    print(f"  Skills: {len(profile.skills)} | Experiences: {len(profile.experiences)}")

    # Step 3: Map to Pokemon
    print("  [3/3] Mapping profile to Pokemon (Mistral)...")
    mapping = map_profile_to_pokemon(profile, api_key)
    print(f"  Pokemon: {mapping.species}")
    print(f"  Reasoning: {mapping.reasoning}")
    print(f"  Nature: {mapping.nature} | Ability: {mapping.ability}")
    print(f"  Moves:")
    for m in mapping.moves:
        print(f"    - {m.name} ({m.type}, {m.category}, BP:{m.basePower}, Acc:{m.accuracy})")

    return Fighter(
        profile=profile,
        pokemon_species=mapping.species,
        mapping=mapping,
    )


def main():
    api_key = get_api_key()

    # Check PS is ready
    check_ps_installation()

    # --extract mode: just show profile for a single PDF
    if "--extract" in sys.argv:
        idx = sys.argv.index("--extract")
        if idx + 1 >= len(sys.argv):
            print("Usage: python main.py --extract <pdf_path>")
            sys.exit(1)
        fighter = build_fighter(sys.argv[idx + 1], api_key)
        print("\n" + json.dumps(fighter.model_dump(), indent=2, default=str))
        return

    # Battle mode: pick 2 PDFs
    if len(sys.argv) >= 3:
        pdf1, pdf2 = sys.argv[1], sys.argv[2]
    else:
        pdfs = sorted(CVS_DIR.glob("*.pdf"))
        if len(pdfs) < 2:
            print(f"Need at least 2 PDFs in {CVS_DIR}/. Found: {len(pdfs)}")
            sys.exit(1)
        pdf1, pdf2 = str(pdfs[0]), str(pdfs[1])

    # Build fighters
    fighter1 = build_fighter(pdf1, api_key)
    fighter2 = build_fighter(pdf2, api_key)

    # BATTLE!
    print(f"\n{'#'*50}")
    print(f"  BATTLE: {fighter1.pokemon_display}")
    print(f"      vs  {fighter2.pokemon_display}")
    print(f"{'#'*50}")

    battle_log = run_battle(fighter1, fighter2, api_key, verbose=True)

    # Save battle log JSON
    output_path = "battle_log.json"
    with open(output_path, "w") as f:
        json.dump(battle_log.model_dump(), f, indent=2, default=str)
    print(f"\nBattle log saved to {output_path}")


if __name__ == "__main__":
    main()
