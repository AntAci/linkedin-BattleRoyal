"""Turn-based battle engine."""

import random

from battle_royal.models.profile import Fighter, BattleMove, TurnResult, BattleLog
from battle_royal.battle.moves import get_type_effectiveness
from battle_royal.agents.fighter_agent import pick_move
from battle_royal.agents.referee_agent import RefereeAgent

MAX_TURNS = 50


def _calc_damage(
    attacker: Fighter,
    defender: Fighter,
    move: BattleMove,
) -> tuple[int, str, bool]:
    """Calculate damage for a move. Returns (damage, effectiveness, critical)."""
    if move.power == 0:
        return 0, "status", False

    # Pick relevant stats based on move category
    if move.category == "physical":
        atk_stat = attacker.stats.attack
        def_stat = defender.stats.defense
    else:  # special
        atk_stat = attacker.stats.sp_attack
        def_stat = defender.stats.sp_defense

    # Base damage formula (simplified Pokemon-style)
    base = ((2 * 50 / 5 + 2) * move.power * (atk_stat / def_stat)) / 50 + 2

    # Type effectiveness
    effectiveness_mult = get_type_effectiveness(move.move_type, defender.stats.types)
    if effectiveness_mult > 1.0:
        eff_label = "super effective"
    elif effectiveness_mult < 1.0:
        eff_label = "not very effective"
    else:
        eff_label = "neutral"

    # Critical hit (6.25% chance, 1.5x)
    critical = random.random() < 0.0625
    crit_mult = 1.5 if critical else 1.0

    # Random factor (0.85-1.0)
    rand_factor = random.uniform(0.85, 1.0)

    damage = int(base * effectiveness_mult * crit_mult * rand_factor)
    damage = max(1, damage)  # Minimum 1 damage

    return damage, eff_label, critical


def _apply_status_effect(target: Fighter, move: BattleMove) -> None:
    """Apply stat buff/debuff from a status move."""
    if not move.stat_effect:
        return

    effect = move.stat_effect.strip()
    modifier = 10 if effect.startswith("+") else -10
    stat_name = effect.lstrip("+-")

    stat_map = {
        "attack": "attack",
        "defense": "defense",
        "sp_attack": "sp_attack",
        "sp_defense": "sp_defense",
        "speed": "speed",
    }

    if stat_name in stat_map:
        current = getattr(target.stats, stat_map[stat_name])
        new_val = max(1, min(100, current + modifier))
        setattr(target.stats, stat_map[stat_name], new_val)


def _fighter_summary(fighter: Fighter) -> dict:
    """Create a summary dict for the BattleLog."""
    return {
        "name": fighter.display_name,
        "types": fighter.stats.types,
        "hp": fighter.stats.hp,
        "attack": fighter.stats.attack,
        "defense": fighter.stats.defense,
        "sp_attack": fighter.stats.sp_attack,
        "sp_defense": fighter.stats.sp_defense,
        "speed": fighter.stats.speed,
        "moves": [m.name for m in fighter.moves],
    }


def run_battle(
    fighter1: Fighter,
    fighter2: Fighter,
    api_key: str,
    verbose: bool = True,
) -> BattleLog:
    """Run a full turn-based battle between two fighters."""
    referee = RefereeAgent(api_key)
    battle_log = BattleLog(
        fighter_1=_fighter_summary(fighter1),
        fighter_2=_fighter_summary(fighter2),
    )

    # Speed determines turn order
    if fighter1.stats.speed >= fighter2.stats.speed:
        order = [fighter1, fighter2]
    else:
        order = [fighter2, fighter1]

    turn = 0
    while turn < MAX_TURNS:
        for attacker, defender in [(order[0], order[1]), (order[1], order[0])]:
            if attacker.is_fainted or defender.is_fainted:
                break

            turn += 1

            # Fighter agent picks a move
            move = pick_move(attacker, defender, turn, api_key)

            # Accuracy check
            if random.randint(1, 100) > move.accuracy:
                damage, eff_label, critical = 0, "missed", False
                if verbose:
                    print(f"  Turn {turn}: {attacker.display_name} used "
                          f"{move.name}... but it missed!")
            else:
                if move.power > 0:
                    damage, eff_label, critical = _calc_damage(
                        attacker, defender, move
                    )
                    defender.current_hp = max(0, defender.current_hp - damage)
                else:
                    damage, eff_label, critical = 0, "status", False
                    # Status moves apply to self (buff) or opponent (debuff)
                    if move.stat_effect and move.stat_effect.startswith("+"):
                        _apply_status_effect(attacker, move)
                    elif move.stat_effect:
                        _apply_status_effect(defender, move)

            # Narrate
            narration = referee.narrate_turn(
                turn=turn,
                attacker=attacker.display_name,
                defender=defender.display_name,
                move_name=move.name,
                damage=damage,
                effectiveness=eff_label,
                critical=critical,
                attacker_hp=attacker.current_hp,
                attacker_max_hp=attacker.stats.hp,
                defender_hp=defender.current_hp,
                defender_max_hp=defender.stats.hp,
            )

            turn_result = TurnResult(
                turn_number=turn,
                attacker=attacker.display_name,
                defender=defender.display_name,
                move_used=move.name,
                damage=damage,
                effectiveness=eff_label,
                critical_hit=critical,
                attacker_hp=attacker.current_hp,
                defender_hp=defender.current_hp,
                narration=narration,
            )
            battle_log.turns.append(turn_result)

            if verbose:
                print(f"\n--- Turn {turn} ---")
                print(f"{attacker.display_name} used {move.name}!")
                if damage > 0:
                    print(f"  Damage: {damage} ({eff_label})"
                          + (" CRITICAL HIT!" if critical else ""))
                print(f"  {attacker.display_name}: {attacker.current_hp}/{attacker.stats.hp} HP")
                print(f"  {defender.display_name}: {defender.current_hp}/{defender.stats.hp} HP")
                print(f"  >> {narration}")

            if defender.is_fainted:
                break

        if fighter1.is_fainted or fighter2.is_fainted:
            break

    # Determine winner
    if fighter1.is_fainted:
        winner = fighter2
    elif fighter2.is_fainted:
        winner = fighter1
    else:
        # Timeout — whoever has more HP% wins
        pct1 = fighter1.current_hp / fighter1.stats.hp
        pct2 = fighter2.current_hp / fighter2.stats.hp
        winner = fighter1 if pct1 >= pct2 else fighter2

    battle_log.winner = winner.display_name

    # Final narration
    battle_log.final_narration = referee.final_narration(
        fighter1=fighter1.display_name,
        types1=fighter1.stats.types,
        fighter2=fighter2.display_name,
        types2=fighter2.stats.types,
        winner=winner.display_name,
        total_turns=len(battle_log.turns),
        winner_hp=winner.current_hp,
        winner_max_hp=winner.stats.hp,
    )

    if verbose:
        print(f"\n{'='*50}")
        print(f"WINNER: {winner.display_name}!")
        print(f"{'='*50}")
        print(battle_log.final_narration)

    return battle_log
