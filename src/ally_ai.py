import math
from typing import List, Optional

from entities import Boss, Monster, NPCAlly, has_line_of_sight
from pathfinding import bfs_path, flee_path


def _dist(a, b) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _hp_ratio(e) -> float:
    return e.hp / e.max_hp if getattr(e, "max_hp", 0) > 0 else 0.0


def _alive_enemies(monsters, bosses, npc_enemies):
    return [e for e in list(monsters) + list(bosses) + list(npc_enemies) if e.alive]


def _move_step(unit, path, now, walls, occupied):
    if not path:
        return None
    nx, ny = path[0]
    if (nx, ny) in occupied:
        return None
    old = (unit.x, unit.y)
    unit.x, unit.y = nx, ny
    unit.last_move = now
    occupied.discard(old)
    occupied.add((nx, ny))
    return (nx, ny)


def _can_move(unit, now):
    return (now - unit.last_move) >= 1.0 / max(0.1, getattr(unit, "speed", 1.0))


def _nearest_enemy(unit, enemies, walls, max_range=10):
    best = None
    best_score = 9999
    for e in enemies:
        d = _dist(unit, e)
        if d > max_range:
            continue
        if not has_line_of_sight(unit.x, unit.y, e.x, e.y, walls):
            continue
        weak_bonus = 3 if _hp_ratio(e) < 0.30 else 0
        boss_penalty = 2 if isinstance(e, Boss) else 0
        score = d - weak_bonus + boss_penalty
        if score < best_score:
            best = e
            best_score = score
    return best


def _most_wounded(targets, healer, heal_range):
    wounded = []
    for t in targets:
        if not t.alive:
            continue
        ratio = _hp_ratio(t)
        # Heal before the ally becomes critical; small parties cannot afford
        # waiting until a companion drops below half HP.
        if ratio >= 0.95 or ratio >= 1.0:
            continue
        distance = _dist(healer, t)
        if distance > heal_range:
            continue

        # Lower score = higher priority. Critical wounds dominate distance;
        # the player gets a small tie-breaker, while frontline allies get a
        # slight bonus because they absorb most incoming damage.
        score = ratio
        if ratio <= 0.25:
            score -= 0.35
        elif ratio <= 0.40:
            score -= 0.15
        if getattr(t, "class_name", "") == "swordsman":
            score -= 0.06
        if getattr(t, "is_player", False):
            score -= 0.04
        score += min(distance, heal_range) * 0.012
        wounded.append((score, ratio, distance, t))
    wounded.sort(key=lambda item: (item[0], item[1], item[2]))
    return wounded[0][3] if wounded else None


def _heal(healer: NPCAlly, target, combat, log, now):
    if (now - healer.last_spell) < 1.8 or healer.mp < 10:
        return False
    amount = int(12 + healer.magic_power * 1.55)
    actual_heal = target.heal(amount)
    healer.mp = max(0, healer.mp - 10)
    healer.last_spell = now
    # Keep a short-lived UI marker so the party panel confirms who was healed.
    target.last_heal_time = now
    target.last_heal_amount = actual_heal
    combat._add_popup(target.x, target.y, f"+{actual_heal}", "0,255,120")
    log.append(f"{healer.name} heals {target.name} for {actual_heal}.")
    return True


def _ranged_attack(ally: NPCAlly, target, combat, log, now):
    if not getattr(ally, "ranged", False) and ally.class_name != "healer":
        return False
    if _dist(ally, target) > ally.attack_range:
        return False
    return combat.npc_ally_ranged_attack(ally, target, now, log)


def _melee_attack(ally, target, combat, now):
    if _dist(ally, target) > 1:
        return None
    return combat.ally_attack(ally, target, now)


def _kite_or_close(ally: NPCAlly, target, gm, occupied, now, preferred_range: int):
    if not _can_move(ally, now):
        return None
    d = _dist(ally, target)
    if d < preferred_range:
        path = flee_path((ally.x, ally.y), (target.x, target.y), gm.walls, occupied, depth=3)
        return _move_step(ally, path, now, gm.walls, occupied)
    if d > preferred_range + 1:
        path = bfs_path((ally.x, ally.y), (target.x, target.y), gm.walls, occupied, max_depth=12)
        return _move_step(ally, path, now, gm.walls, occupied)
    return None


def _follow_player(ally, player, gm, occupied, now, follow_dist=2):
    if _dist(ally, player) > 12:
        old = (ally.x, ally.y)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
            nx, ny = player.x + dx, player.y + dy
            if gm.walkable(nx, ny) and (nx, ny) not in occupied:
                ally.x, ally.y = nx, ny
                occupied.discard(old)
                occupied.add((nx, ny))
                return (nx, ny)
    if _dist(ally, player) <= follow_dist or not _can_move(ally, now):
        return None
    path = bfs_path((ally.x, ally.y), (player.x, player.y), gm.walls, occupied, max_depth=10)
    return _move_step(ally, path, now, gm.walls, occupied)


def npc_ally_decide_and_act(ally: NPCAlly, player, party: List[NPCAlly], summons,
                            monsters, bosses, npc_enemies, gm, occupied, combat, log, now):
    enemies = _alive_enemies(monsters, bosses, npc_enemies)
    ally._player_ref = player

    if ally.class_name == "healer":
        target = _most_wounded([player] + list(party) + list(summons), ally, heal_range=6)
        if target and _heal(ally, target, combat, log, now):
            return "heal"
        if target and _dist(ally, target) > 3 and _can_move(ally, now):
            path = bfs_path((ally.x, ally.y), (target.x, target.y), gm.walls, occupied, max_depth=8)
            if _move_step(ally, path, now, gm.walls, occupied):
                return "reach_wounded"

    if enemies:
        focus = _nearest_enemy(ally, enemies, gm.walls, max_range=ally.aggro_range)
        if not focus:
            return _follow_player(ally, player, gm, occupied, now)

        if ally.class_name == "swordsman":
            if _melee_attack(ally, focus, combat, now):
                return "attack"
            return _kite_or_close(ally, focus, gm, occupied, now, preferred_range=1)

        if ally.class_name == "rogue":
            weak = min(enemies, key=lambda e: (_hp_ratio(e), _dist(ally, e)))
            if _dist(ally, weak) <= ally.aggro_range and has_line_of_sight(ally.x, ally.y, weak.x, weak.y, gm.walls):
                focus = weak
            if _melee_attack(ally, focus, combat, now):
                return "execute"
            return _kite_or_close(ally, focus, gm, occupied, now, preferred_range=1)

        if ally.class_name in ("archer", "mage"):
            if _ranged_attack(ally, focus, combat, log, now):
                return "shoot"
            return _kite_or_close(ally, focus, gm, occupied, now, preferred_range=4 if ally.class_name == "archer" else 5)

        if ally.class_name == "healer":
            # Healers are support-only: after healing, they stay with the party.
            return _follow_player(ally, player, gm, occupied, now, follow_dist=3)

    return _follow_player(ally, player, gm, occupied, now)
