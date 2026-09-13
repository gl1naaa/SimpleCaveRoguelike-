"""
Environment effects — interactive dungeon tiles: water, barrels, rubble.
"""

import random
import math

# ============================================================
#  Tile Constants
# ============================================================
TILE_WATER  = "~"   # Slows entities that walk through it
TILE_BARREL = "!"   # Explosive barrel, non-walkable until destroyed
TILE_RUBBLE = ":"   # Destroyable wall debris, walkable

# Tiles that slow movement
SLOWING_TILES = {TILE_WATER}

# Tiles that are walkable (open ground variants)
WALKABLE_TILES = {TILE_WATER, TILE_RUBBLE}

# Tiles that can be destroyed
DESTROYABLE_TILES = {TILE_BARREL, TILE_RUBBLE}


# ============================================================
#  Query Helpers
# ============================================================

def is_slowing(tile: str) -> bool:
    """Return True if the tile causes slow effect."""
    return tile in SLOWING_TILES


def is_destroyable(tile: str) -> bool:
    """Return True if the tile can be destroyed (barrels, rubble)."""
    return tile in DESTROYABLE_TILES


def is_walkable(tile: str) -> bool:
    """Return True if the tile can be walked on without destroying."""
    return tile in WALKABLE_TILES


# ============================================================
#  Barrel Explosion — AoE
# ============================================================

BARREL_DAMAGE = 15
BARREL_RADIUS = 2


def explode_barrel(x: int, y: int, game_state: dict) -> list:
    """
    Detonate a barrel at (x, y).

    game_state must contain:
        "monsters":  list of Monster objects
        "bosses":    list of Boss objects
        "player":    Player object
        "npc_enemies": list of NPCEnemy objects (optional)
        "allies":    list of Ally objects (optional)
        "tiles":     2-D tile grid (list of lists of str)
        "log":       list to append messages to
        "combat":    CombatSystem instance (for popups)

    Returns a list of hit entities (any that took damage).
    The barrel tile is replaced with "." on success.
    """
    tiles = game_state.get("tiles", [])
    log = game_state.get("log", [])
    combat = game_state.get("combat")
    monsters = game_state.get("monsters", [])
    bosses = game_state.get("bosses", [])
    player = game_state.get("player")
    npc_enemies = game_state.get("npc_enemies", [])
    allies = game_state.get("allies", [])

    # Destroy barrel tile
    if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]):
        tiles[y][x] = "."

    log.append(f"Barrel explodes! ({BARREL_DAMAGE} AoE, r={BARREL_RADIUS})")
    hit = []

    def _dist(ex, ey):
        return math.sqrt((ex - x) ** 2 + (ey - y) ** 2)

    # Damage all entities in radius
    for entity_list in (monsters, bosses, npc_enemies, allies):
        for e in entity_list:
            if e.alive and _dist(e.x, e.y) <= BARREL_RADIUS:
                e.take_damage(BARREL_DAMAGE)
                hit.append(e)
                if combat:
                    combat._add_popup(e.x, e.y, f"-{BARREL_DAMAGE}", "255,160,0")
                if not e.alive:
                    log.append(f"{e.name} destroyed by barrel!")

    # Player takes damage too if in radius
    if player and player.alive and _dist(player.x, player.y) <= BARREL_RADIUS:
        actual = player.take_damage(BARREL_DAMAGE)
        hit.append(player)
        if combat:
            combat._add_popup(player.x, player.y, f"-{actual}", "255,160,0")
        log.append(f"Barrel hit you for {actual}!")

    return hit


# ============================================================
#  Tile Effect on Entity
# ============================================================

def apply_tile_effect(entity, tile: str, combat) -> str:
    """
    Apply environment effect when an entity steps on a tile.
    - Water (~): slow for 2 turns
    - Fire/lava if present: burn (future-proof)

    Returns a short log message or "" if nothing happened.
    """
    if tile == TILE_WATER:
        if not combat.has_effect(entity, "slow"):
            combat.add_effect(entity, __import__('combat').StatusEffect("slow", 2.0, 50))
            combat._add_popup(entity.x, entity.y, "SLOW", "100,180,255")
            return f"{entity.name} wades through water! (SLOW)"
        return ""
    # Future: lava/fire tiles could apply burn here
    return ""


# ============================================================
#  Trap check for any entity (player, monster, boss, etc.)
# ============================================================

TRAP_CHAR = "^"


def check_trap_for_entity(entity, x: int, y: int, traps: dict, floor_num: int = 1) -> int:
    """
    Check if a tile at (x, y) is a trap and apply damage to entity.

    Parameters:
        entity:  any object with take_damage(dmg) and x, y attributes
        x, y:    entity position to check
        traps:   dict mapping (x, y) -> trap info (unused, kept for API compat)
        floor_num: current floor for scaling

    Returns damage dealt (0 if no trap).
    """
    # We don't store traps separately; the tile itself is "^".
    # This function is here so game.py can call it for monsters/enemies.
    # The caller should pass the tile grid and check tile[y][x] == "^".
    return 0


def check_trap_at_tile(entity, tile: str, x: int, y: int, tiles: list, floor_num: int = 1) -> int:
    """
    Check if the tile at entity's position is a trap and deal damage.
    Consumes the trap (replaces with ".").

    Returns damage dealt (0 if no trap).
    """
    if tile != TRAP_CHAR:
        return 0
    trap_dmg = random.randint(5 + floor_num * 2, 15 + floor_num * 3)
    actual = entity.take_damage(trap_dmg)
    if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]):
        tiles[y][x] = "."
    return actual
