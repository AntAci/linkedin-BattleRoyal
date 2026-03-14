#!/usr/bin/env python3
"""LinkedIn Battle Royal — CLI entry point.

Usage:
    python3 main.py                          # Battle first 2 PDFs in cvs/
    python3 main.py "cvs/A.pdf" "cvs/B.pdf"  # Battle specific PDFs
    python3 main.py --extract "cvs/A.pdf"    # Just extract & show profile
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from battle_royal.extraction.pdf_parser import extract_text_from_pdf
from battle_royal.extraction.profile_extractor import extract_profile
from battle_royal.battle.stats import calculate_stats
from battle_royal.battle.moves import assign_types, generate_moves
from battle_royal.battle.engine import run_battle
from battle_royal.models.profile import Fighter

CVS_DIR = Path("cvs")


def get_api_key() -> str:
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        print("ERROR: Set MISTRAL_API_KEY in .env or environment")
        sys.exit(1)
    return key


def build_fighter(pdf_path: str, api_key: str) -> Fighter:
    """Full pipeline: PDF -> profile -> stats -> types -> moves -> Fighter."""
    print(f"\n{'='*50}")
    print(f"Loading fighter from: {pdf_path}")
    print(f"{'='*50}")

    # Step 1: Extract text
    print("  [1/4] Extracting text from PDF...")
    text = extract_text_from_pdf(pdf_path)
    print(f"  Extracted {len(text)} characters")

    # Step 2: LLM profile extraction
    print("  [2/4] Extracting structured profile (Mistral)...")
    profile = extract_profile(text, api_key)
    print(f"  Name: {profile.name}")
    print(f"  Headline: {profile.headline}")
    print(f"  Skills: {len(profile.skills)} | Experiences: {len(profile.experiences)}")

    # Step 3: Calculate stats + assign types
    print("  [3/4] Calculating stats & assigning types...")
    stats = calculate_stats(profile)
    types = assign_types(profile, api_key)
    stats.types = types
    print(f"  Types: {'/'.join(types)}")
    print(f"  HP:{stats.hp} ATK:{stats.attack} DEF:{stats.defense} "
          f"SpA:{stats.sp_attack} SpD:{stats.sp_defense} SPD:{stats.speed}")

    # Step 4: Generate moves
    print("  [4/4] Generating battle moves (Mistral)...")
    moves = generate_moves(profile, stats, api_key)
    for m in moves:
        print(f"    - {m.name} (pow:{m.power} acc:{m.accuracy} {m.category})")

    return Fighter(profile=profile, stats=stats, moves=moves)


def main():
    api_key = get_api_key()

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
    print(f"  BATTLE: {fighter1.display_name} vs {fighter2.display_name}")
    print(f"{'#'*50}")

    battle_log = run_battle(fighter1, fighter2, api_key, verbose=True)

    # Save battle log JSON
    output_path = "battle_log.json"
    with open(output_path, "w") as f:
        json.dump(battle_log.model_dump(), f, indent=2, default=str)
    print(f"\nBattle log saved to {output_path}")


if __name__ == "__main__":
    main()
