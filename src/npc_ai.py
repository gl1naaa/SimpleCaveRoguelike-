import math
from typing import Tuple, List, Optional, Set
from pathfinding import bfs_path, flee_path, flank_positions


def _dist(a, b) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _manhattan(a, b) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _hp_ratio(e) -> float:
    return e.hp / e.max_hp if e.max_hp > 0 else 0.0


def _mp_ratio(e) -> float:
    return e.mp / e.max_mp if e.max_mp > 0 else 0.0


def _count_nearby(pos, entities, radius=3) -> int:
    cx, cy = pos
    count = 0
    for e in entities:
        if e.alive and abs(e.x - cx) + abs(e.y - cy) <= radius:
            count += 1
    return count


def _has_melee_ally_between(npc, target, allies) -> bool:
    for a in allies:
        if a.alive and a.class_name in ("swordsman", "rogue"):
            d_to_target = _dist(a, target)
            d_npc_to_target = _dist(npc, target)
            if d_to_target < d_npc_to_target and d_to_target <= 2:
                return True
    return False


def _has_ally_tanking(npc, target, allies) -> bool:
    for a in allies:
        if a.alive and a.class_name == "swordsman":
            d = _dist(a, target)
            if d <= 2:
                return True
    return False


def _skill_ready(npc, slot: int) -> bool:
    if slot >= len(npc.skills):
        return False
    sk = npc.skills[slot]
    if sk is None:
        return False
    if npc.mp < sk.mana_cost:
        return False
    return sk.ready(0)


def _try_use_skill(npc, slot: int, target, now: float, combat, log) -> bool:
    if slot >= len(npc.skills):
        return False
    sk = npc.skills[slot]
    if sk is None:
        return False
    if not sk.ready(now):
        return False
    if npc.mp < sk.mana_cost:
        return False

    if sk.range > 0:
        dist = _dist(npc, target)
        if dist > sk.range + 1:
            return False

    npc.mp -= sk.mana_cost
    sk.use(now)

    if sk.effect in ("heal", "heal_ally", "heal_ally_big", "buff_ally", "purify", "restore_mp_ally"):
        return True

    t_def = target.defense if hasattr(target, 'defense') else 0
    dmg_base = sk.damage + npc.magic_power if npc.class_name in ("mage", "healer") else sk.damage + npc.atk // 2
    dmg = max(1, dmg_base - t_def // 2)

    is_crit = npc.crit > 0 and (hash(str(now) + str(npc.x)) % 100) < npc.crit * 100
    if is_crit:
        dmg = int(dmg * 2.0)

    actual = target.take_damage(dmg) if hasattr(target, 'take_damage') else 0
    color = "255,255,100" if is_crit else "255,150,150"
    combat._add_popup(target.x, target.y, f"-{actual}", color)

    if sk.aoe > 0:
        combat._add_popup(npc.x, npc.y, sk.name, "180,180,255")

    if not target.alive:
        if hasattr(target, 'name'):
            log.append(f"{npc.name} killed {target.name}!")

    return True


# ============================================================
#  CLASS SCORING FUNCTIONS
# ============================================================

def _score_rogue(npc, target, allies, enemies, walls, occupied, now) -> List[Tuple[float, str, dict]]:
    actions = []
    dist = _dist(npc, target)
    hp = _hp_ratio(npc)
    mp = _mp_ratio(npc)

    has_tank = _has_ally_tanking(npc, target, allies)

    if hp < 0.3:
        path = flee_path((npc.x, npc.y), (target.x, target.y), walls, occupied, 3)
        if path:
            actions.append((95, "flee", {"path": path}))

    if hp < 0.5 and _skill_ready(npc, 4):
        actions.append((88, "use_skill", {"slot": 4}))

    flank = flank_positions((npc.x, npc.y), (target.x, target.y), walls, occupied, 3)
    if flank:
        flank_score = 85 if has_tank else 75
        actions.append((flank_score, "flank", {"pos": flank[0]}))

    if dist <= 1.5 and _skill_ready(npc, 0):
        actions.append((75, "use_skill", {"slot": 0, "target": target}))

    if dist <= 1.5 and _skill_ready(npc, 3):
        actions.append((70, "use_skill", {"slot": 3, "target": target}))

    if dist <= 2 and _skill_ready(npc, 2):
        actions.append((65, "use_skill", {"slot": 2, "target": target}))

    if dist <= 1.5:
        actions.append((50, "melee_attack", {"target": target}))

    if dist > 1.5:
        path = bfs_path((npc.x, npc.y), (target.x, target.y), walls, occupied, 15)
        if path:
            actions.append((40, "chase", {"path": path}))

    actions.append((10, "wander", {}))
    return actions


def _score_mage(npc, target, allies, enemies, walls, occupied, now) -> List[Tuple[float, str, dict]]:
    actions = []
    dist = _dist(npc, target)
    hp = _hp_ratio(npc)
    mp = _mp_ratio(npc)

    has_tank = _has_melee_ally_between(npc, target, allies)

    if dist < 3 and not has_tank:
        path = flee_path((npc.x, npc.y), (target.x, target.y), walls, occupied, 2)
        if path:
            actions.append((95, "flee", {"path": path}))
        if _skill_ready(npc, 4):
            actions.append((90, "use_skill", {"slot": 4}))

    if _skill_ready(npc, 3) and hp < 0.5:
        actions.append((82, "use_skill", {"slot": 3}))

    nearby_count = _count_nearby((target.x, target.y), enemies, 3)
    if nearby_count >= 2 and _skill_ready(npc, 1):
        actions.append((78, "use_skill", {"slot": 1, "target": target}))
    if nearby_count >= 2 and _skill_ready(npc, 2):
        actions.append((72, "use_skill", {"slot": 2, "target": target}))

    if _skill_ready(npc, 0) and dist <= 12:
        actions.append((68, "use_skill", {"slot": 0, "target": target}))

    if npc.ranged and dist > 1:
        actions.append((45, "ranged_attack", {"target": target}))

    if dist > 1:
        path = bfs_path((npc.x, npc.y), (target.x, target.y), walls, occupied, 15)
        if path:
            actions.append((30, "chase", {"path": path}))

    actions.append((5, "wander", {}))
    return actions


def _score_archer(npc, target, allies, enemies, walls, occupied, now) -> List[Tuple[float, str, dict]]:
    actions = []
    dist = _dist(npc, target)
    hp = _hp_ratio(npc)

    has_tank = _has_melee_ally_between(npc, target, allies)

    if dist < 3 and not has_tank:
        path = flee_path((npc.x, npc.y), (target.x, target.y), walls, occupied, 2)
        if path:
            actions.append((90, "kite", {"path": path}))

    if hp < 0.3:
        path = flee_path((npc.x, npc.y), (target.x, target.y), walls, occupied, 3)
        if path:
            actions.append((92, "flee", {"path": path}))

    if _skill_ready(npc, 3):
        actions.append((80, "use_skill", {"slot": 3, "target": target}))

    if _skill_ready(npc, 2):
        actions.append((75, "use_skill", {"slot": 2, "target": target}))

    nearby_count = _count_nearby((target.x, target.y), enemies, 3)
    if nearby_count >= 2 and _skill_ready(npc, 4):
        actions.append((70, "use_skill", {"slot": 4, "target": target}))

    if _skill_ready(npc, 1):
        actions.append((65, "use_skill", {"slot": 1, "target": target}))

    if dist > 2:
        actions.append((50, "ranged_attack", {"target": target}))

    if dist <= 2:
        path = flee_path((npc.x, npc.y), (target.x, target.y), walls, occupied, 2)
        if path:
            actions.append((45, "kite", {"path": path}))

    actions.append((5, "wander", {}))
    return actions


def _score_swordsman(npc, target, allies, enemies, walls, occupied, now) -> List[Tuple[float, str, dict]]:
    actions = []
    dist = _dist(npc, target)
    hp = _hp_ratio(npc)

    if hp < 0.5 and _skill_ready(npc, 4):
        actions.append((90, "use_skill", {"slot": 4}))

    if hp < 0.7 and _skill_ready(npc, 3):
        actions.append((80, "use_skill", {"slot": 3}))

    if dist <= 1.5 and _skill_ready(npc, 2):
        actions.append((82, "use_skill", {"slot": 2, "target": target}))

    nearby_count = _count_nearby((npc.x, npc.y), enemies, 2)
    if nearby_count >= 2 and _skill_ready(npc, 1):
        actions.append((75, "use_skill", {"slot": 1, "target": target}))

    if _skill_ready(npc, 0) and dist <= 1.5:
        actions.append((70, "use_skill", {"slot": 0, "target": target}))

    if dist <= 1.5:
        actions.append((55, "melee_attack", {"target": target}))

    if dist > 1.5:
        path = bfs_path((npc.x, npc.y), (target.x, target.y), walls, occupied, 15)
        if path:
            actions.append((40, "chase", {"path": path}))

    actions.append((5, "wander", {}))
    return actions


def _score_healer(npc, target, allies, enemies, walls, occupied, now) -> List[Tuple[float, str, dict]]:
    actions = []
    dist = _dist(npc, target)
    hp = _hp_ratio(npc)
    mp = _mp_ratio(npc)

    wounded = None
    worst_hp = 999
    for a in allies:
        if a.alive and a is not npc:
            r = _hp_ratio(a)
            if r < 0.5 and r < worst_hp:
                worst_hp = r
                wounded = a

    if wounded and mp > 0.3:
        w_dist = _dist(npc, wounded)
        if _skill_ready(npc, 1) and worst_hp < 0.3:
            actions.append((92, "use_skill", {"slot": 1, "target": wounded}))
        if _skill_ready(npc, 0):
            actions.append((85, "use_skill", {"slot": 0, "target": wounded}))
        if w_dist > 6:
            path = bfs_path((npc.x, npc.y), (wounded.x, wounded.y), walls, occupied, 15)
            if path:
                actions.append((60, "chase", {"path": path}))

    if _skill_ready(npc, 2) and mp > 0.3:
        for a in allies:
            if a.alive and a is not npc:
                if hasattr(a, 'status_effects') or True:
                    actions.append((55, "use_skill", {"slot": 2, "target": a}))
                    break

    if _skill_ready(npc, 3) and mp > 0.3:
        for a in allies:
            if a.alive and a is not npc:
                actions.append((50, "use_skill", {"slot": 3, "target": a}))
                break

    if _skill_ready(npc, 4) and mp < 0.3:
        for a in allies:
            if a.alive and a is not npc:
                actions.append((48, "use_skill", {"slot": 4, "target": a}))
                break

    if dist < 3:
        path = flee_path((npc.x, npc.y), (target.x, target.y), walls, occupied, 2)
        if path:
            actions.append((70, "flee", {"path": path}))

    if dist <= 1.5 and not wounded:
        actions.append((20, "melee_attack", {"target": target}))

    actions.append((5, "wander", {}))
    return actions


def _score_summoner(npc, target, allies, enemies, walls, occupied, now) -> List[Tuple[float, str, dict]]:
    actions = []
    dist = _dist(npc, target)
    hp = _hp_ratio(npc)

    ally_count = sum(1 for a in allies if a.alive and a is not npc)

    if ally_count < 2 and _skill_ready(npc, 4):
        actions.append((88, "use_skill", {"slot": 4}))

    if ally_count < 3 and _skill_ready(npc, 0):
        actions.append((80, "use_skill", {"slot": 0}))

    if dist < 4 and _skill_ready(npc, 3):
        actions.append((70, "use_skill", {"slot": 3}))

    if dist <= 3 and _skill_ready(npc, 2):
        actions.append((68, "use_skill", {"slot": 2, "target": target}))

    if hp < 0.6 and _skill_ready(npc, 1):
        actions.append((65, "use_skill", {"slot": 1, "target": target}))

    if dist > 1:
        path = bfs_path((npc.x, npc.y), (target.x, target.y), walls, occupied, 15)
        if path:
            actions.append((35, "chase", {"path": path}))

    actions.append((5, "wander", {}))
    return actions


CLASS_SCORERS = {
    "rogue": _score_rogue,
    "mage": _score_mage,
    "archer": _score_archer,
    "swordsman": _score_swordsman,
    "healer": _score_healer,
    "summoner": _score_summoner,
}


# ============================================================
#  ACTION EXECUTION
# ============================================================

def _execute_action(npc, action_type, params, target, now, combat, log,
                    gm_walls, occupied, all_allies, all_enemies) -> bool:
    if action_type == "melee_attack":
        t = params.get("target", target)
        if (now - npc.last_attack) < npc.attack_delay:
            return False
        npc.last_attack = now
        t_def = t.defense if hasattr(t, 'defense') else 0
        dmg, crit = combat._calc_damage(npc.atk, t_def, npc.crit)
        if dmg > 0:
            actual = t.take_damage(dmg) if hasattr(t, 'take_damage') else 0
            color = "255,255,100" if crit else "255,150,150"
            combat._add_popup(t.x, t.y, f"-{actual}", color)
            if not t.alive:
                if hasattr(t, 'name'):
                    log.append(f"{npc.name} killed {t.name}!")
        return True

    if action_type == "ranged_attack":
        t = params.get("target", target)
        combat.npc_enemy_ranged_attack(npc, t, now, log)
        return True

    if action_type == "use_skill":
        slot = params["slot"]
        t = params.get("target", target)
        return _try_use_skill(npc, slot, t, now, combat, log)

    if action_type == "chase":
        path = params["path"]
        if path:
            nx, ny = path[0]
            if (nx, ny) not in gm_walls and (nx, ny) not in occupied:
                old = (npc.x, npc.y)
                npc.x, npc.y = nx, ny
                npc.last_move = now
                occupied.discard(old)
                occupied.add((nx, ny))
                return True
        return False

    if action_type == "flee":
        path = params.get("path", [])
        if path:
            nx, ny = path[0]
            if (nx, ny) not in gm_walls and (nx, ny) not in occupied:
                old = (npc.x, npc.y)
                npc.x, npc.y = nx, ny
                npc.last_move = now
                occupied.discard(old)
                occupied.add((nx, ny))
                return True
        return False

    if action_type == "kite":
        path = params.get("path", [])
        if path:
            nx, ny = path[0]
            if (nx, ny) not in gm_walls and (nx, ny) not in occupied:
                old = (npc.x, npc.y)
                npc.x, npc.y = nx, ny
                npc.last_move = now
                occupied.discard(old)
                occupied.add((nx, ny))
                return True
        return False

    if action_type == "flank":
        pos = params.get("pos")
        if pos:
            nx, ny = pos
            if (nx, ny) not in gm_walls and (nx, ny) not in occupied:
                old = (npc.x, npc.y)
                npc.x, npc.y = nx, ny
                npc.last_move = now
                occupied.discard(old)
                occupied.add((nx, ny))
                return True
        return False

    if action_type == "wander":
        dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        import random
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = npc.x + dx, npc.y + dy
            if (nx, ny) not in gm_walls and (nx, ny) not in occupied:
                old = (npc.x, npc.y)
                npc.x, npc.y = nx, ny
                npc.last_move = now
                occupied.discard(old)
                occupied.add((nx, ny))
                return True
        return False

    return False


# ============================================================
#  MAIN ENTRY POINT
# ============================================================

def npc_decide_and_act(npc, player, npc_enemies, monsters, bosses,
                       walls, occupied, now, combat, log) -> None:
    if not npc.alive:
        return
    if combat.is_stunned(npc):
        return

    if now - npc.last_move < 1.0 / npc.speed:
        return

    all_allies = [e for e in npc_enemies if e.alive and e is not npc]
    all_enemies = [player]

    target = None
    min_dist = 999
    for t in all_enemies:
        d = _manhattan(npc, t)
        if d < min_dist:
            min_dist = d
            target = t

    if not target:
        dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        import random
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = npc.x + dx, npc.y + dy
            if (nx, ny) not in walls and (nx, ny) not in occupied:
                old = (npc.x, npc.y)
                npc.x, npc.y = nx, ny
                npc.last_move = now
                occupied.discard(old)
                occupied.add((nx, ny))
                return
        return

    if not npc.can_see_player(target.x, target.y):
        dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        import random
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = npc.x + dx, npc.y + dy
            if (nx, ny) not in walls and (nx, ny) not in occupied:
                old = (npc.x, npc.y)
                npc.x, npc.y = nx, ny
                npc.last_move = now
                occupied.discard(old)
                occupied.add((nx, ny))
                return
        return

    scorer = CLASS_SCORERS.get(npc.class_name, _score_swordsman)
    scored_actions = scorer(npc, target, all_allies, all_enemies, walls, occupied, now)

    scored_actions.sort(key=lambda x: x[0], reverse=True)

    for score, action_type, params in scored_actions:
        if action_type == "melee_attack" or action_type == "ranged_attack" or action_type == "use_skill":
            if (now - npc.last_attack) >= npc.attack_delay:
                success = _execute_action(npc, action_type, params, target, now, combat, log,
                                         walls, occupied, all_allies, all_enemies)
                if success:
                    return

    for score, action_type, params in scored_actions:
        if action_type in ("chase", "flee", "kite", "flank", "wander"):
            success = _execute_action(npc, action_type, params, target, now, combat, log,
                                     walls, occupied, all_allies, all_enemies)
            if success:
                return
