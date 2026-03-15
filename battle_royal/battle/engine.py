"""Battle engine using Pokemon Showdown subprocess."""

from battle_royal.models.profile import Fighter, PSTurnResult, PSTurnAction, PSBattleLog
from battle_royal.battle.ps_bridge import (
    PSBattleProcess,
    parse_protocol_lines,
    extract_hp_pct,
    extract_available_moves,
)
from battle_royal.agents.fighter_agent import pick_move
from battle_royal.agents.referee_agent import RefereeAgent

MAX_TURNS = 50


def _fighter_summary(fighter: Fighter) -> dict:
    return {
        "name": fighter.display_name,
        "pokemon": fighter.pokemon_species,
        "pokemon_display": fighter.pokemon_display,
        "moves": [m.name for m in fighter.mapping.moves],
        "nature": fighter.mapping.nature,
        "ability": fighter.mapping.ability,
        "reasoning": fighter.mapping.reasoning,
    }


def _build_turn_actions(events: dict, fighter1: Fighter, fighter2: Fighter) -> list:
    """Convert parsed protocol events into a sequence of PSTurnAction for replay."""
    actions = []

    # We need to interleave moves and their effects.
    # PS protocol order: move -> effectiveness -> crit -> damage -> (repeat for player 2)
    # We reconstruct this from the parsed events.

    move_idx = 0
    damage_idx = 0
    eff_idx = 0
    crit_idx = 0

    for move_ev in events["moves"]:
        pokemon = move_ev["pokemon"]
        is_p1 = "p1a:" in pokemon
        player = "p1" if is_p1 else "p2"
        attacker = fighter1 if is_p1 else fighter2
        defender = fighter2 if is_p1 else fighter1

        # Look up move type from fighter's mapping
        move_type = ""
        for m in attacker.mapping.moves:
            if m.name.lower() == move_ev["move"].lower():
                move_type = m.type
                break

        actions.append(PSTurnAction(
            action="move",
            player=player,
            move_name=move_ev["move"],
            move_type=move_type,
            target=defender.pokemon_species,
            message=f"{attacker.pokemon_display} used {move_ev['move']}!",
        ))

        # Check for effectiveness after this move
        if eff_idx < len(events["effectiveness"]):
            eff = events["effectiveness"][eff_idx]
            eff_idx += 1
            actions.append(PSTurnAction(
                action="supereffective" if "super" in eff else "resisted",
                player=player,
                message=f"It's {eff}!",
            ))

        # Check for crit
        if crit_idx < len(events["crits"]):
            actions.append(PSTurnAction(
                action="crit",
                player=player,
                message="A critical hit!",
            ))
            crit_idx += 1

        # Damage to defender
        if damage_idx < len(events["damage"]):
            dmg = events["damage"][damage_idx]
            damage_idx += 1
            target_player = "p2" if is_p1 else "p1"
            actions.append(PSTurnAction(
                action="damage",
                player=target_player,
                hp_text=dmg["hp"],
            ))

    # Faints
    for faint_poke in events["faint"]:
        is_p1_faint = "p1a:" in faint_poke
        player = "p1" if is_p1_faint else "p2"
        fainted_fighter = fighter1 if is_p1_faint else fighter2
        actions.append(PSTurnAction(
            action="faint",
            player=player,
            message=f"{fainted_fighter.pokemon_display} fainted!",
        ))

    return actions


def run_battle(
    fighter1: Fighter,
    fighter2: Fighter,
    api_key: str,
    verbose: bool = True,
) -> PSBattleLog:
    """Run a full battle between two fighters using Pokemon Showdown."""
    referee = RefereeAgent(api_key)
    battle_log = PSBattleLog(
        fighter_1=_fighter_summary(fighter1),
        fighter_2=_fighter_summary(fighter2),
    )

    ps = PSBattleProcess()

    try:
        if verbose:
            print(f"\n  Starting Pokemon Showdown battle...")
            print(f"  {fighter1.pokemon_display} vs {fighter2.pokemon_display}")

        init = ps.start_battle(fighter1, fighter2)
        init_events = parse_protocol_lines(init["protocol_lines"])

        if verbose:
            print(f"  Battle started! Turn 1")

        turn = 0
        p1_request = init.get("p1_request")
        p2_request = init.get("p2_request")

        while turn < MAX_TURNS:
            turn += 1

            p1_moves = extract_available_moves(p1_request)
            p2_moves = extract_available_moves(p2_request)
            p1_hp_pct = extract_hp_pct(p1_request)
            p2_hp_pct = extract_hp_pct(p2_request)

            p1_choice_idx = pick_move(
                fighter=fighter1,
                available_moves=p1_moves,
                my_hp_pct=p1_hp_pct,
                opp_hp_pct=p2_hp_pct,
                turn=turn,
                api_key=api_key,
            )
            p2_choice_idx = pick_move(
                fighter=fighter2,
                available_moves=p2_moves,
                my_hp_pct=p2_hp_pct,
                opp_hp_pct=p1_hp_pct,
                turn=turn,
                api_key=api_key,
            )

            result = ps.send_turn(f"move {p1_choice_idx}", f"move {p2_choice_idx}")
            protocol_lines = result["protocol_lines"]
            events = parse_protocol_lines(protocol_lines)

            p1_request = result.get("p1_request") or p1_request
            p2_request = result.get("p2_request") or p2_request

            new_p1_hp = extract_hp_pct(p1_request)
            new_p2_hp = extract_hp_pct(p2_request)

            moves_used = events["moves"]
            effectiveness_list = events["effectiveness"]
            crits = events["crits"]
            faints = events["faint"]
            damages = events["damage"]

            # Build structured actions for visual replay
            turn_actions = _build_turn_actions(events, fighter1, fighter2)

            # Narrate
            narration_context = _build_narration_context(
                turn, fighter1, fighter2, moves_used, damages,
                effectiveness_list, crits, faints,
                new_p1_hp, new_p2_hp,
            )
            narration = referee.narrate_turn(**narration_context)

            turn_result = PSTurnResult(
                turn_number=turn,
                actions=turn_actions,
                p1_hp_pct=new_p1_hp,
                p2_hp_pct=new_p2_hp,
                narration=narration,
                raw_output="\n".join(protocol_lines),
            )
            battle_log.turns.append(turn_result)

            if verbose:
                print(f"\n--- Turn {turn} ---")
                for move_ev in moves_used:
                    print(f"  {move_ev['pokemon']} used {move_ev['move']}!")
                for dmg in damages:
                    print(f"  {dmg['pokemon']}: {dmg['hp']}")
                if effectiveness_list:
                    for eff in effectiveness_list:
                        print(f"  It's {eff}!")
                if crits:
                    print(f"  Critical hit!")
                print(f"  {fighter1.pokemon_display}: {new_p1_hp:.0f}%")
                print(f"  {fighter2.pokemon_display}: {new_p2_hp:.0f}%")
                print(f"  >> {narration}")

            if result["ended"] or events["winner"]:
                winner_name = events["winner"] or ""
                if result["winner"] == "p1" or winner_name == fighter1.profile.name:
                    battle_log.winner = fighter1.display_name
                    battle_log.winner_player = "p1"
                elif result["winner"] == "p2" or winner_name == fighter2.profile.name:
                    battle_log.winner = fighter2.display_name
                    battle_log.winner_player = "p2"
                break

            if faints:
                break

        if not battle_log.winner:
            final_p1_hp = extract_hp_pct(p1_request)
            final_p2_hp = extract_hp_pct(p2_request)
            if final_p1_hp >= final_p2_hp:
                battle_log.winner = fighter1.display_name
                battle_log.winner_player = "p1"
            else:
                battle_log.winner = fighter2.display_name
                battle_log.winner_player = "p2"

        winner_fighter = fighter1 if battle_log.winner_player == "p1" else fighter2
        loser_fighter = fighter2 if battle_log.winner_player == "p1" else fighter1

        battle_log.final_narration = referee.final_narration(
            fighter1=fighter1.pokemon_display,
            fighter2=fighter2.pokemon_display,
            winner=winner_fighter.pokemon_display,
            loser=loser_fighter.pokemon_display,
            total_turns=len(battle_log.turns),
        )

        battle_log.raw_protocol = "\n".join(ps.all_protocol)

        if verbose:
            print(f"\n{'='*50}")
            print(f"WINNER: {battle_log.winner} ({winner_fighter.pokemon_species})!")
            print(f"{'='*50}")
            print(battle_log.final_narration)

    finally:
        ps.close()

    return battle_log


def _build_narration_context(
    turn, fighter1, fighter2, moves_used, damages,
    effectiveness_list, crits, faints, p1_hp, p2_hp,
) -> dict:
    move_summaries = []
    for move_ev in moves_used:
        pokemon = move_ev["pokemon"]
        if "p1a:" in pokemon:
            attacker_name = fighter1.pokemon_display
        else:
            attacker_name = fighter2.pokemon_display
        move_summaries.append(f"{attacker_name} used {move_ev['move']}!")

    damage_summaries = [f"{d['pokemon']}: {d['hp']}" for d in damages]

    return {
        "turn": turn,
        "moves_summary": " ".join(move_summaries),
        "damage_summary": " ".join(damage_summaries),
        "effectiveness": ", ".join(effectiveness_list) if effectiveness_list else "neutral",
        "critical_hits": len(crits) > 0,
        "faints": faints,
        "p1_name": fighter1.pokemon_display,
        "p2_name": fighter2.pokemon_display,
        "p1_hp_pct": p1_hp,
        "p2_hp_pct": p2_hp,
    }
