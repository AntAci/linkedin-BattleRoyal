#!/usr/bin/env python3
"""LinkedIn Battle Royal — Web UI."""

import json
import os
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_file

load_dotenv()

from battle_royal.extraction.pdf_parser import extract_text_from_pdf
from battle_royal.extraction.profile_extractor import extract_profile
from battle_royal.extraction.pokemon_mapper import map_profile_to_pokemon
from battle_royal.battle.engine import run_battle
from battle_royal.models.profile import Fighter
from battle_royal.audio.tts import get_elevenlabs_config, synthesize_speech

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

UPLOAD_DIR = Path(tempfile.mkdtemp(prefix="battle_royal_"))
PS_DIR = Path(__file__).resolve().parent / "pokemon-showdown"

# In-memory store for battle state (battle_id -> state dict)
battles = {}


def get_api_key() -> str:
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY not set")
    return key


def check_ps():
    """Ensure Pokemon Showdown is ready."""
    dist = PS_DIR / "dist" / "sim"
    if not dist.exists():
        if not PS_DIR.exists():
            subprocess.run(
                ["git", "clone",
                 "https://github.com/smogon/pokemon-showdown.git",
                 str(PS_DIR)],
                check=True,
            )
        subprocess.run(["npm", "install"], cwd=str(PS_DIR), check=True)
        subprocess.run(["node", "build"], cwd=str(PS_DIR), check=True)


def build_fighter(pdf_path: str, api_key: str) -> Fighter:
    text = extract_text_from_pdf(pdf_path)
    profile = extract_profile(text, api_key)
    mapping = map_profile_to_pokemon(profile, api_key)
    return Fighter(
        profile=profile,
        pokemon_species=mapping.species,
        mapping=mapping,
    )


def run_battle_async(battle_id: str, path1: str, path2: str):
    """Run the full battle pipeline in a background thread."""
    state = battles[battle_id]
    try:
        api_key = get_api_key()

        # Build fighter 1
        state["status"] = "Extracting Fighter 1 profile..."
        state["step"] = 1
        fighter1 = build_fighter(path1, api_key)
        state["fighter1"] = {
            "name": fighter1.display_name,
            "pokemon": fighter1.pokemon_species,
            "pokemon_display": fighter1.pokemon_display,
            "headline": fighter1.profile.headline,
            "reasoning": fighter1.mapping.reasoning,
            "nature": fighter1.mapping.nature,
            "ability": fighter1.mapping.ability,
            "moves": [
                {"name": m.name, "type": m.type, "category": m.category,
                 "basePower": m.basePower, "accuracy": m.accuracy}
                for m in fighter1.mapping.moves
            ],
        }

        # Build fighter 2
        state["status"] = "Extracting Fighter 2 profile..."
        state["step"] = 2
        fighter2 = build_fighter(path2, api_key)
        state["fighter2"] = {
            "name": fighter2.display_name,
            "pokemon": fighter2.pokemon_species,
            "pokemon_display": fighter2.pokemon_display,
            "headline": fighter2.profile.headline,
            "reasoning": fighter2.mapping.reasoning,
            "nature": fighter2.mapping.nature,
            "ability": fighter2.mapping.ability,
            "moves": [
                {"name": m.name, "type": m.type, "category": m.category,
                 "basePower": m.basePower, "accuracy": m.accuracy}
                for m in fighter2.mapping.moves
            ],
        }

        # Run battle
        state["status"] = "Battle in progress..."
        state["step"] = 3
        battle_log = run_battle(fighter1, fighter2, api_key, verbose=False)

        # Generate TTS audio for narrations (if ElevenLabs is configured)
        el_key, el_voice = get_elevenlabs_config()
        audio_map = {}  # turn_number -> True (indicates audio available)
        if el_key:
            state["status"] = "Generating commentary audio..."
            audio_dir = UPLOAD_DIR / f"{battle_id}_audio"
            audio_dir.mkdir(exist_ok=True)

            for t in battle_log.turns:
                if t.narration:
                    audio_path = audio_dir / f"turn_{t.turn_number}.mp3"
                    ok = synthesize_speech(t.narration, str(audio_path), el_key, el_voice)
                    if ok:
                        audio_map[t.turn_number] = True

            # Final narration audio
            if battle_log.final_narration:
                audio_path = audio_dir / "final.mp3"
                ok = synthesize_speech(battle_log.final_narration, str(audio_path), el_key, el_voice)
                if ok:
                    audio_map["final"] = True

        state["status"] = "complete"
        state["step"] = 4
        state["has_audio"] = bool(audio_map)
        state["audio_turns"] = list(audio_map.keys())
        state["result"] = {
            "winner": battle_log.winner,
            "winner_player": battle_log.winner_player,
            "total_turns": len(battle_log.turns),
            "final_narration": battle_log.final_narration,
            "turns": [
                {
                    "turn_number": t.turn_number,
                    "p1_hp_pct": round(t.p1_hp_pct, 1),
                    "p2_hp_pct": round(t.p2_hp_pct, 1),
                    "narration": t.narration,
                    "actions": [
                        {
                            "action": a.action,
                            "player": a.player,
                            "move_name": a.move_name,
                            "move_type": a.move_type,
                            "target": a.target,
                            "hp_text": a.hp_text,
                            "message": a.message,
                        }
                        for a in t.actions
                    ],
                }
                for t in battle_log.turns
            ],
        }

    except Exception as e:
        state["status"] = "error"
        state["error"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/battle", methods=["POST"])
def start_battle():
    """Upload two PDFs and start a battle."""
    if "pdf1" not in request.files or "pdf2" not in request.files:
        return jsonify({"error": "Two PDF files required"}), 400

    pdf1 = request.files["pdf1"]
    pdf2 = request.files["pdf2"]

    if not pdf1.filename or not pdf2.filename:
        return jsonify({"error": "Both files must be selected"}), 400

    # Save uploaded files
    battle_id = str(uuid.uuid4())
    path1 = UPLOAD_DIR / f"{battle_id}_1.pdf"
    path2 = UPLOAD_DIR / f"{battle_id}_2.pdf"
    pdf1.save(str(path1))
    pdf2.save(str(path2))

    # Initialize battle state
    battles[battle_id] = {
        "status": "Starting...",
        "step": 0,
        "fighter1": None,
        "fighter2": None,
        "result": None,
        "error": None,
    }

    # Run in background thread
    thread = threading.Thread(
        target=run_battle_async,
        args=(battle_id, str(path1), str(path2)),
        daemon=True,
    )
    thread.start()

    return jsonify({"battle_id": battle_id})


@app.route("/api/battle/<battle_id>")
def battle_status(battle_id):
    """Poll battle progress."""
    state = battles.get(battle_id)
    if not state:
        return jsonify({"error": "Battle not found"}), 404
    return jsonify(state)


@app.route("/api/battle/<battle_id>/audio/<turn_key>")
def battle_audio(battle_id, turn_key):
    """Serve TTS audio for a specific turn or 'final'."""
    state = battles.get(battle_id)
    if not state:
        return jsonify({"error": "Battle not found"}), 404

    if turn_key == "final":
        filename = "final.mp3"
    else:
        filename = f"turn_{turn_key}.mp3"

    audio_path = UPLOAD_DIR / f"{battle_id}_audio" / filename
    if not audio_path.exists():
        return jsonify({"error": "Audio not found"}), 404

    return send_file(str(audio_path), mimetype="audio/mpeg")


if __name__ == "__main__":
    check_ps()
    app.run(debug=True, port=5000)
