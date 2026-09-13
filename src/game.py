import sys, io, os, math, random, time, ctypes
from typing import List, Tuple, Optional, Dict, Set
from config import *
from ui import (fg, bg, rst, bold, dim, BLK, SH1, SH2, SH3, DIAM, HEART, DSTAR, ARROW, DOT,
                WALL_H, WALL_V, WALL_TL, WALL_TR, WALL_BL, WALL_BR, WALL_LT, WALL_RT, WALL_T, WALL_B,
                BOX_H, BOX_V, BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_LT, BOX_RT, BOX_T, BOX_B,
                rainbow, rarity_color, clear_screen, hide_cursor, show_cursor)
from input import InputState, wait_for_any_key
from fov import FOV
from map_generator import generate_dungeon, Room
from entities import Player, Monster, Boss, Ally, NPCAlly, Chest, MONSTER_TYPES, BOSS_TYPES, NPCEnemy, has_line_of_sight
from combat import CombatSystem, DamagePopup, StatusEffect, Projectile
from npc_ai import npc_decide_and_act
from ally_ai import npc_ally_decide_and_act, _most_wounded
from pathfinding import flee_path
from inventory import Inventory, handle_inventory_input
from items import Item, generate_random_item
from menu import show_title, show_class_select, show_controls, show_death, show_level_up, show_victory
from map_generator import generate_city
try:
    from meta import MetaProgression, apply_meta_bonuses, open_meta_shop
    _META_AVAILABLE = True
except ImportError:
    _META_AVAILABLE = False
try:
    from run_stats import RunTracker
    _RUN_STATS_AVAILABLE = True
except ImportError:
    _RUN_STATS_AVAILABLE = False
try:
    from env_effects import (TILE_WATER, TILE_BARREL, TILE_RUBBLE,
                             explode_barrel, apply_tile_effect, check_trap_at_tile)
    _ENV_EFFECTS_AVAILABLE = True
except ImportError:
    _ENV_EFFECTS_AVAILABLE = False
try:
    from fx import FXSystem, water_char, render_particle
    _FX_AVAILABLE = True
except ImportError:
    _FX_AVAILABLE = False

# ============================================================
#  Game Map
# ============================================================
class GameMap:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.tiles: List[List[str]] = []
        self.walls: set = set()

    def load(self, tiles, walls=None):
        self.tiles = tiles
        self.walls = walls or set()

    def tile(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.tiles[y][x]
        return "#"

    def walkable(self, x, y):
        t = self.tile(x, y)
        if _ENV_EFFECTS_AVAILABLE:
            return t in (".", STAIRS_DOWN, "*", "^", "$", "&", TILE_WATER, TILE_RUBBLE)
        return t in (".", STAIRS_DOWN, "*", "^", "$", "&")

    def is_wall(self, x, y):
        return self.tile(x, y) == "#"

    def get_floor_tiles(self, tiles):
        floors = []
        for y in range(self.h):
            for x in range(self.w):
                if tiles[y][x] == ".":
                    floors.append((x, y))
        return floors

    def wall_char(self, x, y):
        if not self.is_wall(x, y):
            return BLK
        up    = self.is_wall(x, y - 1)
        down  = self.is_wall(x, y + 1)
        left  = self.is_wall(x - 1, y)
        right = self.is_wall(x + 1, y)
        if up and down and left and right:
            return BLK
        if up and down and left:    return WALL_RT
        if up and down and right:   return WALL_LT
        if left and right and up:   return WALL_B
        if left and right and down: return WALL_T
        if up and left:   return WALL_BR
        if up and right:  return WALL_BL
        if down and left: return WALL_TR
        if down and right:return WALL_TL
        if up or down:    return WALL_V
        if left or right: return WALL_H
        return BLK


# ============================================================
#  Floor Generation
# ============================================================
def gen_floor(floor_num: int, player: Player):
    gm = GameMap(MAP_WIDTH, MAP_HEIGHT)
    tiles, first_room, last_room, rooms = generate_dungeon(floor_num)
    gm.load(tiles)

    # Place player in first room
    px, py = first_room.center
    player.x, player.y = px, py
    player.floor = floor_num

    # Walls set
    gm.walls = set()
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            if tiles[y][x] == "#":
                gm.walls.add((x, y))

    # Entities
    monsters: List[Monster] = []
    bosses: List[Boss] = []
    chests: List[Chest] = []
    npc_enemies: List[NPCEnemy] = []

    # Get walkable tiles
    floors = gm.get_floor_tiles(tiles)
    occupied = set()
    occupied.add((px, py))
    occupied.add(last_room.center)

    def _free_tile():
        random.shuffle(floors)
        for tx, ty in floors:
            if (tx, ty) not in occupied:
                if abs(tx - px) + abs(ty - py) >= 5:
                    occupied.add((tx, ty))
                    return tx, ty
        return None

    # Spawn monsters in rooms
    from config import NPC_ENEMY_CHANCE, NPC_ENEMY_MIN_FLOOR, NPC_ENEMY_CLASSES, NPC_ENEMY_CLASS_WEIGHTS, NPC_ENEMY_PER_ROOM_MAX
    monster_pool = list(MONSTER_TYPES.keys())
    # Exclude ranged mobs from the base pool (they get added separately)
    base_monsters = [m for m in monster_pool if m in ["rat", "bat", "goblin", "skeleton", "spider", "slime", "pack_hunter"]][:7]
    ranged_monsters = [m for m in monster_pool if MONSTER_TYPES.get(m, {}).get("ranged", False)]
    floor_monsters = list(base_monsters)
    if floor_num >= 3:
        floor_monsters += ["orc", "wraith"]
    if floor_num >= 5:
        floor_monsters += ["demon"]
    if floor_num >= 7:
        floor_monsters += ["dragon"]
    if floor_num >= 3:
        floor_monsters += ["stone_guard"]
    if floor_num >= 4:
        floor_monsters += ["venom_stalker"]
    if floor_num >= 6:
        floor_monsters += ["blood_cultist"]
    # Add ranged mobs to pool on floor 2+
    if floor_num >= 2:
        floor_monsters += ranged_monsters

    for room in rooms[1:]:  # skip first room
        if room.room_type == ROOM_NORMAL:
            count = random.randint(2, 1 + floor_num)
            npc_in_room = 0
            for _ in range(count):
                pos = _free_tile()
                if pos:
                    # Max 1 NPC enemy per room, 30% chance from floor 2+
                    if (floor_num >= NPC_ENEMY_MIN_FLOOR
                            and npc_in_room < NPC_ENEMY_PER_ROOM_MAX
                            and random.random() < NPC_ENEMY_CHANCE):
                        cls = random.choices(NPC_ENEMY_CLASSES, weights=NPC_ENEMY_CLASS_WEIGHTS, k=1)[0]
                        npc_e = NPCEnemy(pos[0], pos[1], cls, floor_num)
                        npc_enemies.append(npc_e)
                        npc_in_room += 1
                    else:
                        mtype = random.choice(floor_monsters)
                        m = Monster(pos[0], pos[1], mtype, floor_num)
                        if floor_num >= 2 and random.random() < min(0.16, 0.025 + floor_num * 0.012):
                            m.promote_elite()
                        monsters.append(m)
        elif room.room_type == ROOM_BOSS:
            boss_names = list(BOSS_TYPES.keys())
            bname = boss_names[min(floor_num // 2, len(boss_names) - 1)]
            pos = room.center
            b = Boss(pos[0], pos[1], bname, floor_num)
            bosses.append(b)
        elif room.room_type == ROOM_TREASURE:
            pos = room.center
            c = Chest(pos[0], pos[1])
            c.generate_loot(floor_num, player.class_name)
            chests.append(c)
        elif room.room_type == ROOM_TRAP:
            for _ in range(random.randint(1, 3)):
                pos = _free_tile()
                if pos:
                    tiles[pos[1]][pos[0]] = "^"
        elif room.room_type == ROOM_EVENT:
            pos = room.center
            tiles[pos[1]][pos[0]] = "*"

    # Extra chests scattered
    for _ in range(random.randint(0, 2)):
        pos = _free_tile()
        if pos:
            c = Chest(pos[0], pos[1])
            c.generate_loot(floor_num, player.class_name)
            chests.append(c)

    return gm, monsters, bosses, chests, rooms, npc_enemies


def _vis_len(s):
    """Calculate visible length of string excluding ANSI escape codes."""
    i, length = 0, 0
    while i < len(s):
        if s[i] == '\x1b':
            while i < len(s) and s[i] != 'm': i += 1
        else:
            length += 1
        i += 1
    return length


def _clamp_color(v):
    return max(0, min(255, int(v)))


def _rgb_scale(rgb, amount):
    return tuple(_clamp_color(c * amount) for c in rgb)


def _rgb_shift(rgb, shift):
    return tuple(_clamp_color(c + s) for c, s in zip(rgb, shift))


def _floor_theme(floor_num: int) -> Dict[str, object]:
    themes = [
        {
            "name": "Damp Caves", "accent": (80, 190, 150),
            "floor_bg": (13, 16, 18), "floor_fg": (45, 62, 58),
            "stone": (80, 92, 96), "fog": (10, 13, 15), "void": (5, 7, 9),
            "water": (45, 130, 180), "hazard": (200, 120, 45),
        },
        {
            "name": "Old Ruins", "accent": (215, 175, 95),
            "floor_bg": (17, 15, 14), "floor_fg": (70, 62, 52),
            "stone": (105, 96, 86), "fog": (13, 12, 12), "void": (7, 7, 8),
            "water": (60, 95, 130), "hazard": (220, 145, 45),
        },
        {
            "name": "Spore Vaults", "accent": (170, 220, 90),
            "floor_bg": (12, 18, 13), "floor_fg": (58, 76, 48),
            "stone": (78, 96, 70), "fog": (8, 13, 9), "void": (4, 7, 4),
            "water": (70, 145, 120), "hazard": (170, 210, 55),
        },
        {
            "name": "Ember Rift", "accent": (255, 135, 55),
            "floor_bg": (22, 13, 10), "floor_fg": (90, 55, 42),
            "stone": (108, 72, 62), "fog": (15, 9, 8), "void": (8, 4, 4),
            "water": (80, 80, 120), "hazard": (255, 95, 35),
        },
        {
            "name": "Black Shrine", "accent": (180, 130, 255),
            "floor_bg": (14, 12, 20), "floor_fg": (58, 50, 76),
            "stone": (84, 74, 108), "fog": (10, 8, 15), "void": (4, 3, 8),
            "water": (90, 80, 180), "hazard": (230, 70, 160),
        },
    ]
    return themes[min((max(1, floor_num) - 1) // 2, len(themes) - 1)]


def _light_for_tile(x, y, player, tile, theme, game_time):
    dist = math.sqrt((x - player.x) ** 2 + (y - player.y) ** 2)
    warm = 0.0
    if tile in (ALTAR, STAIRS_DOWN, SHOP_CHAR):
        warm = 0.20 + 0.08 * math.sin(game_time * 3.0)
    elif _ENV_EFFECTS_AVAILABLE and tile == TILE_BARREL:
        warm = 0.08 + 0.04 * math.sin(game_time * 5.0 + x)
    torch = ((x * 11 + y * 7) % 31 == 0)
    if torch:
        warm = max(warm, 0.10 + 0.05 * math.sin(game_time * 6.0 + x + y))
    return min(1.0, max(0.08, 1.0 - dist * 0.035 + warm))


def _tile_glyph(tile, x, y, gm, game_time):
    if tile == "#":
        return gm.wall_char(x, y)
    if tile == ".":
        variants = [DOT, ".", ",", chr(183)]
        return variants[(x * 3 + y * 5) % len(variants)]
    if tile == STAIRS_DOWN:
        return ARROW
    if tile == ALTAR:
        return "*" if int(game_time * 4) % 2 == 0 else DSTAR
    if tile == "^":
        return "^"
    if tile == SHOP_CHAR:
        return "$"
    if tile == "&":
        return "&"
    if _ENV_EFFECTS_AVAILABLE and tile == TILE_WATER:
        return water_char(game_time, fancy=True) if _FX_AVAILABLE else "~"
    if _ENV_EFFECTS_AVAILABLE and tile == TILE_BARREL:
        return "!"
    if _ENV_EFFECTS_AVAILABLE and tile == TILE_RUBBLE:
        return chr(9617)
    return tile if tile else " "


def _find_entity_at(x, y, monsters, bosses, allies, npc_enemies):
    for group in (bosses, monsters, npc_enemies or [], allies):
        for ent in group:
            if ent.alive and ent.x == x and ent.y == y:
                return ent
    return None


def _inspect_lines(gm, player, monsters, bosses, chests, allies, npc_enemies, combat_sys, pos):
    x, y = pos
    tile = gm.tile(x, y)
    lines = [" Inspect", f" X:{x} Y:{y}"]
    ent = _find_entity_at(x, y, monsters, bosses, allies, npc_enemies)
    chest = next((c for c in chests if c.x == x and c.y == y), None)
    if x == player.x and y == player.y:
        lines += [f" {player.name}", f" HP {player.hp}/{player.max_hp}", f" MP {player.mp}/{player.max_mp}"]
    elif ent:
        hp = getattr(ent, "hp", 0)
        max_hp = getattr(ent, "max_hp", 0)
        lines += [f" {ent.name[:20]}", f" HP {hp}/{max_hp}"]
        defense = getattr(ent, "defense", None)
        atk = getattr(ent, "atk", None)
        if atk is not None:
            lines.append(f" ATK {atk}")
        if defense is not None:
            lines.append(f" DEF {defense}")
        if combat_sys:
            active = []
            for status in ("burn", "slow", "stun", "shield", "buff", "evasion"):
                if combat_sys.has_effect(ent, status):
                    active.append(status)
            if active:
                lines.append(" " + ",".join(active)[:22])
    elif chest:
        state = "opened" if chest.opened else "sealed"
        lines += [f" Chest: {state}", f" Gold: {getattr(chest, 'gold', 0)}"]
    else:
        names = {
            "#": "Stone wall", ".": "Cave floor", STAIRS_DOWN: "Down stairs",
            ALTAR: "Glowing altar", "^": "Trap", SHOP_CHAR: "Shop", "&": "Road marker",
        }
        if _ENV_EFFECTS_AVAILABLE:
            names.update({TILE_WATER: "Cold water", TILE_BARREL: "Explosive barrel", TILE_RUBBLE: "Loose rubble"})
        lines.append(" " + names.get(tile, f"Tile {tile}")[:22])
    lines.append(" TAB/Space: close")
    return lines

# ============================================================
#  Render
# ============================================================
def render(gm, player, monsters, bosses, chests, allies, fov, floor_num, log, combat_sys, show_inv, show_skills, game_time, npc_enemies=None, fx_system=None, inspect_pos=None):
    try:
        import shutil
        term_w = shutil.get_terminal_size().columns
        term_h = shutil.get_terminal_size().lines
    except Exception:
        term_w, term_h = 120, 40

    PANEL_W = 24
    MAP_W = max(40, term_w - 2 * PANEL_W)
    MAP_H = max(10, term_h - 10)
    PBG = bg(THEME_PANEL_BG[0], THEME_PANEL_BG[1], THEME_PANEL_BG[2])
    theme = _floor_theme(floor_num)
    accent = theme["accent"]
    render_now = time.time()

    _has_effect = hasattr(combat_sys, 'has_effect') if combat_sys else False

    def _ui_bar(value, maximum, width=20):
        ratio = max(0.0, min(1.0, value / maximum)) if maximum else 0.0
        filled = int(round(ratio * width))
        return BLK * filled + SH1 * (width - filled), int(ratio * 100)

    buf = [chr(27) + '[H']

    # ===== TOP HUD =====
    hp_ratio = max(0.0, min(1.0, player.hp / player.max_hp)) if player.max_hp > 0 else 0
    if hp_ratio > 0.6:   hr, hg, hb = 80, 200, 80
    elif hp_ratio > 0.3: hr, hg, hb = 210, 190, 60
    else:                hr, hg, hb = 210, 60, 60
    bar_w = 20
    hp_bar, hp_percent = _ui_bar(player.hp, player.max_hp, bar_w)

    mp_ratio = max(0.0, min(1.0, player.mp / player.max_mp)) if player.max_mp > 0 else 0
    mp_bar, mp_percent = _ui_bar(player.mp, player.max_mp, bar_w)

    # Title bar
    buf.append(
        bg(18, 18, 28) + fg(120, 170, 210) + ' ' + DIAM + ' '
        + fg(200, 200, 210) + bold() + 'SIMPLE CAVE ROGUELIKE' + rst()
        + bg(18, 18, 28)
        + f'  {fg(220, 190, 80)}Floor {floor_num}{rst()}'
        + f'  {fg(*accent)}{theme["name"]}{rst()}'
        + f'  {fg(140, 140, 160)}Lv.{player.level}{rst()}'
        + f'  {fg(180, 180, 200)}{player.name}{rst()}'
        + ' ' * 30 + rst()
    )
    # HP bar
    shield_active = combat_sys.has_effect(player, "shield")
    shield_power = combat_sys.get_effect_power(player, "shield") if shield_active else 0
    buf.append(
        bg(18, 18, 28)
        + fg(100, 200, 230) + ' HP '
        + f'{fg(hr, hg, hb)}{player.hp}/{player.max_hp} '
        + bg(hr // 3, hg // 3, hb // 3) + fg(hr, hg, hb)
        + hp_bar + f' {hp_percent:>3d}%'
        + rst()
    )
    if shield_active:
        shield_text = f'  \u26e8 {shield_power}'
        buf.append(
            bg(18, 18, 28)
            + fg(100, 180, 255) + bold() + shield_text + rst()
            + ' ' * 5
            + f'  {fg(100, 200, 230)}MP '
            + f'{fg(80, 130, 255)}{player.mp}/{player.max_mp} '
            + bg(10, 10, 40) + fg(80, 130, 255)
            + mp_bar + f' {mp_percent:>3d}%'
            + rst()
            + ' ' * 10
        )
    else:
        buf.append(
            bg(18, 18, 28)
            + f'  {fg(100, 200, 230)}MP '
            + f'{fg(80, 130, 255)}{player.mp}/{player.max_mp} '
            + bg(10, 10, 40) + fg(80, 130, 255)
            + mp_bar + f' {mp_percent:>3d}%'
            + rst()
            + ' ' * 10
        )
    # Stats
    buf.append(
        bg(18, 18, 28)
        + f' {fg(255,100,100)}STR:{player.str}{rst()}'
        + f' {fg(100,255,100)}AGI:{player.agi}{rst()}'
        + f' {fg(100,150,255)}INT:{player.int_stat}{rst()}'
        + f' {fg(180, 180, 200)}ATK:{fg(255, 150, 150)}{player.atk}{rst()}'
        + f' {fg(180, 180, 200)}DEF:{fg(150, 150, 255)}{player.defense}{rst()}'
        + f' {fg(180, 180, 200)}XP:{fg(150, 255, 150)}{player.xp}/{player.xp_to_next}{rst()}'
        + f' {fg(255, 215, 0)}Gold:{player.inventory.gold}{rst()}'
        + ' ' * 10 + rst()
    )
    active_effects = sorted(combat_sys.get_effects(player)) if combat_sys and hasattr(combat_sys, 'get_effects') else []
    if active_effects:
        buf.append(bg(18, 18, 28) + fg(210, 180, 255) + ' EFFECTS: ' +
                   '  '.join(e.upper() for e in active_effects[:5]) + rst())
    buf.append(bg(18, 18, 28) + SH2 * 80 + rst())

    # ===== FIND NEAREST ENEMY =====
    nearest_enemy = None
    nearest_dist = 999
    for m in monsters:
        if m.alive:
            d = abs(m.x - player.x) + abs(m.y - player.y)
            if d < nearest_dist:
                nearest_dist = d
                nearest_enemy = m
    for b in bosses:
        if b.alive:
            d = abs(b.x - player.x) + abs(b.y - player.y)
            if d < nearest_dist:
                nearest_dist = d
                nearest_enemy = b

    # ===== HELPER: PANEL LINE =====
    def _pnl(text, fg_c=None):
        if fg_c:
            return PBG + fg_c + text.ljust(PANEL_W) + rst()
        return PBG + text.ljust(PANEL_W) + rst()

    # ===== LEFT PANEL (All visible enemies + allies) =====
    left = []
    left.append(_pnl(f' {player.name}', fg(80, 220, 255) + bold()))
    left.append(_pnl(f' Lv.{player.level}  {player.class_name.upper()}', fg(140, 140, 160)))
    left.append(_pnl(f' STR:{player.str} AGI:{player.agi} INT:{player.int_stat}', fg(140, 140, 160)))
    left.append(_pnl(f' ATK:{player.atk} DEF:{player.defense} CRT:{int(player.crit_chance*100)}%', fg(140, 140, 160)))
    left.append(_pnl(f' Dodge:{int(player.dodge_chance*100)}% MP:{player.mp_regen:.1f}/s', fg(140, 140, 160)))
    left.append(_pnl(''))
    left.append(_pnl(' ' + chr(9472) * 13, fg(70, 70, 90)))
    left.append(_pnl(' VISIBLE THREATS', fg(220, 120, 100) + bold()))

    # All visible enemies
    visible_enemies = []
    for m in monsters:
        if m.alive and (m.x, m.y) in fov.visible:
            visible_enemies.append(m)
    for b in bosses:
        if b.alive and (b.x, b.y) in fov.visible:
            visible_enemies.append(b)
    for ne in (npc_enemies or []):
        if ne.alive and (ne.x, ne.y) in fov.visible:
            visible_enemies.append(ne)

    if visible_enemies:
        left.append(_pnl(f' Enemies ({len(visible_enemies)})', fg(220, 80, 80) + bold()))
        for e in visible_enemies[:8]:
            ehp_r = e.hp / e.max_hp if e.max_hp > 0 else 0
            ehp_f = int(ehp_r * 10)
            bar = chr(9608) * ehp_f + chr(9617) * (10 - ehp_f)
            name = ("[ELITE] " if getattr(e, 'is_elite', False) else "") + e.name
            name = name[:18]
            left.append(_pnl(f' {name}', fg(220, 120, 120)))
            left.append(_pnl(f' HP {bar} {int(ehp_r * 100):>3d}%', fg(220, 100, 100)))
    else:
        left.append(_pnl(' No enemies visible', fg(70, 70, 90)))

    left.append(_pnl(' ' + chr(9472) * 13, fg(70, 70, 90)))
    left.append(_pnl(f' PARTY ({sum(1 for a in allies if a.alive)})', fg(100, 220, 140) + bold()))

    # All visible allies
    visible_allies = [a for a in allies if a.alive and (a.x, a.y) in fov.visible]

    if visible_allies:
        left.append(_pnl(f' Allies ({len(visible_allies)})', fg(80, 220, 120) + bold()))
        CLASS_ICONS = {"swordsman": "W", "archer": "A", "mage": "M", "healer": "+", "rogue": "R"}
        for a in visible_allies[:8]:
            ahp_r = a.hp / a.max_hp if a.max_hp > 0 else 0
            ahp_f = int(ahp_r * 10)
            bar = chr(9608) * ahp_f + chr(9617) * (10 - ahp_f)
            if hasattr(a, 'class_name') and a.class_name:
                icon = CLASS_ICONS.get(a.class_name, "?")
            elif hasattr(a, 'ally_type'):
                icon = "S" if a.ally_type == "skeleton" else "?"
            else:
                icon = "?"
            raw_name = a.name
            short_name = raw_name[:16]
            if getattr(a, 'is_infinite', False):
                tag = f'{icon} {short_name} Lv{getattr(a, "level", "?")} \u221e'
            elif hasattr(a, 'duration') and hasattr(a, 'spawn_time'):
                remaining = max(0, int(a.duration - (time.time() - a.spawn_time)))
                tag = f'{icon} {short_name} Lv{getattr(a, "level", "?")} {remaining}s'
            else:
                tag = f'{icon} {short_name} Lv{getattr(a, "level", "?")}'
            if getattr(a, 'equipment_score', 0) > 0:
                tag += f' +{a.equipment_score}'
            left.append(_pnl(f' {tag}', fg(100, 200, 120)))
            heal_note = ''
            if time.time() - getattr(a, 'last_heal_time', -999) < 2.0:
                heal_note = f" +{getattr(a, 'last_heal_amount', 0)}"
            left.append(_pnl(f' HP {bar} {int(ahp_r * 100):>3d}%{heal_note}',
                             fg(120, 255, 150) if heal_note else fg(80, 190, 110)))
    else:
        left.append(_pnl(' No allies visible', fg(70, 70, 90)))
    while len(left) < MAP_H:
        left.append(_pnl(''))

    # ===== RIGHT PANEL (Action Log) =====
    right = []
    if inspect_pos is not None:
        for info in _inspect_lines(gm, player, monsters, bosses, chests, allies, npc_enemies, combat_sys, inspect_pos):
            color = fg(*accent) + bold() if info.strip() == "Inspect" else fg(170, 175, 190)
            right.append(_pnl(info[:PANEL_W - 1], color))
        right.append(_pnl(' ' + chr(9472) * 13, fg(70, 70, 90)))
        remaining = max(0, MAP_H - len(right))
        recent_log = log[-remaining:] if len(log) > remaining else log
    else:
        recent_log = log[-MAP_H:] if len(log) > MAP_H else log
    for msg in recent_log:
        visible = msg[:PANEL_W - 1]
        msg_l = msg.lower()
        # Loot rarity highlighting
        rarity_tag = None
        if 'found:' in msg_l and '[' in visible:
            try:
                bracket_start = visible.rindex('[')
                bracket_end = visible.rindex(']')
                rarity_tag = visible[bracket_start+1:bracket_end].strip().lower()
            except ValueError:
                rarity_tag = None
        if rarity_tag and rarity_tag in RARITY_COLORS:
            color_val = RARITY_COLORS[rarity_tag]
            if isinstance(color_val, str) and color_val == "rainbow":
                c_ = fg(255, 180, 0)
            else:
                c_ = rarity_color(rarity_tag)
        elif 'kill' in msg_l or 'slain' in msg_l:
            c_ = fg(255, 150, 150)
        elif 'found' in msg_l:
            c_ = fg(220, 190, 80)
        elif 'level' in msg_l:
            c_ = fg(100, 255, 100)
        elif 'hit' in msg_l or 'damage' in msg_l or 'trap' in msg_l:
            c_ = fg(220, 100, 100)
        elif 'heal' in msg_l or 'restored' in msg_l:
            c_ = fg(100, 200, 255)
        else:
            c_ = fg(160, 160, 180)
        right.append(_pnl(' ' + visible, c_))
    while len(right) < MAP_H:
        right.append(_pnl(''))

    # ===== MAP VIEWPORT =====
    vw, vh = MAP_W, MAP_H
    sx = max(0, player.x - vw // 2)
    sy = max(0, player.y - vh // 2)
    if fx_system:
        shake_x, shake_y = fx_system.get_shake_offset()
        sx = max(0, sx + shake_x)
        sy = max(0, sy + shake_y)
    ex = min(gm.w, sx + vw)
    ey = min(gm.h, sy + vh)
    if ex - sx < vw: sx = max(0, ex - vw)
    if ey - sy < vh: sy = max(0, ey - vh)

    map_lines = []
    for y in range(sy, ey):
        line = ''
        for x in range(sx, ex):
            t = gm.tile(x, y)
            br = fov.visible.get((x, y))
            exp = (x, y) in fov.explored

            if inspect_pos == (x, y) and (br is not None or exp):
                line += bg(*accent) + fg(5, 8, 10) + bold() + _tile_glyph(t, x, y, gm, game_time) + rst()
            elif x == player.x and y == player.y:
                line += bg(20, 40, 60) + fg(80, 220, 255) + bold() + '@' + rst()
            elif br is not None:
                b = max(0.08, br) * _light_for_tile(x, y, player, t, theme, game_time)
                mob = next((m for m in monsters if m.x == x and m.y == y and m.alive), None)
                boss = next((b_ for b_ in bosses if b_.x == x and b_.y == y and b_.alive), None)
                ally = next((a for a in allies if a.x == x and a.y == y and a.alive), None)
                npc_e = next((ne for ne in (npc_enemies or []) if ne.x == x and ne.y == y and ne.alive), None)
                chest = next((c for c in chests if c.x == x and c.y == y), None)
                popups_here = combat_sys.get_popups_at(x, y)
                proj_here = combat_sys.get_projectile_at(x, y)
                particles_here = fx_system.particles_at(x, y, render_now) if fx_system else []
                flash_rgb = fx_system.flash_at(x, y, render_now) if fx_system else None

                if particles_here and _FX_AVAILABLE:
                    line += render_particle(particles_here[-1], brightness=b)
                elif proj_here:
                    pr, pg, pb = map(int, proj_here.color.split(","))
                    line += bg(int(pr * 0.2 * b), int(pg * 0.2 * b), int(pb * 0.2 * b))
                    line += fg(int(pr * b), int(pg * b), int(pb * b))
                    line += bold() + proj_here.char + rst()
                elif ally:
                    if getattr(ally, 'is_hired', False):
                        # Hired NPCs use role initials so the party is readable
                        # directly on the map, without opening the side panel.
                        role_icons = {
                            'swordsman': ('W', (255, 220, 100)),
                            'archer': ('A', (200, 255, 100)),
                            'mage': ('M', (150, 180, 255)),
                            'healer': ('+', (100, 255, 200)),
                            'rogue': ('R', (220, 100, 255)),
                        }
                        icon, rgb = role_icons.get(getattr(ally, 'class_name', ''), ('N', (150, 255, 180)))
                        line += bg(int(10 * b), int(25 * b), int(18 * b))
                        line += fg(int(rgb[0] * b), int(rgb[1] * b), int(rgb[2] * b))
                        line += bold() + icon + rst()
                    elif getattr(ally, 'is_infinite', False):
                        line += bg(int(10 * b), int(30 * b), int(10 * b))
                        line += fg(int(80 * b), int(255 * b), int(80 * b))
                        line += bold() + 'S' + rst()
                    else:
                        line += bg(int(30 * b), int(25 * b), int(10 * b))
                        line += fg(int(255 * b), int(200 * b), int(80 * b))
                        line += bold() + 's' + rst()
                elif mob:
                    if popups_here:
                        pc = popups_here[0].color.split(",")
                        pr, pg, pb = int(pc[0]), int(pc[1]), int(pc[2])
                        line += bg(int(pr * 0.3 * b), int(pg * 0.3 * b), int(pb * 0.3 * b))
                        line += fg(int(pr * b), int(pg * b), int(pb * b))
                        line += bold() + mob.char + rst()
                    else:
                        # Wound glow: dark-red bg intensity scales with missing HP
                        hp_ratio_m = mob.hp / mob.max_hp if mob.max_hp > 0 else 0
                        wound = max(0.15, 1.0 - hp_ratio_m)
                        line += bg(int(50 * wound * b), int(10 * wound * b), int(10 * wound * b))
                        mr, mg, mb = mob.rgb
                        # Status effect colors (priority: stun > burn > slow)
                        if _has_effect and combat_sys.has_effect(mob, "stun"):
                            line += fg(int(255 * b), int(220 * b), int(50 * b))
                        elif _has_effect and combat_sys.has_effect(mob, "burn"):
                            line += fg(int(255 * b), int(140 * b), int(30 * b))
                        elif _has_effect and combat_sys.has_effect(mob, "slow"):
                            line += fg(int(80 * b), int(200 * b), int(255 * b))
                        else:
                            line += fg(int(mr * b), int(mg * b), int(mb * b))
                        line += bold() + mob.char + rst()
                elif boss:
                    if popups_here:
                        pc = popups_here[0].color.split(",")
                        pr, pg, pb = int(pc[0]), int(pc[1]), int(pc[2])
                        line += bg(int(pr * 0.3 * b), int(pg * 0.3 * b), int(pb * 0.3 * b))
                        line += fg(int(pr * b), int(pg * b), int(pb * b))
                        line += bold() + boss.char + rst()
                    else:
                        # Distinct purple background for bosses
                        line += bg(int(60 * b), int(10 * b), int(60 * b))
                        boss_r, boss_g, boss_b = boss.rgb
                        # Status effect colors (priority: stun > burn > slow)
                        if _has_effect and combat_sys.has_effect(boss, "stun"):
                            line += fg(int(255 * b), int(220 * b), int(50 * b))
                        elif _has_effect and combat_sys.has_effect(boss, "burn"):
                            line += fg(int(255 * b), int(140 * b), int(30 * b))
                        elif _has_effect and combat_sys.has_effect(boss, "slow"):
                            line += fg(int(80 * b), int(200 * b), int(255 * b))
                        else:
                            line += fg(int(boss_r * b), int(boss_g * b), int(boss_b * b))
                        line += bold() + boss.char + rst()
                elif npc_e:
                    # NPC enemy — red tint
                    cr, cg, cb = map(int, npc_e.color.split(","))
                    line += bg(int(cr * 0.2 * b), int(10 * b), int(10 * b))
                    line += fg(int(cr * b), int(cg * b), int(cb * b))
                    line += bold() + '@' + rst()
                elif chest:
                    if chest.opened:
                        line += fg(int(100 * b), int(100 * b), int(100 * b)) + 'x' + rst()
                    else:
                        line += bg(int(40 * b), int(35 * b), int(10 * b))
                        line += fg(int(255 * b), int(215 * b), int(0 * b))
                        line += bold() + '=' + rst()
                elif t == '#':
                    wch = gm.wall_char(x, y)
                    # Base stone — cold dungeon granite with slight purple undertone
                    stone_rgb = theme["stone"]
                    wr = int(stone_rgb[0] * b)
                    wg = int(stone_rgb[1] * b)
                    wb = int(stone_rgb[2] * b)
                    # Top-lit: walls facing up catch light
                    up_open = not gm.is_wall(x, y - 1)
                    down_open = not gm.is_wall(x, y + 1)
                    left_open = not gm.is_wall(x - 1, y)
                    right_open = not gm.is_wall(x + 1, y)
                    if up_open:
                        wr = min(255, wr + 55)
                        wg = min(255, wg + 48)
                        wb = min(255, wb + 60)
                    # Floor-facing edges: mossy damp tint
                    if down_open:
                        wr = min(255, wr + 8)
                        wg = min(255, wg + 18)
                        wb = min(255, wb + 8)
                    # Side edges: deeper shadow
                    if left_open or right_open:
                        wr = max(0, wr - 12)
                        wg = max(0, wg - 12)
                        wb = max(0, wb - 8)
                    # Inner corners: darkest
                    if (up_open and left_open) or (up_open and right_open) or (down_open and left_open) or (down_open and right_open):
                        wr = max(0, wr - 15)
                        wg = max(0, wg - 15)
                        wb = max(0, wb - 10)
                    # Torch warmth: random walls near floor get warm glow
                    torch_hash = (x * 11 + y * 7) % 23
                    if torch_hash == 0 and down_open:
                        wr = min(255, wr + 35)
                        wg = min(255, wg + 18)
                        wb = max(0, wb - 10)
                    # Stone texture cracks
                    crack = (x * 3 + y * 5) % 9
                    if crack == 0:
                        wr = max(0, wr - 15)
                        wg = max(0, wg - 15)
                        wb = max(0, wb - 12)
                    elif crack == 1:
                        wr = min(255, wr + 8)
                        wg = min(255, wg + 6)
                        wb = min(255, wb + 10)
                    # Positional noise
                    hash_val = (x * 7 + y * 13) % 11
                    wr = max(0, min(255, wr + hash_val - 5))
                    wg = max(0, min(255, wg + hash_val - 5))
                    wb = max(0, min(255, wb + hash_val - 5))
                    line += bg(wr // 3, wg // 3, wb // 3)
                    line += fg(wr, wg, wb)
                    line += wch + rst()
                elif t == '.':
                    # Check for popups on floor tiles
                    popups_here = combat_sys.get_popups_at(x, y)
                    if popups_here:
                        pc = popups_here[0].color.split(",")
                        pr, pg, pb = int(pc[0]), int(pc[1]), int(pc[2])
                        line += bg(int(pr * 0.15 * b), int(pg * 0.15 * b), int(pb * 0.15 * b))
                        line += fg(int(pr * b), int(pg * b), int(pb * b))
                        line += bold() + popups_here[0].text + rst()
                    else:
                        # Stone floor with cracks and variation
                        fh = (x * 3 + y * 7) % 11
                        if (x + y) % 2 == 0:
                            floor_bg = theme["floor_bg"]
                            floor_fg = _rgb_shift(theme["floor_fg"], (fh * 2, fh, fh))
                            line += bg(*_rgb_scale(floor_bg, b))
                            line += fg(*_rgb_scale(floor_fg, b))
                            line += _tile_glyph(t, x, y, gm, game_time)
                        else:
                            floor_bg = _rgb_shift(theme["floor_bg"], (-4, -4, -4))
                            floor_fg = _rgb_shift(theme["floor_fg"], (-8 + fh, -8 + fh, -8 + fh))
                            line += bg(*_rgb_scale(floor_bg, b))
                            line += fg(*_rgb_scale(floor_fg, b))
                            line += _tile_glyph(t, x, y, gm, game_time)
                        line += rst()
                elif t == STAIRS_DOWN:
                    popups_here = combat_sys.get_popups_at(x, y)
                    if popups_here:
                        pc = popups_here[0].color.split(",")
                        pr, pg, pb = int(pc[0]), int(pc[1]), int(pc[2])
                        line += fg(int(pr * b), int(pg * b), int(pb * b))
                        line += bold() + popups_here[0].text + rst()
                    else:
                        line += bg(35, 30, 10)
                        line += fg(230, 200, 80) + bold() + ARROW + rst()
                elif t == '^':
                    popups_here = combat_sys.get_popups_at(x, y)
                    if popups_here:
                        pc = popups_here[0].color.split(",")
                        pr, pg, pb = int(pc[0]), int(pc[1]), int(pc[2])
                        line += fg(int(pr * b), int(pg * b), int(pb * b))
                        line += bold() + popups_here[0].text + rst()
                    else:
                        line += bg(int(30 * b), int(15 * b), int(5 * b))
                        line += fg(int(200 * b), int(100 * b), int(40 * b))
                        line += '^' + rst()
                elif t == ALTAR:
                    popups_here = combat_sys.get_popups_at(x, y)
                    if popups_here:
                        pc = popups_here[0].color.split(",")
                        pr, pg, pb = int(pc[0]), int(pc[1]), int(pc[2])
                        line += fg(int(pr * b), int(pg * b), int(pb * b))
                        line += bold() + popups_here[0].text + rst()
                    else:
                        line += bg(int(30 * b), int(25 * b), int(40 * b))
                        line += fg(int(200 * b), int(180 * b), int(255 * b))
                        line += bold() + '*' + rst()
                elif _ENV_EFFECTS_AVAILABLE and t == TILE_WATER:
                    line += bg(*_rgb_scale((8, 18, 34), b))
                    line += fg(*_rgb_scale(theme["water"], b))
                    line += _tile_glyph(t, x, y, gm, game_time) + rst()
                elif _ENV_EFFECTS_AVAILABLE and t == TILE_BARREL:
                    if flash_rgb:
                        line += bg(*_rgb_scale(flash_rgb, 0.35 * b))
                    else:
                        line += bg(int(40 * b), int(25 * b), int(8 * b))
                    line += fg(*_rgb_scale(theme["hazard"], b))
                    line += bold() + '!' + rst()
                elif _ENV_EFFECTS_AVAILABLE and t == TILE_RUBBLE:
                    line += bg(int(20 * b), int(18 * b), int(16 * b))
                    line += fg(int(80 * b), int(75 * b), int(70 * b))
                    line += '\u2591' + rst()
                elif t == SHOP_CHAR:
                    line += bg(int(20 * b), int(30 * b), int(15 * b))
                    line += fg(int(255 * b), int(215 * b), int(0 * b))
                    line += bold() + '$' + rst()
                elif t == '&':
                    line += bg(int(20 * b), int(20 * b), int(25 * b))
                    line += fg(int(120 * b), int(120 * b), int(150 * b))
                    line += '&' + rst()
                else:
                    line += ' '
            elif exp:
                mob = next((m for m in monsters if m.x == x and m.y == y and m.alive), None)
                boss = next((b_ for b_ in bosses if b_.x == x and b_.y == y and b_.alive), None)
                if mob or boss:
                    line += ' '
                elif t == '#':
                    line += bg(*theme["fog"]) + fg(*_rgb_scale(theme["stone"], 0.45)) + gm.wall_char(x, y) + rst()
                elif t == '.':
                    line += bg(*theme["fog"]) + fg(*_rgb_scale(theme["floor_fg"], 0.45)) + _tile_glyph(t, x, y, gm, game_time) + rst()
                elif t == STAIRS_DOWN:
                    line += bg(10, 10, 13) + fg(70, 60, 25) + ARROW + rst()
                elif _ENV_EFFECTS_AVAILABLE and t == TILE_WATER:
                    line += bg(6, 10, 18) + fg(20, 50, 100) + '\u2248' + rst()
                elif _ENV_EFFECTS_AVAILABLE and t == TILE_BARREL:
                    line += bg(16, 10, 4) + fg(80, 55, 18) + '!' + rst()
                elif _ENV_EFFECTS_AVAILABLE and t == TILE_RUBBLE:
                    line += bg(10, 9, 8) + fg(40, 38, 35) + '\u2591' + rst()
                elif t == SHOP_CHAR:
                    line += bg(10, 14, 8) + fg(100, 85, 10) + '$' + rst()
                elif t == '&':
                    line += bg(10, 10, 12) + fg(55, 55, 70) + '&' + rst()
                else:
                    line += ' '
            else:
                line += bg(*theme["void"]) + ' ' + rst()

        map_lines.append(line)

    while len(map_lines) < MAP_H:
        map_lines.append(PBG + ' ' * MAP_W + rst())

    # ===== COMBINE MAP + SIDE PANELS =====
    for i in range(MAP_H):
        buf.append(left[i] + map_lines[i] + rst() + right[i])

    # ===== BOTTOM PANEL =====
    buf.append(bg(18, 18, 28) + SH2 * 80 + rst())

    # Skill bar
    skill_line = bg(18, 18, 28) + ' '
    skill_keys = ['Z', 'X', 'C', 'V', 'B']
    now = time.time()
    for i, sk in enumerate(player.skills[:5]):
        if sk is None:
            skill_line += fg(60, 60, 80) + f' {skill_keys[i]}:[empty] '
        elif sk.ready(now):
            skill_line += fg(80, 200, 80) + f' {skill_keys[i]}:{sk.name[:6]} '
        else:
            remaining = sk.cooldown - (now - sk.last_used)
            skill_line += fg(100, 60, 60) + f' {skill_keys[i]}:{remaining:.0f}s '
    skill_line += rst() + ' ' * 20
    buf.append(skill_line)

    # Status bar
    enemies = sum(1 for m in monsters if m.alive) + sum(1 for b in bosses if b.alive)
    on_stairs = gm.tile(player.x, player.y) == STAIRS_DOWN
    on_chest = any(c.x == player.x and c.y == player.y and not c.opened for c in chests)
    on_event = gm.tile(player.x, player.y) == ALTAR
    on_trap = gm.tile(player.x, player.y) == '^'

    action_hint = ''
    if on_stairs:
        action_hint = fg(220, 200, 80) + bold() + 'SPACE: descend' + rst()
    elif on_chest:
        action_hint = fg(255, 215, 0) + bold() + 'SPACE: open chest' + rst()
    elif on_event:
        action_hint = fg(200, 180, 255) + bold() + 'SPACE: interact' + rst()
    elif on_trap:
        action_hint = fg(200, 100, 50) + 'Disarmed!' + rst()
    else:
        action_hint = fg(140, 140, 160) + 'SPACE: use' + rst()

    buf.append(
        bg(18, 18, 28)
        + fg(220, 80, 80) + f' {enemies} enemies '
        + fg(70, 70, 90) + '|'
        + action_hint
        + fg(70, 70, 90) + '|'
        + fg(160, 160, 180) + ' E:inventory  Del:drop  TAB:inspect  Z-B:skills '
        + ' ' * 30 + rst()
    )
    buf.append('')

    # Pad all lines to terminal width to prevent ghosting
    padded = []
    for line in buf:
        vl = _vis_len(line)
        padding = max(0, term_w - vl)
        padded.append(line + rst() + ' ' * padding)
    # Fill remaining terminal lines with blanks
    while len(padded) < term_h:
        padded.append(' ' * term_w)

    sys.stdout.write(chr(10).join(padded))
    sys.stdout.flush()


# ============================================================
#  Panel helper (must be defined before render_city)
# ============================================================
def _pnl(text, fg_c=None):
    PBG = bg(THEME_PANEL_BG[0], THEME_PANEL_BG[1], THEME_PANEL_BG[2])
    PANEL_W = 24
    if fg_c:
        return PBG + fg_c + text.ljust(PANEL_W) + rst()
    return PBG + text.ljust(PANEL_W) + rst()


# ============================================================
#  City Render
# ============================================================
def render_city(gm, player, shop_items, floor_num, log, shop_cursor,
                show_shop, game_time, shop_name="", party_allies=None):
    try:
        import shutil
        term_w = shutil.get_terminal_size().columns
        term_h = shutil.get_terminal_size().lines
    except Exception:
        term_w, term_h = 120, 40

    PBG = bg(THEME_PANEL_BG[0], THEME_PANEL_BG[1], THEME_PANEL_BG[2])
    buf = [chr(27) + '[H']

    # Title
    buf.append(
        bg(18, 18, 28) + fg(220, 180, 80) + bold() + ' CITY OF SANCTUARY ' + rst()
        + bg(18, 18, 28) + f'  Floor {floor_num}  '
        + fg(255, 215, 0) + f'Gold: {player.inventory.gold}'
        + ' ' * 25 + rst()
    )

    # HP/MP bars
    hp_ratio = max(0.0, min(1.0, player.hp / player.max_hp)) if player.max_hp > 0 else 0
    hr, hg, hb = (80, 200, 80) if hp_ratio > 0.6 else (210, 190, 60) if hp_ratio > 0.3 else (210, 60, 60)
    bar_w = 20
    filled = int(hp_ratio * bar_w)
    mp_ratio = max(0.0, min(1.0, player.mp / player.max_mp)) if player.max_mp > 0 else 0
    mp_filled = int(mp_ratio * bar_w)

    buf.append(
        bg(18, 18, 28)
        + fg(100, 200, 230) + ' HP '
        + f'{fg(hr, hg, hb)}{player.hp}/{player.max_hp} '
        + bg(hr // 3, hg // 3, hb // 3) + fg(hr, hg, hb)
        + BLK * filled + SH1 * (bar_w - filled)
        + rst()
        + f'  {fg(100, 200, 230)}MP '
        + f'{fg(80, 130, 255)}{player.mp}/{player.max_mp} '
        + bg(10, 10, 40) + fg(80, 130, 255)
        + BLK * mp_filled + SH1 * (bar_w - mp_filled)
        + rst() + ' ' * 20
    )
    buf.append(bg(18, 18, 28) + SH2 * 80 + rst())

    # Map
    overlay_lines = 0
    if show_shop:
        overlay_lines = 12  # title + borders + items + help
    MAP_W = max(40, term_w - 40)
    MAP_H = max(10, term_h - 10 - overlay_lines)
    vw, vh = MAP_W, MAP_H
    sx = max(0, player.x - vw // 2)
    sy = max(0, player.y - vh // 2)
    ex = min(gm.w, sx + vw)
    ey = min(gm.h, sy + vh)
    if ex - sx < vw: sx = max(0, ex - vw)
    if ey - sy < vh: sy = max(0, ey - vh)

    map_lines = []
    for y in range(sy, ey):
        line = ''
        for x in range(sx, ex):
            t = gm.tile(x, y)
            if x == player.x and y == player.y:
                line += bg(20, 40, 60) + fg(80, 220, 255) + bold() + '@' + rst()
            elif t == '$':
                line += bg(20, 30, 15) + fg(255, 215, 0) + bold() + '$' + rst()
            elif t == ALTAR:
                line += bg(30, 25, 40) + fg(200, 180, 255) + bold() + ALTAR + rst()
            elif t == '&':
                line += fg(50, 50, 70) + '&' + rst()
            elif t == '>':
                line += bg(35, 30, 10) + fg(230, 200, 80) + bold() + ARROW + rst()
            elif t == '.':
                fh = (x * 3 + y * 7) % 11
                if (x + y) % 2 == 0:
                    line += bg(16, 14, 18) + fg(50 + fh * 2, 46 + fh, 58 + fh) + DOT + rst()
                else:
                    line += bg(12, 10, 14) + fg(38 + fh, 34 + fh, 42 + fh) + DOT + rst()
            elif t == '#':
                line += bg(10, 9, 14) + fg(68, 62, 78) + '#' + rst()
            else:
                line += ' '
        map_lines.append(line)

    while len(map_lines) < MAP_H:
        map_lines.append(PBG + ' ' * MAP_W + rst())

    # Side panel (player + log)
    PANEL_W = 24
    right = []
    right.append(_pnl(f' {player.name} [{player.class_name}]', fg(80, 220, 255)))
    while len(right) < MAP_H:
        right.append(_pnl(''))

    # Combine
    max_lines = max(len(map_lines), len(right))
    while len(map_lines) < max_lines: map_lines.append(' ' * MAP_W)
    while len(right) < max_lines: right.append(' ' * PANEL_W)
    for i in range(max_lines):
        buf.append(map_lines[i] + rst() + right[i])

    # Bottom
    buf.append(bg(18, 18, 28) + SH2 * 80 + rst())
    buf.append(
        bg(18, 18, 28)
        + fg(220, 200, 80) + f' $:Shop  *:Heal  >:Descend '
        + fg(180, 180, 80) + 'M:Meta '
        + fg(140, 140, 160) + '| SPACE: interact'
        + ' ' * 30 + rst()
    )

    # Shop overlay
    if show_shop:
        buf.append('')
        buf.append(fg(255, 215, 0) + bold() + f'  {shop_name or "SHOP"}' + rst())
        buf.append(fg(60, 60, 80) + '  ' + BOX_TL + BOX_H * 50 + BOX_TR + rst())
        for i, item in enumerate(shop_items):
            is_sel = (shop_cursor == i)
            is_ally_offer = isinstance(item, dict) and item.get("kind") == "ally"
            price = int(item.get("cost", 0)) if is_ally_offer else CITY_NPC_BASE_PRICE + floor_num * CITY_PRICE_FLOOR_MULT + i * CITY_PRICE_INDEX_MULT
            num = str(i + 1)
            if is_sel:
                prefix = f'>>>{num}'
            else:
                prefix = f'  {num}'
            rc = fg(150, 255, 190) if is_ally_offer else rarity_color(item.rarity)
            item_name = (f"{item['name']} [{item['class_name']}]" if is_ally_offer else item.name)
            if is_sel:
                buf.append(fg(60, 60, 80) + '  ' + BOX_V + rst()
                           + fg(255, 255, 100) + f' {prefix} {rc}{item_name[:18]:<18s}{rst()}'
                           + fg(255, 215, 0) + f'{price:>5d}g' + rst()
                           + fg(60, 60, 80) + ' ' + BOX_V + rst())
            else:
                buf.append(fg(60, 60, 80) + '  ' + BOX_V + rst()
                           + fg(140, 140, 160) + f' {prefix} {rc}{item_name[:18]:<18s}{rst()}'
                           + fg(200, 180, 80) + f'{price:>5d}g' + rst()
                           + fg(60, 60, 80) + ' ' + BOX_V + rst())
        buf.append(fg(60, 60, 80) + '  ' + BOX_BL + BOX_H * 50 + BOX_BR + rst())
        if any(isinstance(item, dict) and item.get("kind") == "ally" for item in shop_items):
            hired = party_allies or []
            names = ", ".join(a.name.split(" (")[0] for a in hired) or "none"
            buf.append(fg(140, 220, 170) + f'  Party {len(hired)}/{MAX_PARTY_SIZE}: {names[:44]}' + rst())
            buf.append(fg(140, 140, 160) + '  1-9: select | Space: hire | Delete: dismiss last | E/ESC: close' + rst())
        else:
            buf.append(fg(140, 140, 160) + '  1-9: select | Space: buy | E/ESC: close' + rst())

    # Hire overlay
    # Pad
    padded = []
    for line in buf:
        vl = _vis_len(line)
        padding = max(0, term_w - vl)
        padded.append(line + rst() + ' ' * padding)
    while len(padded) < term_h:
        padded.append(' ' * term_w)

    sys.stdout.write(chr(10).join(padded))
    sys.stdout.flush()


# ============================================================
#  Inventory Overlay
# ============================================================
_ITEM_CHARS = {
    "weapon": "/", "helmet": "^", "chest": "]", "legs": "=", "boots": "u",
    "gloves": "g", "necklace": "n", "ring": "o", "cape": "c",
    "consumable": "!", "skill_book": "?",
}

def _inv_cell(item, is_cur):
    """Render one inventory cell. [ X ] format, 5 visible chars."""
    if item:
        ic = _ITEM_CHARS.get(item.item_type, "?")
        rc = rarity_color(item.rarity)
        if is_cur:
            return f"{bg(50,50,70)}[{rc} {ic}{rst()} ]"
        else:
            return f"[{rc} {ic}{rst()} ]"
    else:
        if is_cur:
            return f"{bg(50,50,70)}[   ]"
        else:
            return f"{fg(40,40,50)}[   ]{rst()}"

def render_inventory(player, inv_cur, inv_col):
    """Render full inventory screen."""
    inv = player.inventory
    GRID_COLS = 6
    GRID_ROWS = (inv.max_slots + GRID_COLS - 1) // GRID_COLS
    CW = 5  # cell width (visible chars)
    buf = ["\x1b[2J\x1b[H"]

    # Header
    buf.append(f"  {bold()}{fg(255, 215, 0)}INVENTORY{rst()}  {fg(100, 100, 120)}- press E to close{rst()}")
    buf.append(f"  {fg(255, 215, 0)}Gold: {inv.gold}{rst()}")
    buf.append("")

    # === Left: Equipment ===
    eq_lines = []
    eq_lines.append(f"  {bold()}{fg(0, 200, 200)}Equipment{rst()}")
    for si, sn in enumerate(inv.EQUIP_SLOTS):
        item = inv.equipment.get(sn)
        label = sn.upper()[:9]
        if item:
            ic = _ITEM_CHARS.get(item.item_type, "?")
            rc = rarity_color(item.rarity)
            eq_lines.append(f"  {fg(100,100,120)}{label:9s}{rst()} {rc}[{ic}]{rst()} {item.name[:12]:<12s}")
        else:
            eq_lines.append(f"  {fg(100,100,120)}{label:9s}{rst()} {fg(50,50,70)}[---]{rst()}")
    eq_lines.append("")
    eq_lines.append(f"  {bold()}{fg(0, 200, 200)}Skills{rst()}")
    skl_keys = ["Z", "X", "C", "V", "B"]
    for si in range(5):
        sk = player.skills[si] if si < len(player.skills) else None
        if sk:
            eq_lines.append(f"  {fg(100,100,120)}{skl_keys[si]}{rst()}     {fg(0,200,0)}{sk.name[:16]:<16s}{rst()}")
        else:
            eq_lines.append(f"  {fg(100,100,120)}{skl_keys[si]}{rst()}     {fg(50,50,70)}---{rst()}")

    # === Center: Item Grid ===
    grid_lines = []
    grid_lines.append(f"  {bold()}{fg(0, 200, 200)}Items{rst()}")
    # Top border: ┌─────┬─────┬...┐
    grid_lines.append(f"  {fg(60,60,80)}{BOX_TL}{BOX_H*CW}{BOX_T}" + f"{BOX_H*CW}{BOX_T}" * (GRID_COLS - 2) + f"{BOX_H*CW}{BOX_TR}" + rst())
    for row in range(GRID_ROWS):
        cells = []
        for col in range(GRID_COLS):
            idx = row * GRID_COLS + col
            item = inv.slots[idx] if idx < inv.max_slots else None
            is_cur = (inv_col == 0 and inv_cur == idx)
            cells.append(_inv_cell(item, is_cur))
        grid_lines.append(f"  {fg(60,60,80)}{BOX_V}{rst()}" + f"{fg(60,60,80)}{BOX_V}{rst()}".join(cells) + f"{fg(60,60,80)}{BOX_V}{rst()}")
    # Bottom border
    grid_lines.append(f"  {fg(60,60,80)}{BOX_BL}{BOX_H*CW}{BOX_B}" + f"{BOX_H*CW}{BOX_B}" * (GRID_COLS - 2) + f"{BOX_H*CW}{BOX_BR}" + rst())

    # Merge left and center
    max_lines = max(len(eq_lines), len(grid_lines))
    while len(eq_lines) < max_lines: eq_lines.append("")
    while len(grid_lines) < max_lines: grid_lines.append("")
    for i in range(max_lines):
        vlen = _vis_len(eq_lines[i])
        pad = " " * max(0, 34 - vlen)
        buf.append(eq_lines[i] + pad + grid_lines[i])

    # === Right: Item Card ===
    card_w = 24
    sel_item = None
    if inv_col == 0 and 0 <= inv_cur < inv.max_slots:
        sel_item = inv.slots[inv_cur]
    elif inv_col == 1:
        eq_slots = inv.EQUIP_SLOTS
        if 0 <= inv_cur < len(eq_slots):
            sel_item = inv.equipment.get(eq_slots[inv_cur])

    buf.append("")
    buf.append(f"  {bold()}{fg(200, 200, 220)}Item Info{rst()}")
    buf.append(f"  {fg(60,60,80)}{BOX_TL}{BOX_H*(card_w-2)}{BOX_TR}{rst()}")
    if sel_item:
        nm = sel_item.name[:card_w-4]
        if hasattr(sel_item, 'is_unique') and sel_item.is_unique:
            nm_c = rainbow(nm, time.time())
        else:
            nm_c = rarity_color(sel_item.rarity) + bold() + nm + rst()
        pad = card_w - 4 - len(nm)
        buf.append(f"  {fg(60,60,80)}{BOX_V}{rst()} {nm_c}{' '*pad} {fg(60,60,80)}{BOX_V}{rst()}")
        rl = sel_item.rarity.upper()
        buf.append(f"  {fg(60,60,80)}{BOX_V}{rst()} {rarity_color(sel_item.rarity)}{rl:<{card_w-4}}{rst()}{fg(60,60,80)}{BOX_V}{rst()}")
        buf.append(f"  {fg(60,60,80)}{BOX_LT}{BOX_H*(card_w-2)}{BOX_RT}{rst()}")
        st = sel_item.stat_text()
        if st != "---":
            for part in [st[i:i+card_w-4] for i in range(0, len(st), card_w-4)]:
                buf.append(f"  {fg(60,60,80)}{BOX_V}{rst()} {fg(200,200,100)}{part:<{card_w-4}}{rst()}{fg(60,60,80)}{BOX_V}{rst()}")
        desc = getattr(sel_item, 'description', '') or ""
        if desc:
            for i in range(0, len(desc), card_w-4):
                chunk = desc[i:i+card_w-4]
                buf.append(f"  {fg(60,60,80)}{BOX_V}{rst()} {fg(160,160,180)}{chunk:<{card_w-4}}{rst()}{fg(60,60,80)}{BOX_V}{rst()}")
        act = ""
        if inv_col == 0:
            t = sel_item.item_type
            if t in ("weapon", "helmet", "chest", "legs", "boots", "gloves", "necklace", "ring", "cape"):
                act = "[Space] Equip"
            elif t == "consumable": act = "[Space] Use"
            elif t == "skill_book": act = "[Space] Learn"
        elif inv_col == 1:
            act = "[Space] Unequip"
        if act:
            buf.append(f"  {fg(60,60,80)}{BOX_V}{rst()} {fg(80,200,80)}{act:<{card_w-4}}{rst()}{fg(60,60,80)}{BOX_V}{rst()}")
    else:
        buf.append(f"  {fg(60,60,80)}{BOX_V}{rst()} {fg(80,80,100)}{'Select an item':<{card_w-4}}{rst()}{fg(60,60,80)}{BOX_V}{rst()}")
    buf.append(f"  {fg(60,60,80)}{BOX_BL}{BOX_H*(card_w-2)}{BOX_BR}{rst()}")

    # Footer
    buf.append("")
    buf.append(f"  {dim()}WASD: move | Space: equip/use | Del: drop | E: close{rst()}")

    # Center content
    try:
        import shutil
        term_w = shutil.get_terminal_size().columns
    except Exception:
        term_w = 120
    pad = max(0, (term_w - 80) // 2)
    P = " " * pad
    centered = [P + line if line.strip() else line for line in buf]
    sys.stdout.write("\n".join(centered))
    sys.stdout.flush()


# ============================================================
#  Main Game Loop
# ============================================================
def run_game(class_name: str, player_name: str):
    hide_cursor()
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()

    player = Player(0, 0, class_name)
    player.name = player_name

    # Run tracker integration
    tracker = None
    if _RUN_STATS_AVAILABLE:
        try:
            tracker = RunTracker()
            tracker.start()
        except Exception:
            tracker = None

    # Meta-progression: apply bonuses
    meta = None
    if _META_AVAILABLE:
        try:
            meta = MetaProgression()
            apply_meta_bonuses(player, meta)
        except Exception:
            meta = None

    floor_num = 1
    gm, monsters, bosses, chests, rooms, npc_enemies = gen_floor(floor_num, player)
    fov = FOV(MAP_WIDTH, MAP_HEIGHT)
    combat = CombatSystem()
    fx_system = FXSystem() if _FX_AVAILABLE else None
    combat.fx = fx_system
    inp = InputState()
    allies: List[Ally] = []

    # Start every run with a small random party.  There can never be two
    # healers: the player counts as the healer when playing that class.
    # Healer is reserved for the player: NPC companions never duplicate it.
    party_pool = ["swordsman", "archer", "mage", "rogue"]
    random.shuffle(party_pool)
    starter_party_size = random.randint(1, 2)
    starter_party = party_pool[:starter_party_size]
    occupied_start = {(player.x, player.y)}
    for index, ally_class in enumerate(starter_party):
        spawn_pos = next(((player.x + dx, player.y + dy)
                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                                         (2, 0), (-2, 0), (0, 2), (0, -2))
                          if gm.walkable(player.x + dx, player.y + dy) and
                          (player.x + dx, player.y + dy) not in occupied_start),
                         (player.x, player.y))
        ally = NPCAlly(spawn_pos[0], spawn_pos[1], ally_class, floor_num, "")
        ally.is_hired = True
        ally.hire_cost = 0
        ally._player_ref = player
        allies.append(ally)
        occupied_start.add((ally.x, ally.y))

    party_names = ", ".join(a.name for a in allies)
    log = [f"Welcome to floor {floor_num}!", f"Your party joins you: {party_names}."]
    show_inv = False
    inv_cursor = 0
    inv_col = 0
    game_time = 0.0
    action_cooldown = 0.0
    mp_regen_acc = 0.0
    hp_regen_acc = 0.0
    basic_atk_cd = 0.0
    inv_nav_cd = 0.0
    last_frame = time.time()
    last_move_dx, last_move_dy = 1, 0
    inspect_mode = False
    inspect_pos = (player.x, player.y)

    # City state
    in_city = False
    city_shops = []
    city_shop_items = []
    show_shop = False
    shop_cursor = 0
    shop_just_closed = False
    boss_killed = False
    bosses_killed_count = 0
    already_rewarded_boss_ids: Set[int] = set()
    loot_awarded_ids: Set[int] = set()
    victory_flag = False

    def enter_city():
        nonlocal in_city, city_shops, city_shop_items, gm, monsters, bosses, chests, npc_enemies
        nonlocal show_shop, shop_cursor
        in_city = True
        show_shop = False
        shop_cursor = 0
        tiles, walls, shops, pstart = generate_city(floor_num)
        gm = GameMap(60, 40)
        gm.load(tiles, walls)
        player.x, player.y = pstart
        city_shops = shops
        # The tavern is rebuilt each visit: three randomized recruits are available.
        tavern_pos = next(((x, y) for y in range(2, gm.h - 2) for x in range(2, gm.w - 2)
                           if gm.walkable(x, y) and (x, y) != pstart and
                           all((x, y) != (s["x"], s["y"]) for s in city_shops)), (pstart[0] + 2, pstart[1]))
        tx, ty = tavern_pos
        gm.tiles[ty][tx] = "$"
        recruit_classes = [("swordsman", "Bran", 90), ("archer", "Mira", 100),
                           ("mage", "Oren", 125), ("healer", "Sela", 110),
                           ("rogue", "Vex", 115)]
        random.shuffle(recruit_classes)
        tavern_items = [{"kind": "ally", "class_name": cls, "name": name,
                         "cost": cost + floor_num * 15}
                        for cls, name, cost in recruit_classes[:3]]
        city_shops.append({"x": tx, "y": ty, "name": "TAVERN - HIRE ALLIES", "items": tavern_items})
        city_shop_items = []
        monsters = []
        bosses = []
        chests = []
        npc_enemies = []
        log.append(f"Welcome to City of Sanctuary (Floor {floor_num})!")

    def exit_city():
        nonlocal in_city, floor_num, gm, monsters, bosses, chests, npc_enemies, fov
        nonlocal allies, boss_killed, victory_flag
        in_city = False
        floor_num += 1
        if floor_num > 10:
            show_victory(floor_num - 1, player.turns, player.monsters_killed)
            player.alive = False
            victory_flag = True
            return
        gm, monsters, bosses, chests, rooms, npc_enemies = gen_floor(floor_num, player)
        fov = FOV(MAP_WIDTH, MAP_HEIGHT)
        hired = [a for a in allies if getattr(a, "is_hired", False) and a.alive]
        allies.clear()
        allies.extend(hired[:MAX_PARTY_SIZE])
        occupied = {(player.x, player.y)}
        for ally in allies:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if gm.walkable(player.x + dx, player.y + dy) and (player.x + dx, player.y + dy) not in occupied:
                    ally.x, ally.y = player.x + dx, player.y + dy
                    occupied.add((ally.x, ally.y))
                    break
        boss_killed = False
        already_rewarded_boss_ids.clear()
        log.append(f"Descended to floor {floor_num}!")

    def distribute_unclaimed_chests():
        """Resolve unopened chests at the floor boundary for the party."""
        recipients = [a for a in allies if getattr(a, "is_hired", False) and a.alive]
        if not recipients:
            return
        cursor = 0
        claimed = 0
        for chest in chests:
            if chest.opened:
                continue
            chest.open()
            for item in chest.items:
                recipient = recipients[cursor % len(recipients)]
                if recipient.receive_loot(item):
                    log.append(f"{recipient.name} claims {item.name} from an abandoned chest.")
                    cursor += 1
                elif player.inventory.add_item(item):
                    log.append(f"You recover {item.name} from an abandoned chest.")
            player.inventory.gold += chest.gold
            claimed += 1
        if claimed:
            log.append(f"Party secured loot from {claimed} unopened chest(s).")

    try:
        while player.alive:
            now = time.time()
            dt = now - last_frame
            last_frame = now
            game_time += dt
            if fx_system:
                fx_system.update(now)

            keys = inp.read()
            if "quit" in keys:
                break

            # === CITY MODE ===
            if in_city:
                # Toggle shop
                if "inventory" in keys:
                    if show_shop:
                        show_shop = False
                    else:
                        show_inv = not show_inv
                        if show_inv:
                            inv_cursor = 0
                            inv_col = 0
                            sys.stdout.write("\x1b[2J\x1b[H")
                            sys.stdout.flush()
                            render_inventory(player, inv_cursor, inv_col)
                    continue

                # Meta-progression shop (M key)
                if "meta_shop" in keys and _META_AVAILABLE and meta is not None:
                    try:
                        if show_shop:
                            show_shop = False
                        open_meta_shop(player, meta)
                        sys.stdout.write("\x1b[2J\x1b[H")
                        sys.stdout.flush()
                    except Exception:
                        pass
                    continue

                if show_inv:
                    # Merge held + pressed directional keys for inventory nav
                    inv_keys = set(keys)
                    for action in ("up", "down", "left", "right"):
                        if inp.is_held(action):
                            inv_keys.add(action)
                    inv_cursor, inv_col, inv_nav_cd = handle_inventory_input(
                        player, inv_keys, game_time, inv_cursor, inv_col, inv_nav_cd,
                        log, render_inventory)
                    continue

                # Shop navigation
                if show_shop:
                    current_shop_name = ""
                    for shop in city_shops:
                        if shop["x"] == player.x and shop["y"] == player.y:
                            current_shop_name = shop["name"]
                            break
                    if "quit" in keys:
                        show_shop = False
                        shop_just_closed = True
                    # Number keys 1-9 to select item
                    for i in range(9):
                        if f"hotkey{i}" in keys and i < len(city_shop_items):
                            shop_cursor = i
                    if "action" in keys and city_shop_items and 0 <= shop_cursor < len(city_shop_items):
                        item = city_shop_items[shop_cursor]
                        if isinstance(item, dict) and item.get("kind") == "ally":
                            hired = [a for a in allies if getattr(a, "is_hired", False) and a.alive]
                            if len(hired) >= MAX_PARTY_SIZE:
                                log.append(f"Party is full ({MAX_PARTY_SIZE})!")
                            elif player.inventory.gold < item["cost"]:
                                log.append("Not enough gold!")
                            else:
                                player.inventory.gold -= item["cost"]
                                recruit = NPCAlly(player.x + 1, player.y, item["class_name"], floor_num, item["name"])
                                recruit.is_hired = True
                                recruit.hire_cost = item["cost"]
                                recruit._player_ref = player
                                allies.append(recruit)
                                city_shop_items.pop(shop_cursor)
                                log.append(f"{recruit.name} joined the party for {item['cost']}g!")
                                if not city_shop_items:
                                    show_shop = False
                                elif shop_cursor >= len(city_shop_items):
                                    shop_cursor = len(city_shop_items) - 1
                        else:
                            rarity_mult = {"common": 1.0, "uncommon": 1.3, "rare": 1.8, "epic": 2.5, "mythic": 4.0, "legendary": 6.0}.get(item.rarity, 1.0)
                            price = int((CITY_NPC_BASE_PRICE + floor_num * CITY_PRICE_FLOOR_MULT + shop_cursor * CITY_PRICE_INDEX_MULT) * rarity_mult)
                            if player.inventory.gold >= price:
                                player.inventory.gold -= price
                                if player.inventory.add_item(item):
                                    city_shop_items.pop(shop_cursor)
                                    log.append(f"Bought {item.name} for {price}g!")
                                    if not city_shop_items:
                                        show_shop = False
                                    elif shop_cursor >= len(city_shop_items):
                                        shop_cursor = max(0, len(city_shop_items) - 1)
                                else:
                                    player.inventory.gold += price
                                    log.append("Inventory full!")
                            else:
                                log.append("Not enough gold!")
                    if "delete" in keys and city_shop_items and any(isinstance(i, dict) and i.get("kind") == "ally" for i in city_shop_items):
                        hired = [a for a in allies if getattr(a, "is_hired", False) and a.alive]
                        if hired:
                            fired = hired[-1]
                            allies.remove(fired)
                            log.append(f"{fired.name} was dismissed.")
                        else:
                            log.append("No hired allies to dismiss.")

                # City movement
                dx, dy = 0, 0
                if inp.is_held("up"): dy = -1
                elif inp.is_held("down"): dy = 1
                elif inp.is_held("left"): dx = -1
                elif inp.is_held("right"): dx = 1
                if (dx != 0 or dy != 0) and player.can_move(now):
                    occupied_city = {(player.x, player.y)}
                    if gm.walkable(player.x + dx, player.y + dy) and (player.x + dx, player.y + dy) not in occupied_city:
                        player.move(dx, dy, now, gm.walls, occupied_city)

                # City interactions
                tile = gm.tile(player.x, player.y)
                # Auto-open/close shop on $ tile
                if tile == '$' and not show_shop and not shop_just_closed:
                    # Find which shop we're at
                    for shop in city_shops:
                        if shop["x"] == player.x and shop["y"] == player.y:
                            city_shop_items = shop["items"]
                            show_shop = True
                            shop_cursor = 0
                            log.append(f"Welcome to {shop['name']}!")
                            break
                elif tile != '$':
                    shop_just_closed = False
                    if show_shop:
                        show_shop = False
                        city_shop_items = []

                if "action" in keys and now > action_cooldown and not show_shop:
                    action_cooldown = now + 0.3
                    if tile == ALTAR:
                        player.hp = player.max_hp
                        player.mp = player.max_mp
                        log.append("Altar heals you to full!")
                    elif tile == '>':
                        exit_city()

                # Skills (useful in city for testing)
                for i in range(5):
                    if f"skill{i}" in keys:
                        ok, msg = player.use_skill(i, now)
                        if ok:
                            log.append(msg)

                # Render city
                current_shop_name = ""
                if show_shop:
                    for shop in city_shops:
                        if shop["x"] == player.x and shop["y"] == player.y:
                            current_shop_name = shop["name"]
                            break
                render_city(gm, player, city_shop_items, floor_num, log,
                            shop_cursor, show_shop, game_time, current_shop_name,
                            [a for a in allies if getattr(a, "is_hired", False) and a.alive])
                time.sleep(0.03)
                continue

            # === DUNGEON MODE ===

            # Toggle inventory
            if "inventory" in keys:
                show_inv = not show_inv
                if show_inv:
                    inv_cursor = 0; inv_col = 0
                    sys.stdout.write("\x1b[2J\x1b[H"); sys.stdout.flush()
                    render_inventory(player, inv_cursor, inv_col)
                continue

            if show_inv:
                inv_keys = set(keys)
                for action in ("up", "down", "left", "right"):
                    if inp.is_held(action):
                        inv_keys.add(action)
                inv_cursor, inv_col, inv_nav_cd = handle_inventory_input(
                    player, inv_keys, game_time, inv_cursor, inv_col, inv_nav_cd,
                    log, render_inventory)
                continue

            if "tab" in keys:
                inspect_mode = not inspect_mode
                inspect_pos = (player.x, player.y)

            if inspect_mode:
                ix, iy = inspect_pos
                mdx, mdy = 0, 0
                if inp.is_held("up"):
                    mdy = -1
                elif inp.is_held("down"):
                    mdy = 1
                elif inp.is_held("left"):
                    mdx = -1
                elif inp.is_held("right"):
                    mdx = 1
                if mdx or mdy:
                    inspect_pos = (
                        max(0, min(gm.w - 1, ix + mdx)),
                        max(0, min(gm.h - 1, iy + mdy)),
                    )
                    time.sleep(0.04)
                if "action" in keys:
                    inspect_mode = False
                fov.compute(player.x, player.y, 10, gm.tiles)
                combat.update_popups()
                render(gm, player, monsters, bosses, chests, allies, fov, floor_num, log,
                       combat, show_inv, False, game_time, npc_enemies, fx_system, inspect_pos)
                time.sleep(0.03)
                continue

            # ---- GAMEPLAY MODE ----

            occupied = {(player.x, player.y)}
            for m in monsters:
                if m.alive:
                    occupied.add((m.x, m.y))
            for b in bosses:
                if b.alive:
                    occupied.add((b.x, b.y))
            for ne in npc_enemies:
                if ne.alive:
                    occupied.add((ne.x, ne.y))

            # Movement
            dx, dy = 0, 0
            if inp.is_held("up"):    dy = -1
            elif inp.is_held("down"):  dy = 1
            elif inp.is_held("left"):  dx = -1
            elif inp.is_held("right"): dx = 1

            if dx != 0 or dy != 0:
                last_move_dx, last_move_dy = dx, dy

            moved = False
            if (dx != 0 or dy != 0) and player.can_move(now):
                nx, ny = player.x + dx, player.y + dy

                # Find nearest enemy for auto-attack
                auto_range = 4 if player.class_name == "archer" else 1
                nearest_enemy = None
                nearest_dist = 999
                for m in monsters:
                    if m.alive:
                        d = math.sqrt((m.x - player.x)**2 + (m.y - player.y)**2)
                        if d <= auto_range and d < nearest_dist:
                            nearest_dist = d
                            nearest_enemy = m
                for b in bosses:
                    if b.alive:
                        d = math.sqrt((b.x - player.x)**2 + (b.y - player.y)**2)
                        if d <= auto_range and d < nearest_dist:
                            nearest_dist = d
                            nearest_enemy = b
                for ne in npc_enemies:
                    if ne.alive:
                        d = math.sqrt((ne.x - player.x)**2 + (ne.y - player.y)**2)
                        if d <= auto_range and d < nearest_dist:
                            nearest_dist = d
                            nearest_enemy = ne

                if nearest_enemy and now > basic_atk_cd and player.class_name in ("swordsman", "archer", "rogue"):
                    basic_atk_cd = now + (0.35 if player.class_name == "swordsman" else 0.45 if player.class_name == "rogue" else 0.5)
                    if player.class_name == "archer":
                        def _auto_on_hit(target, hx, hy):
                            t_def = target.defense if hasattr(target, 'defense') else 0
                            skill_miss = max(0.02, 0.10 - player.level * 0.008)
                            dmg, crit = combat._calc_damage(player.atk, t_def, player.crit_chance, skill_miss)
                            if dmg == 0:
                                combat._add_popup(target.x, target.y, "MISS", "200,200,200")
                                return
                            target.take_damage(dmg)
                            if tracker:
                                try:
                                    tracker.log_damage(dmg)
                                except Exception:
                                    pass
                            color = "255,255,100" if crit else "255,200,200"
                            combat._add_popup(target.x, target.y, f"-{dmg}", color)
                            if not target.alive:
                                if isinstance(target, Boss) and id(target) not in already_rewarded_boss_ids:
                                    already_rewarded_boss_ids.add(id(target))
                                    boss_killed = True
                                    xp = combat.calculate_xp(target)
                                    player.gain_xp(xp)
                                    player.monsters_killed += 1
                                    if tracker:
                                        try:
                                            tracker.log_kill(target.name)
                                        except Exception:
                                            pass
                                    gold_drop = BOSS_GOLD_BASE + floor_num * BOSS_GOLD_FLOOR_MULT
                                    player.inventory.gold += gold_drop
                                    log.append(f"KILLED {target.name}! +{gold_drop}g")
                                elif not isinstance(target, Boss):
                                    xp = combat.calculate_xp(target)
                                    player.gain_xp(xp)
                                    player.monsters_killed += 1
                                    if tracker:
                                        try:
                                            tracker.log_kill(target.name)
                                        except Exception:
                                            pass
                                    gold_drop = random.randint(MONSTER_GOLD_MIN, MONSTER_GOLD_MAX_BASE + floor_num * MONSTER_GOLD_FLOOR_MULT)
                                    player.inventory.gold += gold_drop
                                    log.append(f"Killed {target.name}! +{gold_drop}g")
                        combat.add_projectile(
                            player.x, player.y, nearest_enemy.x, nearest_enemy.y,
                            "-", "220,200,140",
                            speed=14.0,
                            on_hit=_auto_on_hit,
                        )
                        dx_a = nearest_enemy.x - player.x
                        dy_a = nearest_enemy.y - player.y
                        steps_a = max(abs(dx_a), abs(dy_a), 1)
                        for s in range(1, steps_a):
                            tx = player.x + int(dx_a * s / steps_a)
                            ty = player.y + int(dy_a * s / steps_a)
                            combat._add_popup(tx, ty, "\u00b7", "180,160,120")
                        combat._add_popup(nearest_enemy.x, nearest_enemy.y - 1, "\u2191", "220,200,140")
                        log.append(f"Auto Shot \u2192 {nearest_enemy.name}!")
                    else:
                        atk_bonus = 1.2 if player.class_name == "swordsman" else 1.0
                        if atk_bonus > 1.0:
                            orig_atk = player.atk
                            try:
                                player.atk = int(player.atk * atk_bonus)
                                result = combat.player_attack_monster(player, nearest_enemy, now)
                            finally:
                                player.atk = orig_atk
                        else:
                            result = combat.player_attack_monster(player, nearest_enemy, now)
                        if result is not None:
                            dmg, crit = result
                            if dmg > 0:
                                if tracker:
                                    try:
                                        tracker.log_damage(dmg)
                                    except Exception:
                                        pass
                                dx_s = nearest_enemy.x - player.x
                                dy_s = nearest_enemy.y - player.y
                                steps_s = max(abs(dx_s), abs(dy_s), 1)
                                slash_char = "\\" if player.class_name == "rogue" else "/"
                                slash_color = "200,255,200" if player.class_name == "rogue" else "220,220,255"
                                for s in range(1, steps_s + 1):
                                    tx = player.x + int(dx_s * s / steps_s)
                                    ty = player.y + int(dy_s * s / steps_s)
                                    combat._add_popup(tx, ty, slash_char, slash_color)
                                combat._add_popup(nearest_enemy.x, nearest_enemy.y - 1, "HIT", "255,200,100")
                                log.append(f"Hit {nearest_enemy.name} for {dmg}!")
                                if not nearest_enemy.alive:
                                    if isinstance(nearest_enemy, Boss) and id(nearest_enemy) not in already_rewarded_boss_ids:
                                        already_rewarded_boss_ids.add(id(nearest_enemy))
                                        boss_killed = True
                                        xp = combat.calculate_xp(nearest_enemy)
                                        player.gain_xp(xp)
                                        player.monsters_killed += 1
                                        if tracker:
                                            try:
                                                tracker.log_kill(nearest_enemy.name)
                                            except Exception:
                                                pass
                                        gold_drop = BOSS_GOLD_BASE + floor_num * BOSS_GOLD_FLOOR_MULT
                                        player.inventory.gold += gold_drop
                                        log.append(f"KILLED {nearest_enemy.name}! +{gold_drop}g")
                                    elif not isinstance(nearest_enemy, Boss):
                                        xp = combat.calculate_xp(nearest_enemy)
                                        player.gain_xp(xp)
                                        player.monsters_killed += 1
                                        if tracker:
                                            try:
                                                tracker.log_kill(nearest_enemy.name)
                                            except Exception:
                                                pass
                                        gold_drop = random.randint(MONSTER_GOLD_MIN, MONSTER_GOLD_MAX_BASE + floor_num * MONSTER_GOLD_FLOOR_MULT)
                                        player.inventory.gold += gold_drop
                                        log.append(f"Killed {nearest_enemy.name}! +{gold_drop}g")
                            else:
                                combat._add_popup(nearest_enemy.x, nearest_enemy.y - 1, "MISS", "200,200,200")
                                log.append(f"Missed {nearest_enemy.name}!")
                elif _ENV_EFFECTS_AVAILABLE and gm.tile(nx, ny) == TILE_BARREL:
                    # Barrel: explode on contact
                    game_state = {
                        "monsters": monsters, "bosses": bosses, "player": player,
                        "npc_enemies": npc_enemies, "allies": allies,
                        "tiles": gm.tiles, "log": log, "combat": combat,
                    }
                    try:
                        explode_barrel(nx, ny, game_state)
                        if fx_system:
                            fx_system.spawn_explosion(nx, ny, n=18)
                            fx_system.add_shake(0.8)
                    except Exception:
                        pass
                    moved = True
                elif gm.walkable(nx, ny):
                    player.move(dx, dy, now, gm.walls, occupied)
                    moved = True
                    # Environment tile effects (water slow, etc.)
                    if _ENV_EFFECTS_AVAILABLE:
                        try:
                            tile_msg = apply_tile_effect(player, gm.tile(player.x, player.y), combat)
                            if tile_msg:
                                log.append(tile_msg)
                        except Exception:
                            pass
                    # Traps activate on step
                    if gm.tile(player.x, player.y) == '^':
                        trap_dmg = random.randint(5 + floor_num * 2, 15 + floor_num * 3)
                        player.hp -= trap_dmg
                        if player.hp <= 0:
                            player.alive = False
                        log.append(f"Trap! -{trap_dmg} HP")
                        gm.tiles[player.y][player.x] = "."

            # Action (space)
            if "action" in keys and now > action_cooldown:
                action_cooldown = now + 0.3
                # Stairs — go to city
                if gm.tile(player.x, player.y) == STAIRS_DOWN:
                    distribute_unclaimed_chests()
                    enter_city()
                # Chest
                chest = next((c for c in chests if c.x == player.x and c.y == player.y and not c.opened), None)
                if chest:
                    chest.open()
                    for item in chest.items:
                        if player.inventory.add_item(item):
                            log.append(f"Found: {item.name} [{item.rarity}]")
                        else:
                            log.append("Inventory full!")
                    player.inventory.gold += chest.gold
                    log.append(f"Found {chest.gold} gold!")
                # Event
                elif gm.tile(player.x, player.y) == "*":
                    events = [
                        "A mysterious altar glows...",
                        "You find a healing spring! +20 HP",
                        "A fairy grants you a blessing!",
                        "You discover a treasure map!",
                        "A ghost tells you a secret...",
                        "A wandering smith leaves a random relic behind!",
                        "A scout marks the safest route ahead!",
                    ]
                    event = random.choice(events)
                    log.append(event)
                    if "healing" in event.lower():
                        player.heal(20)
                    elif "smith" in event.lower():
                        relic = generate_random_item(floor_num + 1, player.class_name)
                        if player.inventory.add_item(relic):
                            log.append(f"Event loot: {relic.short_text()}")
                        else:
                            log.append("The relic is lost: inventory full.")
                    elif "scout" in event.lower():
                        for ally in allies:
                            if getattr(ally, "is_hired", False) and ally.alive:
                                ally.aggro_range += 2
                        log.append("Your allies gain +2 awareness for this floor.")
                    gm.tiles[player.y][player.x] = "."

            # Skills (Z/X/C/V/B)
            for i in range(5):
                if f"skill{i}" in keys:
                    ok, msg = player.use_skill(i, now)
                    if not ok:
                        log.append(msg)
                        continue
                    skill = player.skills[i]
                    if skill is None:
                        continue
                    log.append(f"Used {skill.name}!")
                    if tracker:
                        try:
                            tracker.log_skill(skill.name)
                        except Exception:
                            pass

                    # Self-targeted effects (no enemies needed)
                    if skill.effect in ("heal", "buff", "shield", "evasion"):
                        heal_target = None
                        if skill.effect == "heal" and player.class_name == "healer":
                            heal_target = _most_wounded([player] + [a for a in allies if a.alive], player, 6)
                        heal_before = heal_target.hp if heal_target is not None else None
                        combat.player_use_skill(player, skill, [], now, gm=gm,
                                               allies=allies, heal_target=heal_target)
                        if heal_target is not None and heal_target is not player:
                            healed_for = max(0, heal_target.hp - heal_before)
                            if healed_for:
                                log.append(f"{skill.name} heals {heal_target.name} for {healed_for} HP!")
                        if skill.id == "sword_3":
                            combat.add_effect(player, StatusEffect("buff", skill.effect_duration, 30))
                            combat._add_popup(player.x, player.y - 1, "+30% ATK", "255,200,0")
                        if skill.effect == "evasion":
                            combat.add_effect(player, StatusEffect("evasion", skill.effect_duration, skill.effect_power))
                            combat.add_effect(player, StatusEffect("haste", skill.effect_duration, 30))
                            combat._add_popup(player.x, player.y - 1, f"EVASION +{skill.effect_power}%", "200,200,255")
                        if skill.id == "sword_4":
                            combat.add_effect(player, StatusEffect("haste", skill.effect_duration, 50))
                            combat.add_effect(player, StatusEffect("def_down", skill.effect_duration, 20))
                            combat._add_popup(player.x, player.y - 1, "+50% SPD / -20% DEF", "255,160,80")
                    elif skill.effect == "teleport":
                        # Blink: move 5 tiles in last moved direction
                        old_x, old_y = player.x, player.y
                        blink_dist = 5
                        for step in range(1, blink_dist + 1):
                            nx = player.x + last_move_dx * step
                            ny = player.y + last_move_dy * step
                            if 0 <= nx < gm.w and 0 <= ny < gm.h and gm.walkable(nx, ny) and (nx, ny) not in gm.walls:
                                player.x, player.y = nx, ny
                            else:
                                break
                        combat._add_popup(player.x, player.y - 1, "BLINK", "180,120,255")
                        # Trail effect from old to new position
                        dx_b = player.x - old_x
                        dy_b = player.y - old_y
                        steps = max(abs(dx_b), abs(dy_b), 1)
                        for s in range(1, steps):
                            tx = old_x + int(dx_b * s / steps)
                            ty = old_y + int(dy_b * s / steps)
                            combat._add_popup(tx, ty, "~", "140,80,200")
                    elif skill.effect == "summon":
                        count = skill.effect_power if skill.effect_power > 0 else 1
                        is_infinite = skill.effect_duration == float('inf') or skill.effect_duration <= 0
                        # Count existing infinite skeletons separately
                        inf_skeletons = sum(1 for a in allies if a.alive and
                                            getattr(a, "ally_type", "") == "skeleton" and
                                            getattr(a, "is_infinite", False))
                        MAX_INF = 3
                        for _ in range(count):
                            if is_infinite and inf_skeletons >= MAX_INF:
                                log.append(f"Max skeletons ({MAX_INF}) reached!")
                                break
                            for _2 in range(30):
                                sx = player.x + random.randint(-2, 2)
                                sy = player.y + random.randint(-2, 2)
                                if gm.walkable(sx, sy):
                                    dur = skill.effect_duration if not is_infinite else float('inf')
                                    ally = Ally(sx, sy, "skeleton", dur)
                                    floor_mult = 1 + floor_num * 0.15
                                    ally.max_hp = int((ally.max_hp + player.str * 1.5) * floor_mult)
                                    ally.hp = ally.max_hp
                                    ally.atk = int((ally.atk + player.agi * 0.3) * floor_mult)
                                    allies.append(ally)
                                    if is_infinite:
                                        inf_skeletons += 1
                                    combat._add_popup(sx, sy - 1, "RISE", "100,255,100")
                                    for p in range(4):
                                        px = sx + random.randint(-1, 1)
                                        py = sy + random.randint(-2, 0)
                                        combat._add_popup(px, py, "+", "80,200,80")
                                    log.append(f"Skeleton rises!")
                                    break
                    elif skill.effect == "decoy":
                        for _ in range(20):
                            dx = random.randint(-2, 2)
                            dy = random.randint(-2, 2)
                            wx, wy = player.x + dx, player.y + dy
                            if gm.walkable(wx, wy):
                                ally = Ally(wx, wy, "wraith", skill.effect_duration)
                                allies.append(ally)
                                combat._add_popup(wx, wy - 1, "BONE WALL", "200,200,180")
                                # Bone particle scatter
                                for p in range(5):
                                    px = wx + random.randint(-2, 2)
                                    py = wy + random.randint(-2, 2)
                                    combat._add_popup(px, py, "#", "180,170,150")
                                log.append("Bone wall summoned!")
                                break
                    else:
                        # Damage-dealing skills — find targets
                        targets = []
                        if skill.id == "mage_1":
                            # Chain Lightning: chain between targets, max 3 bounces
                            chain_range = 8
                            hit = set()
                            origin_x, origin_y = player.x, player.y
                            for bounce in range(3):
                                best = None
                                best_dist = 999
                                for m in monsters:
                                    if m.alive and (m.x, m.y) not in hit:
                                        dist = math.sqrt((m.x - origin_x)**2 + (m.y - origin_y)**2)
                                        if dist <= chain_range and dist < best_dist:
                                            best_dist = dist
                                            best = m
                                for b in bosses:
                                    if b.alive and (b.x, b.y) not in hit:
                                        dist = math.sqrt((b.x - origin_x)**2 + (b.y - origin_y)**2)
                                        if dist <= chain_range and dist < best_dist:
                                            best_dist = dist
                                            best = b
                                for ne in npc_enemies:
                                    if ne.alive and (ne.x, ne.y) not in hit:
                                        dist = math.sqrt((ne.x - origin_x)**2 + (ne.y - origin_y)**2)
                                        if dist <= chain_range and dist < best_dist:
                                            best_dist = dist
                                            best = ne
                                if best:
                                    targets.append(best)
                                    hit.add((best.x, best.y))
                                    origin_x, origin_y = best.x, best.y
                                else:
                                    break
                        elif skill.aoe >= 1:
                            for m in monsters:
                                if m.alive:
                                    dist = math.sqrt((m.x - player.x)**2 + (m.y - player.y)**2)
                                    if dist <= skill.range:
                                        targets.append(m)
                            for b in bosses:
                                if b.alive:
                                    dist = math.sqrt((b.x - player.x)**2 + (b.y - player.y)**2)
                                    if dist <= skill.range:
                                        targets.append(b)
                            for ne in npc_enemies:
                                if ne.alive:
                                    dist = math.sqrt((ne.x - player.x)**2 + (ne.y - player.y)**2)
                                    if dist <= skill.range:
                                        targets.append(ne)
                        else:
                            best = None
                            best_dist = 999
                            for m in monsters:
                                if m.alive:
                                    dist = math.sqrt((m.x - player.x)**2 + (m.y - player.y)**2)
                                    if dist <= skill.range and dist < best_dist:
                                        best_dist = dist
                                        best = m
                            for b in bosses:
                                if b.alive:
                                    dist = math.sqrt((b.x - player.x)**2 + (b.y - player.y)**2)
                                    if dist <= skill.range and dist < best_dist:
                                        best_dist = dist
                                        best = b
                            for ne in npc_enemies:
                                if ne.alive:
                                    dist = math.sqrt((ne.x - player.x)**2 + (ne.y - player.y)**2)
                                    if dist <= skill.range and dist < best_dist:
                                        best_dist = dist
                                        best = ne
                            if best:
                                targets.append(best)

                        if targets:
                            atk = player.atk
                            if combat.has_effect(player, "buff"):
                                atk = int(atk * (1 + combat.get_effect_power(player, "buff") / 100.0))
                            skill_stat_bonus = 0
                            if skill.scale_stat:
                                coef = skill.scale_coef if skill.scale_coef > 0 else 0.3
                                stat_value = getattr(player, skill.scale_stat + "_stat", getattr(player, skill.scale_stat, 0))
                                skill_stat_bonus = int(stat_value * coef)

                            def _mk_on_hit(sk, player_ref, atk_val, occ):
                                def _on_hit(target, hx, hy):
                                    if sk.id == "rogue_1" and target.alive:
                                        # Move to the tile behind the target before striking.
                                        bx = target.x + (target.x - player_ref.x)
                                        by = target.y + (target.y - player_ref.y)
                                        if abs(target.x - player_ref.x) >= abs(target.y - player_ref.y):
                                            bx = target.x + (1 if player_ref.x < target.x else -1)
                                            by = target.y
                                        else:
                                            bx = target.x
                                            by = target.y + (1 if player_ref.y < target.y else -1)
                                        if 0 <= bx < gm.w and 0 <= by < gm.h and gm.walkable(bx, by) and (bx, by) not in gm.walls:
                                            player_ref.x, player_ref.y = bx, by
                                    t_def = target.defense if hasattr(target, 'defense') else 0
                                    if combat.has_effect(target, "slow"):
                                        t_def = max(0, t_def - 2)
                                    target_dodge = getattr(target, 'dodge', 0.05)
                                    skill_miss = max(0.02, 0.10 - player_ref.level * 0.008)
                                    crit_chance = player_ref.crit_chance
                                    if sk.effect == "crit_boost":
                                        crit_chance += sk.effect_power / 100.0
                                    dmg, crit = combat._calc_damage(atk_val + sk.damage + skill_stat_bonus, t_def, crit_chance, skill_miss)
                                    if dmg == 0:
                                        combat._add_popup(target.x, target.y, "MISS", "200,200,200")
                                        return
                                    target.take_damage(dmg)
                                    if tracker:
                                        try:
                                            tracker.log_damage(dmg)
                                        except Exception:
                                            pass
                                    color = "255,255,100" if crit else "255,150,150"
                                    combat._add_popup(target.x, target.y, f"-{dmg}", color)

                                    # Apply status effect
                                    if sk.effect and sk.effect_duration > 0 and sk.effect not in ("heal","buff","shield","teleport","summon","decoy"):
                                        if sk.effect == "burn":
                                            combat.add_effect(target, StatusEffect("burn", sk.effect_duration, sk.effect_power))
                                            combat._add_popup(target.x, target.y - 1, "BURN", "255,80,0")
                                        elif sk.effect == "slow":
                                            combat.add_effect(target, StatusEffect("slow", sk.effect_duration, sk.effect_power))
                                            combat._add_popup(target.x, target.y - 1, "SLOW", "100,200,255")
                                        elif sk.effect == "stun":
                                            combat.add_effect(target, StatusEffect("stun", sk.effect_duration))
                                            combat._add_popup(target.x, target.y - 1, "STUN", "255,255,0")
                                        elif sk.effect == "knockback":
                                            dx_k = target.x - player_ref.x
                                            dy_k = target.y - player_ref.y
                                            dist_k = max(1, abs(dx_k) + abs(dy_k))
                                            nx_k = target.x + (dx_k // dist_k) * 2
                                            ny_k = target.y + (dy_k // dist_k) * 2
                                            if 0 <= nx_k < gm.w and 0 <= ny_k < gm.h and (nx_k, ny_k) not in gm.walls:
                                                target.x = nx_k
                                                target.y = ny_k
                                            combat._add_popup(target.x, target.y - 1, "KNOCK", "200,200,255")
                                    if sk.id == "sword_2" and target.alive:
                                        combat.add_effect(target, StatusEffect("weaken", 3.0, 20))
                                        combat._add_popup(target.x, target.y - 1, "WEAKEN", "255,180,120")
                                    if sk.id == "sword_2" and target.alive:
                                        dx_b = target.x - player_ref.x
                                        dy_b = target.y - player_ref.y
                                        step_b = max(1, abs(dx_b) + abs(dy_b))
                                        nx_b = target.x + (dx_b // step_b) * 2
                                        ny_b = target.y + (dy_b // step_b) * 2
                                        if 0 <= nx_b < gm.w and 0 <= ny_b < gm.h and (nx_b, ny_b) not in gm.walls:
                                            target.x, target.y = nx_b, ny_b
                                            combat._add_popup(target.x, target.y, "KNOCK", "200,200,255")
                                    if sk.effect == "lifesteal" and dmg > 0:
                                        heal = int(dmg * sk.effect_power / 100.0)
                                        before_hp = player_ref.hp
                                        player_ref.heal(heal)
                                        actual_heal = player_ref.hp - before_hp
                                        combat._add_popup(player_ref.x, player_ref.y, f"+{actual_heal}", "0,255,100")

                                    if not target.alive:
                                        if isinstance(target, Boss) and id(target) not in already_rewarded_boss_ids:
                                            already_rewarded_boss_ids.add(id(target))
                                            xp = combat.calculate_xp(target)
                                            player_ref.gain_xp(xp)
                                            player_ref.monsters_killed += 1
                                            if tracker:
                                                try:
                                                    tracker.log_kill(target.name)
                                                except Exception:
                                                    pass
                                            gold_drop = BOSS_GOLD_BASE + floor_num * BOSS_GOLD_FLOOR_MULT
                                            player_ref.inventory.gold += gold_drop
                                            boss_killed = True
                                            log.append(f"KILLED {target.name} with {sk.name}! +{gold_drop}g")
                                        elif isinstance(target, Monster):
                                            xp = combat.calculate_xp(target)
                                            player_ref.gain_xp(xp)
                                            player_ref.monsters_killed += 1
                                            if tracker:
                                                try:
                                                    tracker.log_kill(target.name)
                                                except Exception:
                                                    pass
                                            gold_drop = random.randint(MONSTER_GOLD_MIN, MONSTER_GOLD_MAX_BASE + floor_num * MONSTER_GOLD_FLOOR_MULT)
                                            player_ref.inventory.gold += gold_drop
                                            log.append(f"Killed {target.name} with {sk.name}! +{gold_drop}g")
                                        elif hasattr(target, 'class_name'):
                                            # NPCEnemy
                                            xp = target.xp_value if hasattr(target, 'xp_value') else 15
                                            player_ref.gain_xp(xp)
                                            player_ref.monsters_killed += 1
                                            if tracker:
                                                try:
                                                    tracker.log_kill(target.name)
                                                except Exception:
                                                    pass
                                            gold_drop = random.randint(8, 20 + floor_num * 3)
                                            player_ref.inventory.gold += gold_drop
                                            log.append(f"Killed {target.name} with {sk.name}! +{gold_drop}g")
                                return _on_hit

                            sid = skill.id
                            proj_configs = {
                                # === SWORDSMAN — fast melee slashes ===
                                "sword_0":  {"char": "/", "color": "220,220,255", "speed": 22.0, "pierce": True},
                                "sword_1":  {"char": "*", "color": "200,200,255", "speed": 18.0, "pierce": True, "aoe": 1},
                                "sword_2":  {"char": "O", "color": "255,255,100", "speed": 18.0, "pierce": False},
                                # === ARCHER — arrows ===
                                "archer_0": {"char": "-", "color": "220,200,140", "speed": 14.0, "pierce": False},
                                "archer_1": {"char": "-", "color": "220,200,140", "speed": 12.0, "pierce": False},
                                "archer_2": {"char": "-", "color": "100,220,50",  "speed": 12.0, "pierce": False},
                                "archer_3": {"char": "-", "color": "100,200,255", "speed": 12.0, "pierce": False},
                                "archer_4": {"char": "v", "color": "220,200,140", "speed": 16.0, "pierce": True},
                                # === MAGE — magic bolts ===
                                "mage_0":   {"char": "*", "color": "255,120,0",  "speed": 10.0, "pierce": False, "aoe": 1},
                                "mage_1":   {"char": "~", "color": "150,200,255", "speed": 18.0, "pierce": True},
                                "mage_2":   {"char": "*", "color": "180,220,255", "speed": 8.0,  "pierce": False, "aoe": 2},
                                # === SUMMONER ===
                                "summon_1": {"char": "~", "color": "180,80,220",  "speed": 10.0, "pierce": False},
                                "summon_2": {"char": "*", "color": "255,100,0",   "speed": 8.0,  "pierce": False, "aoe": 1},
                            }
                            cfg = proj_configs.get(sid, {"char": skill.name[0].upper(), "color": "255,200,200", "speed": 12.0, "pierce": False})

                            for t in targets:
                                on_hit = _mk_on_hit(skill, player, atk, occupied)
                                aoe_r = cfg.get("aoe", 0)
                                combat.add_projectile(
                                    player.x, player.y, t.x, t.y,
                                    cfg["char"], cfg["color"],
                                    speed=cfg["speed"],
                                    on_hit=on_hit,
                                    pierce=cfg.get("pierce", False),
                                    aoe_radius=aoe_r,
                                )

                            # === VISUAL EFFECTS per skill ===
                            # SWORDSMAN
                            if sid == "sword_0":  # Cleave — slash trail to each target
                                for t in targets:
                                    dx_c = t.x - player.x
                                    dy_c = t.y - player.y
                                    steps_s = max(abs(dx_c), abs(dy_c), 1)
                                    for s in range(1, steps_s + 1):
                                        tx = player.x + int(dx_c * s / steps_s)
                                        ty = player.y + int(dy_c * s / steps_s)
                                        combat._add_popup(tx, ty, "/", "220,220,255")
                                    combat._add_popup(t.x + dy_c, t.y - dx_c, "\\", "180,180,220")
                            elif sid == "sword_1":  # Whirlwind — spinning ring
                                for p in range(8):
                                    angle = p * 45
                                    px = player.x + int(1.5 * math.cos(math.radians(angle)))
                                    py = player.y + int(1.5 * math.sin(math.radians(angle)))
                                    combat._add_popup(px, py, "*", "200,200,255")
                                for p in range(4):
                                    angle = p * 90 + 22
                                    px = player.x + int(1.0 * math.cos(math.radians(angle)))
                                    py = player.y + int(1.0 * math.sin(math.radians(angle)))
                                    combat._add_popup(px, py, "~", "180,180,240")
                            elif sid == "sword_2":  # Shield Bash — impact + shockwave
                                for t in targets:
                                    combat._add_popup(t.x, t.y - 1, "BANG", "255,255,100")
                                    for d in [(-1,0),(1,0),(0,-1),(0,1)]:
                                        combat._add_popup(t.x + d[0], t.y + d[1], "!", "255,200,50")
                            # ARCHER
                            elif sid == "archer_0":  # Quick Shot — arrow trail
                                for t in targets:
                                    dx_a = t.x - player.x
                                    dy_a = t.y - player.y
                                    steps_a = max(abs(dx_a), abs(dy_a), 1)
                                    for s in range(1, steps_a):
                                        tx = player.x + int(dx_a * s / steps_a)
                                        ty = player.y + int(dy_a * s / steps_a)
                                        combat._add_popup(tx, ty, "·", "180,160,120")
                            elif sid == "archer_1":  # Volley — 3 spread arrows
                                for t in targets:
                                    combat._add_popup(t.x, t.y - 2, "↓", "200,180,140")
                                    combat._add_popup(t.x - 1, t.y - 1, "↓", "180,160,120")
                                    combat._add_popup(t.x + 1, t.y - 1, "↓", "180,160,120")
                            elif sid == "archer_2":  # Poison Arrow — toxic drips
                                for t in targets:
                                    combat._add_popup(t.x, t.y - 1, "PSN", "0,220,0")
                                    for p in range(4):
                                        px = t.x + random.randint(-1, 1)
                                        py = t.y + random.randint(-1, 1)
                                        combat._add_popup(px, py, "·", "0,180,0")
                            elif sid == "archer_3":  # Frost Arrow — ice shards
                                for t in targets:
                                    combat._add_popup(t.x, t.y - 1, "ICE", "100,200,255")
                                    for p in range(5):
                                        angle = p * 72
                                        px = t.x + int(1.2 * math.cos(math.radians(angle)))
                                        py = t.y + int(1.2 * math.sin(math.radians(angle)))
                                        combat._add_popup(px, py, "*", "150,220,255")
                            elif sid == "archer_4":  # Arrow Rain — falling barrage
                                for t in targets:
                                    for p in range(7):
                                        px = t.x + random.randint(-3, 3)
                                        py = t.y + random.randint(-4, -1)
                                        combat._add_popup(px, py, "v", "200,180,140")
                            # MAGE
                            elif sid == "mage_0":  # Fireball — trail + explosion
                                for t in targets:
                                    dx_f = t.x - player.x
                                    dy_f = t.y - player.y
                                    steps_f = max(abs(dx_f), abs(dy_f), 1)
                                    for s in range(1, steps_f):
                                        tx = player.x + int(dx_f * s / steps_f)
                                        ty = player.y + int(dy_f * s / steps_f)
                                        combat._add_popup(tx, ty, "≈", "255,100,0")
                                    combat._add_popup(t.x, t.y - 1, "FIRE", "255,120,0")
                                    for p in range(8):
                                        angle = p * 45
                                        px = t.x + int(1.5 * math.cos(math.radians(angle)))
                                        py = t.y + int(1.5 * math.sin(math.radians(angle)))
                                        combat._add_popup(px, py, "*", "255,80,0")
                            elif sid == "mage_1":  # Chain Lightning — zigzag bolts
                                prev_x, prev_y = player.x, player.y
                                for t in targets:
                                    dx_l = t.x - prev_x
                                    dy_l = t.y - prev_y
                                    steps_l = max(abs(dx_l), abs(dy_l), 1)
                                    for s in range(1, steps_l + 1):
                                        tx = prev_x + int(dx_l * s / steps_l)
                                        ty = prev_y + int(dy_l * s / steps_l)
                                        combat._add_popup(tx, ty, "~", "100,180,255")
                                    # Impact spark at target
                                    combat._add_popup(t.x, t.y - 1, "ZAP", "180,220,255")
                                    combat._add_popup(t.x - 1, t.y, "/", "120,180,255")
                                    combat._add_popup(t.x + 1, t.y, "\\", "120,180,255")
                                    combat._add_popup(t.x, t.y - 2, "*", "200,230,255")
                                    prev_x, prev_y = t.x, t.y
                            elif sid == "mage_2":  # Blizzard — ice storm
                                for t in targets:
                                    combat._add_popup(t.x, t.y - 1, "ICE", "180,220,255")
                                    for p in range(10):
                                        px = t.x + random.randint(-3, 3)
                                        py = t.y + random.randint(-3, 1)
                                        combat._add_popup(px, py, "*", "200,230,255")
                            # SUMMONER
                            elif sid == "summon_1":  # Spirit Drain — stream to enemy
                                for t in targets:
                                    dx_d = player.x - t.x
                                    dy_d = player.y - t.y
                                    steps_d = max(abs(dx_d), abs(dy_d), 1)
                                    for s in range(1, steps_d):
                                        tx = t.x + int(dx_d * s / steps_d)
                                        ty = t.y + int(dy_d * s / steps_d)
                                        combat._add_popup(tx, ty, "~", "180,80,220")
                                    combat._add_popup(t.x, t.y - 1, "DRAIN", "180,80,220")
                            elif sid == "summon_2":  # Fire Nova — expanding ring
                                for ring in range(1, 4):
                                    for p in range(8 * ring):
                                        angle = p * (360 / (8 * ring))
                                        px = player.x + int(ring * 1.0 * math.cos(math.radians(angle)))
                                        py = player.y + int(ring * 1.0 * math.sin(math.radians(angle)))
                                        combat._add_popup(px, py, "*", "255,100,0")
                                combat._add_popup(player.x, player.y - 1, "NOVA", "255,150,0")

            # Process status effects on monsters
            for m in monsters:
                if m.alive:
                    combat.process_effects(m, now)

            # Process status effects on bosses
            for b in bosses:
                if b.alive:
                    combat.process_effects(b, now)

            # Process status effects on NPC enemies
            for ne in npc_enemies:
                if ne.alive:
                    combat.process_effects(ne, now)

            # Process status effects on player
            combat.process_effects(player, now)

            # Update projectiles
            combat.update_projectiles(monsters, bosses, player, log, dt, now, npc_enemies, allies)

            # Monster AI
            occupied = {(player.x, player.y)}
            for m in monsters:
                if m.alive:
                    occupied.add((m.x, m.y))
            for b in bosses:
                if b.alive:
                    occupied.add((b.x, b.y))
            for ne in npc_enemies:
                if ne.alive:
                    occupied.add((ne.x, ne.y))
            for a in allies:
                if a.alive:
                    occupied.add((a.x, a.y))

            # Hired party members use role-based tactics and pathfinding.
            hired_allies = [a for a in allies if getattr(a, "is_hired", False) and a.alive]
            summons = [a for a in allies if not getattr(a, "is_hired", False) and a.alive]
            for ally in hired_allies:
                npc_ally_decide_and_act(ally, player, hired_allies, summons,
                                        monsters, bosses, npc_enemies, gm,
                                        occupied, combat, log, now)

            # A companion standing next to an unopened chest can claim it.
            # Loot goes into the ally's personal progression bag.
            if not any(e.alive for e in monsters + bosses + npc_enemies):
                for ally in hired_allies:
                    chest = next((c for c in chests if not c.opened and
                                  abs(c.x - ally.x) + abs(c.y - ally.y) <= 1), None)
                    if chest is None:
                        continue
                    chest.open()
                    for item in chest.items:
                        if ally.receive_loot(item):
                            log.append(f"{ally.name} loots {item.name}.")
                        elif player.inventory.add_item(item):
                            log.append(f"{ally.name} passes {item.name} to you.")
                    player.inventory.gold += chest.gold
                    log.append(f"{ally.name} opened a chest (+{chest.gold}g).")

            for m in monsters:
                if not m.alive:
                    continue
                # Find closest target (player or NPC enemy)
                closest_target = None
                closest_dist = 999
                for t in [player] + [a for a in allies if a.alive] + [ne for ne in npc_enemies if ne.alive]:
                    d = abs(m.x - t.x) + abs(m.y - t.y)
                    if d < closest_dist:
                        closest_dist = d
                        closest_target = t
                
                if closest_target and m.can_see_player(closest_target.x, closest_target.y):
                    dist_p = abs(m.x - closest_target.x) + abs(m.y - closest_target.y)
                    # Cowards and skirmishers disengage when wounded, creating space
                    # instead of blindly walking into the player's weapon.
                    if getattr(m, "flee_hp", 0.0) and m.hp / max(1, m.max_hp) <= m.flee_hp and dist_p <= 4:
                        if not combat.is_stunned(m):
                            old_pos = (m.x, m.y)
                            path = flee_path((m.x, m.y), (closest_target.x, closest_target.y), gm.walls, occupied, 2)
                            if path:
                                m.x, m.y = path[0]
                                m.last_move = now
                                occupied.discard(old_pos)
                                occupied.add((m.x, m.y))
                                continue
                    # Pack hunters become more dangerous when they surround a target.
                    # The bonus is recalculated every turn and never permanently mutates atk.
                    pack_bonus = 0
                    if getattr(m, "behavior", "") == "pack":
                        pack_bonus = min(8, sum(1 for other in monsters
                                               if other is not m and other.alive and
                                               other.monster_type == m.monster_type and
                                               abs(other.x - closest_target.x) + abs(other.y - closest_target.y) <= 2) * 2)
                    original_atk = m.atk
                    m.atk += pack_bonus
                    # Ranged monster AI
                    if hasattr(m, 'ranged') and m.ranged and dist_p > 1:
                        if dist_p <= m.attack_range:
                            combat.monster_ranged_attack(m, closest_target, now, log)
                        else:
                            if not combat.is_stunned(m):
                                old_pos = (m.x, m.y)
                                spd_mult = combat.get_speed_mult(m)
                                old_spd = m.speed
                                try:
                                    m.speed *= spd_mult
                                    result = m.move_towards(closest_target.x, closest_target.y, now, gm.walls, occupied)
                                finally:
                                    m.speed = old_spd
                                if result:
                                    occupied.discard(old_pos)
                                    occupied.add(result)
                                    # Check trap for ranged monster
                                    if _ENV_EFFECTS_AVAILABLE and gm.tile(m.x, m.y) == '^':
                                        try:
                                            check_trap_at_tile(m, '^', m.x, m.y, gm.tiles, floor_num)
                                            log.append(f"{m.name} hit a trap!")
                                        except Exception:
                                            pass
                    else:
                        # Melee monster AI
                        if dist_p <= 1:
                            if closest_target is player:
                                result = combat.monster_attack_player(m, player, now)
                                if result and result[0] > 0:
                                    dmg, crit = result
                                    if tracker:
                                        try:
                                            tracker.damage_taken += dmg
                                        except Exception:
                                            pass
                                    log.append(f"{m.name} hits you for {dmg}!")
                                    if not player.alive:
                                        break
                                elif result and result[0] == 0:
                                    log.append(f"{m.name} missed you!")
                            elif closest_target in allies:
                                result = combat.monster_attack_ally(m, closest_target, now)
                                if result and result[0] > 0:
                                    log.append(f"{m.name} hits {closest_target.name} for {result[0]}!")
                                if result and not closest_target.alive:
                                    log.append(f"{m.name} killed {closest_target.name}!")
                            else:
                                # Attack NPC enemy
                                if (now - m.last_attack) < m.attack_delay:
                                    m.atk = original_atk
                                    continue
                                m.last_attack = now
                                t_def = closest_target.defense if hasattr(closest_target, 'defense') else 0
                                dmg, crit = combat._calc_damage(m.atk, t_def, 0.05)
                                if dmg > 0:
                                    actual = closest_target.take_damage(dmg)
                                    combat._add_popup(closest_target.x, closest_target.y, f"-{actual}", "255,100,100")
                                    if not closest_target.alive:
                                        log.append(f"{m.name} killed {closest_target.name}!")
                        else:
                            if not combat.is_stunned(m):
                                old_pos = (m.x, m.y)
                                spd_mult = combat.get_speed_mult(m)
                                old_spd = m.speed
                                try:
                                    m.speed *= spd_mult
                                    result = m.move_towards(closest_target.x, closest_target.y, now, gm.walls, occupied)
                                finally:
                                    m.speed = old_spd
                                if result:
                                    occupied.discard(old_pos)
                                    occupied.add(result)
                                    # Check trap for melee monster
                                    if _ENV_EFFECTS_AVAILABLE and gm.tile(m.x, m.y) == '^':
                                        try:
                                            check_trap_at_tile(m, '^', m.x, m.y, gm.tiles, floor_num)
                                            log.append(f"{m.name} hit a trap!")
                                        except Exception:
                                            pass
                    m.atk = original_atk
                else:
                    if not combat.is_stunned(m):
                        old_pos = (m.x, m.y)
                        result = m.wander(now, gm.walls, occupied)
                        if result:
                            occupied.discard(old_pos)
                            occupied.add(result)
                            # Check trap for wandering monster
                            if _ENV_EFFECTS_AVAILABLE and gm.tile(m.x, m.y) == '^':
                                try:
                                    check_trap_at_tile(m, '^', m.x, m.y, gm.tiles, floor_num)
                                    log.append(f"{m.name} hit a trap!")
                                except Exception:
                                    pass

            for b in bosses:
                if not b.alive:
                    # Check if boss was just killed (by projectile/player attack earlier)
                    if not boss_killed and id(b) not in already_rewarded_boss_ids:
                        already_rewarded_boss_ids.add(id(b))
                        boss_killed = True
                        bosses_killed_count += 1
                        xp = combat.calculate_xp(b)
                        player.gain_xp(xp)
                        player.monsters_killed += 1
                        gold_drop = BOSS_GOLD_BASE + floor_num * BOSS_GOLD_FLOOR_MULT
                        player.inventory.gold += gold_drop
                        log.append(f"KILLED {b.name}! +{xp} XP, +{gold_drop}g!")
                    continue
                # The player has absolute aggro priority. A boss only chooses
                # an ally when the player is outside its aggro range.
                boss_target = player if b.can_see_player(player.x, player.y) else None
                if boss_target is None:
                    boss_target = min(
                        (a for a in allies if a.alive and b.can_see_player(a.x, a.y)),
                        key=lambda a: abs(b.x - a.x) + abs(b.y - a.y),
                        default=None,
                    )
                if boss_target is not None:
                    dist_p = abs(b.x - boss_target.x) + abs(b.y - boss_target.y)
                    if dist_p <= 1:
                        result = (combat.boss_attack_player(b, player, now)
                                  if boss_target is player else
                                  combat.boss_attack_ally(b, boss_target, now))
                        if result and result[0] > 0:
                            dmg, crit = result
                            if boss_target is player and tracker:
                                try:
                                    tracker.damage_taken += dmg
                                except Exception:
                                    pass
                            victim_name = "you" if boss_target is player else boss_target.name
                            log.append(f"{b.name} hits {victim_name} for {dmg}!")
                            if boss_target is player and not player.alive:
                                break
                        elif result and result[0] == 0:
                            victim_name = "you" if boss_target is player else boss_target.name
                            log.append(f"{b.name} missed {victim_name}!")
                    else:
                        if not combat.is_stunned(b):
                            old_pos = (b.x, b.y)
                            spd_mult = combat.get_speed_mult(b)
                            old_spd = b.speed
                            try:
                                b.speed *= spd_mult
                                result = b.move_towards(boss_target.x, boss_target.y, now, gm.walls, occupied)
                            finally:
                                b.speed = old_spd
                            if result:
                                occupied.discard(old_pos)
                                occupied.add(result)

            # ---- NPC Enemy AI (Utility AI) ----
            for ne in npc_enemies:
                if not ne.alive:
                    continue
                npc_decide_and_act(
                    ne, player, npc_enemies, monsters, bosses,
                    gm.walls, occupied, now, combat, log
                )

            # Random monster loot: every enemy has a small, floor-scaled chance
            # to drop a fully randomized item, not only chests.
            for defeated in monsters + bosses + npc_enemies:
                if defeated.alive or id(defeated) in loot_awarded_ids:
                    continue
                loot_awarded_ids.add(id(defeated))
                if random.random() < min(0.28, 0.08 + floor_num * 0.012):
                    dropped = generate_random_item(floor_num, player.class_name)
                    if player.inventory.add_item(dropped):
                        log.append(f"Loot drop: {dropped.short_text()}")
                        if tracker:
                            try:
                                tracker.log_loot(dropped.name)
                            except Exception:
                                pass

            # Regenerate MP and HP slowly
            mp_regen_acc += player.mp_regen * dt
            if mp_regen_acc >= 1.0:
                amt = int(mp_regen_acc)
                player.restore_mp(amt)
                mp_regen_acc -= amt
            hp_regen_acc += player.hp_regen * dt
            if hp_regen_acc >= 1.0:
                amt = int(hp_regen_acc)
                player.heal(amt)
                if tracker:
                    try:
                        tracker.log_heal(amt)
                    except Exception:
                        pass
                hp_regen_acc -= amt

            # Ally AI — focus on player's nearby enemy, else roam free
            occupied = {(player.x, player.y)}
            for m in monsters:
                if m.alive:
                    occupied.add((m.x, m.y))
            for b in bosses:
                if b.alive:
                    occupied.add((b.x, b.y))
            for a in allies:
                if a.alive:
                    occupied.add((a.x, a.y))

            # Find closest enemy to player within dist 3
            focus_target = None
            focus_dist = 999
            for m in monsters:
                if m.alive:
                    d = abs(m.x - player.x) + abs(m.y - player.y)
                    if d <= 3 and d < focus_dist:
                        focus_dist = d
                        focus_target = m
            for b in bosses:
                if b.alive:
                    d = abs(b.x - player.x) + abs(b.y - player.y)
                    if d <= 3 and d < focus_dist:
                        focus_dist = d
                        focus_target = b
            for ne in npc_enemies:
                if ne.alive:
                    d = abs(ne.x - player.x) + abs(ne.y - player.y)
                    if d <= 3 and d < focus_dist:
                        focus_dist = d
                        focus_target = ne

            for ally in allies[:]:
                if not ally.alive or (not getattr(ally, "is_hired", False) and
                                       not getattr(ally, "is_infinite", False) and ally.expired()):
                    allies.remove(ally)
                    continue
                if getattr(ally, "is_hired", False):
                    continue

                ally_dist = abs(ally.x - player.x) + abs(ally.y - player.y)
                if ally_dist > 10:
                    old_ally_pos = (ally.x, ally.y)
                    ally.x = player.x
                    ally.y = player.y
                    occupied.discard(old_ally_pos)
                    occupied.add((player.x, player.y))
                    continue

                if focus_target:
                    d = abs(focus_target.x - ally.x) + abs(focus_target.y - ally.y)
                    if d <= 1:
                        result = combat.ally_attack(ally, focus_target, now)
                        if result and not focus_target.alive:
                            if isinstance(focus_target, Boss) and id(focus_target) not in already_rewarded_boss_ids:
                                already_rewarded_boss_ids.add(id(focus_target))
                                boss_killed = True
                                xp = combat.calculate_xp(focus_target)
                                player.gain_xp(xp)
                                leveled = ally.gain_xp(xp)
                                player.monsters_killed += 1
                                gold_drop = BOSS_GOLD_BASE + floor_num * BOSS_GOLD_FLOOR_MULT
                                player.inventory.gold += gold_drop
                                log.append(f"{ally.name} killed {focus_target.name}! +{xp} XP +{gold_drop}g")
                                if leveled:
                                    combat._add_popup(ally.x, ally.y - 1, f"LVL {ally.level}", "100,255,200")
                                    log.append(f"{ally.name} leveled up to {ally.level}!")
                            elif not isinstance(focus_target, Boss):
                                xp = combat.calculate_xp(focus_target)
                                player.gain_xp(xp)
                                leveled = ally.gain_xp(xp)
                                player.monsters_killed += 1
                                gold_drop = random.randint(3, 10 + floor_num * 2)
                                player.inventory.gold += gold_drop
                                log.append(f"{ally.name} killed {focus_target.name}! +{xp} XP +{gold_drop}g")
                                if leveled:
                                    combat._add_popup(ally.x, ally.y - 1, f"LVL {ally.level}", "100,255,200")
                                    log.append(f"{ally.name} leveled up to {ally.level}!")
                    else:
                        old_pos = (ally.x, ally.y)
                        result = ally.move_towards(focus_target.x, focus_target.y, now, gm.walls, occupied)
                        if result:
                            occupied.discard(old_pos)
                            occupied.add(result)
                else:
                    roam_target = None
                    roam_dist = 999
                    for m in monsters:
                        if m.alive and has_line_of_sight(ally.x, ally.y, m.x, m.y, gm.walls):
                            d = abs(m.x - ally.x) + abs(m.y - ally.y)
                            if d < roam_dist:
                                roam_dist = d
                                roam_target = m
                    for b in bosses:
                        if b.alive and has_line_of_sight(ally.x, ally.y, b.x, b.y, gm.walls):
                            d = abs(b.x - ally.x) + abs(b.y - ally.y)
                            if d < roam_dist:
                                roam_dist = d
                                roam_target = b
                    for ne in npc_enemies:
                        if ne.alive and has_line_of_sight(ally.x, ally.y, ne.x, ne.y, gm.walls):
                            d = abs(ne.x - ally.x) + abs(ne.y - ally.y)
                            if d < roam_dist:
                                roam_dist = d
                                roam_target = ne

                    if roam_target:
                        if roam_dist <= 1:
                            result = combat.ally_attack(ally, roam_target, now)
                            if result and not roam_target.alive:
                                if isinstance(roam_target, Boss) and id(roam_target) not in already_rewarded_boss_ids:
                                    already_rewarded_boss_ids.add(id(roam_target))
                                    boss_killed = True
                                    xp = combat.calculate_xp(roam_target)
                                    player.gain_xp(xp)
                                    leveled = ally.gain_xp(xp)
                                    player.monsters_killed += 1
                                    gold_drop = BOSS_GOLD_BASE + floor_num * BOSS_GOLD_FLOOR_MULT
                                    player.inventory.gold += gold_drop
                                    log.append(f"{ally.name} killed {roam_target.name}! +{xp} XP +{gold_drop}g")
                                    if leveled:
                                        combat._add_popup(ally.x, ally.y - 1, f"LVL {ally.level}", "100,255,200")
                                        log.append(f"{ally.name} leveled up to {ally.level}!")
                                elif not isinstance(roam_target, Boss):
                                    xp = combat.calculate_xp(roam_target)
                                    player.gain_xp(xp)
                                    leveled = ally.gain_xp(xp)
                                    player.monsters_killed += 1
                                    gold_drop = random.randint(3, 10 + floor_num * 2)
                                    player.inventory.gold += gold_drop
                                    log.append(f"{ally.name} killed {roam_target.name}! +{xp} XP +{gold_drop}g")
                                    if leveled:
                                        combat._add_popup(ally.x, ally.y - 1, f"LVL {ally.level}", "100,255,200")
                                        log.append(f"{ally.name} leveled up to {ally.level}!")
                        else:
                            old_pos = (ally.x, ally.y)
                            result = ally.move_towards(roam_target.x, roam_target.y, now, gm.walls, occupied)
                            if result:
                                occupied.discard(old_pos)
                                occupied.add(result)
                    else:
                        dist_to_player = abs(ally.x - player.x) + abs(ally.y - player.y)
                        if dist_to_player > 2:
                            old_pos = (ally.x, ally.y)
                            result = ally.move_towards(player.x, player.y, now, gm.walls, occupied)
                            if result:
                                occupied.discard(old_pos)
                                occupied.add(result)

            # ---- Party AI (NPC Allies hired in city) ----
            all_enemies = [m for m in monsters if m.alive] + [b for b in bosses if b.alive] + [ne for ne in npc_enemies if ne.alive]

            # FOV
            fov.compute(player.x, player.y, 10, gm.tiles)

            # Update popups
            combat.update_popups()

            # Render
            render(gm, player, monsters, bosses, chests, allies, fov, floor_num, log,
                   combat, show_inv, False, game_time, npc_enemies, fx_system,
                   inspect_pos if inspect_mode else None)

            time.sleep(0.03)

    except KeyboardInterrupt:
        pass
    finally:
        show_cursor()

    if not player.alive:
        # Run stats — finish and save
        if tracker:
            try:
                tracker.finish(floor_num, "victory!" if victory_flag else "killed in combat")
                tracker.save_to_history()
            except Exception:
                pass
        # Meta-progression: award points on death
        if meta is not None:
            try:
                earned = meta.add_points(floor_num, player.monsters_killed, bosses_killed_count)
                meta.save()
            except Exception:
                pass
        show_death(floor_num, player.turns, player.monsters_killed, player_name, class_name,
                   stats=tracker.to_dict() if tracker else None)
