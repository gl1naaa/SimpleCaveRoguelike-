# ============================================================
#  Simple Cave Roguelike — Configuration
# ============================================================
import os
import json

# --- Defaults (used if config.json is missing or corrupt) ---

_DEFAULTS = {
    "display": {
        "screen_width": 120, "screen_height": 40,
        "viewport_w": 80, "viewport_h": 22,
        "fps": 30, "font_name": "Consolas", "font_size": 28, "font_weight": 400,
    },
    "map": {
        "width": 80, "height": 50, "room_min": 5, "room_max": 12,
        "connect_chance": 0.2, "bsp_room_chance": 0.8, "corridor_width": 3,
        "extra_corridors_divisor": 3,
    },
    "player": {
        "char": "@", "max_hp": 100, "max_mp": 50, "base_atk": 10, "base_def": 5,
        "base_speed": 150, "move_delay": 0.12, "skill_cooldown": 100,
        "xp_base": 40, "xp_exponent": 1.4, "dodge_cap": 0.40,
        "level_up_primary": 3, "level_up_secondary": 1,
    },
    "combat": {
        "crit_multiplier": 2.0, "damage_variance": 0.25,
        "basic_atk_cooldown_swordsman": 0.35, "basic_atk_cooldown_rogue": 0.45,
        "basic_atk_cooldown_others": 0.5, "auto_range_archer": 4,
        "auto_range_melee": 1, "swordsman_atk_bonus": 1.2,
        "skill_miss_base": 0.10, "skill_miss_per_level": 0.008, "skill_miss_min": 0.02,
        "monster_gold_min": 8, "monster_gold_max_base": 25, "monster_gold_floor_mult": 3,
        "boss_gold_base": 50, "boss_gold_floor_mult": 20,
        "trap_damage_min": 5, "trap_damage_max": 15, "event_heal_amount": 20,
        "archer_projectile_speed": 14.0, "blink_distance": 5,
    },
    "movement": {"move_cooldown": 150, "skill_cooldown": 300, "monster_tick": 180},
    "inventory": {"size": 20, "cols": 6, "rows": 5},
    "skills": {"keys": ["z", "x", "c", "v", "b"], "num_slots": 5},
    "rarity": {
        "order": ["common", "uncommon", "rare", "epic", "mythic", "legendary", "unique"],
        "weights": {"common": 30, "uncommon": 25, "rare": 22, "epic": 14,
                     "mythic": 5, "legendary": 2.0, "unique": 0.5},
        "stat_mult": {"common": 1.0, "uncommon": 1.3, "rare": 1.7, "epic": 2.2,
                       "mythic": 3.0, "legendary": 4.0, "unique": 1.0},
        "colors": {"common": [170,170,170], "uncommon": [80,200,80], "rare": [80,130,255],
                    "epic": [180,80,255], "mythic": [255,60,60], "legendary": [255,255,60],
                    "unique": "rainbow"},
    },
    "weapons": {
        "sword": {"atk_base": 5, "atk_range": 4, "class_req": "swordsman"},
        "bow":   {"atk_base": 4, "atk_range": 5, "class_req": "archer"},
        "staff": {"atk_base": 3, "atk_range": 3, "class_req": "mage"},
        "orb":   {"atk_base": 2, "atk_range": 4, "class_req": "summoner"},
        "mace":  {"atk_base": 4, "atk_range": 3, "class_req": "healer"},
        "dagger":{"atk_base": 5, "atk_range": 4, "class_req": "rogue"},
    },
    "armor": {
        "light":  {"def_base": 2, "def_range": 3},
        "medium": {"def_base": 4, "def_range": 4},
        "heavy":  {"def_base": 7, "def_range": 5},
    },
    "helmet_types": {
        "leather_helm": {"def_base": 1, "def_range": 2, "hp": 5},
        "chain_helm":   {"def_base": 2, "def_range": 3, "hp": 8},
        "plate_helm":   {"def_base": 3, "def_range": 4, "hp": 12},
    },
    "chest_types": {
        "leather_chest": {"def_base": 2, "def_range": 3, "hp": 8},
        "chain_chest":   {"def_base": 4, "def_range": 4, "hp": 12},
        "plate_chest":   {"def_base": 6, "def_range": 5, "hp": 18},
    },
    "legs_types": {
        "leather_legs": {"def_base": 1, "def_range": 2, "agi": 1},
        "chain_legs":   {"def_base": 2, "def_range": 3, "agi": 1},
        "plate_legs":   {"def_base": 3, "def_range": 4, "agi": 0},
    },
    "boots_types": {
        "leather_boots": {"def_base": 1, "def_range": 1, "speed": 8},
        "chain_boots":   {"def_base": 1, "def_range": 2, "speed": 4},
        "plate_boots":   {"def_base": 2, "def_range": 3, "speed": 0},
    },
    "gloves_types": {
        "leather_gloves": {"def_base": 0, "def_range": 1, "atk": 2},
        "chain_gloves":   {"def_base": 1, "def_range": 2, "atk": 3},
        "plate_gloves":   {"def_base": 2, "def_range": 2, "atk": 4},
    },
    "necklace_types": {
        "crystal":  {"mp": 10, "int": 2},
        "ruby":     {"hp": 15, "str": 2},
        "sapphire": {"mp": 18, "int": 3},
        "emerald":  {"hp": 10, "agi": 2},
    },
    "cape_types": {
        "cloth":  {"speed": 5, "agi": 1},
        "fur":    {"hp": 10, "def": 1},
        "shadow": {"speed": 10, "crit": 2},
        "arcane": {"mp": 12, "int": 2},
    },
    "player_classes": {
        "swordsman": {"weapon": "sword", "desc": "Melee tank, high STR and HP"},
        "archer":    {"weapon": "bow",   "desc": "Ranged DPS, high AGI and crits"},
        "mage":      {"weapon": "staff", "desc": "Glass cannon, high INT and spells"},
        "summoner":  {"weapon": "orb",   "desc": "Universal, all stats scale allies"},
        "healer":    {"weapon": "mace",  "desc": "Support, heals allies, buffs, restores MP"},
        "rogue":     {"weapon": "dagger","desc": "Melee DPS, high crits, poison, evasion"},
    },
    "rooms": {"weights": {"normal": 55, "treasure": 18, "boss": 12, "trap": 10, "event": 5}},
    "monster_scaling": {
        "hp_scale": 18, "atk_scale": 4.0, "def_scale": 1.0,
        "base_per_floor": 6, "scale_per_floor": 3,
    },
    "npc_enemies": {
        "chance": 0.3, "min_floor": 2, "per_room_max": 1,
        "classes": ["swordsman", "archer", "mage", "healer", "rogue"],
        "class_weights": [25, 25, 20, 15, 15],
    },
    "npc_ai": {
        "flee_hp": 0.3, "kite_range": 3, "heal_hp": 0.5, "heal_range": 6,
        "heal_cooldown": 2.0, "flank_chance": 0.6, "bfs_depth": 15,
        "update_interval": 0.3,
    },
    "party": {
        "max_size": 5, "max_infinite_skeletons": 3,
        "ally_focus_range": 3, "ally_leash_range": 10, "ally_follow_distance": 2,
    },
    "fov": {"radius": 10, "ray_count": 720, "min_brightness": 0.05},
    "chest_loot": {"min_items": 1, "max_items": 3, "gold_min": 15, "gold_max": 70, "gold_floor_divisor": 3},
    "unique_items": {"drop_chance": 0.005},
    "consumable_value": {"base": 15, "floor_mult": 3},
    "class_weapon_affinity": 0.65,
    "city": {"base_price": 50, "price_floor_mult": 20, "price_index_mult": 10,
             "width": 60, "height": 40, "items_per_shop": 3},
    "gameplay": {"total_floors": 10, "victory_floor": 10},
    "colors": {
        "hud_bg": [18,18,28], "hud_fg": [180,180,200], "player": [80,220,255],
        "wall": [90,80,100], "floor": [50,48,55], "fog_wall": [42,40,50],
        "fog_floor": [28,26,32], "stair": [230,200,80], "chest": [200,170,60],
        "monster": [220,70,70], "boss": [200,40,200], "trap": [200,120,40],
        "shop": [80,200,120],
    },
    "display_symbols": {"stairs_down": ">", "chest": "=", "trap": "^", "shop": "$", "altar": "*"},
    "boss_scaling": {"phase2_threshold": 0.5, "phase3_threshold": 0.3,
                     "phase2_atk_mult": 1.3, "phase3_atk_mult": 1.5,
                     "boss_base_dodge": 0.10, "boss_aggro_range": 10},
    "monster_base_stats": {"base_dodge": 0.05, "aggro_range": 6},
}


def _load_json():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _deep_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def _tuple(lst):
    if isinstance(lst, list) and len(lst) >= 3:
        return (lst[0], lst[1], lst[2])
    return lst


_cfg = _load_json()


def _validate_cfg(cfg, defaults, prefix=""):
    """Validate numeric config values — fall back to defaults if wrong type."""
    for key, default_val in defaults.items():
        if isinstance(default_val, dict):
            if key in cfg and isinstance(cfg[key], dict):
                _validate_cfg(cfg[key], default_val, f"{prefix}{key}.")
            elif key not in cfg:
                cfg[key] = default_val
        else:
            if key in cfg:
                val = cfg[key]
                if type(val) is not type(default_val):
                    if isinstance(default_val, (int, float)) and isinstance(val, (int, float)):
                        pass
                    else:
                        cfg[key] = default_val
            else:
                cfg[key] = default_val


_validate_cfg(_cfg, _DEFAULTS)

# --- Display ---
SCREEN_WIDTH  = _deep_get(_cfg, "display", "screen_width",  default=_DEFAULTS["display"]["screen_width"])
SCREEN_HEIGHT = _deep_get(_cfg, "display", "screen_height", default=_DEFAULTS["display"]["screen_height"])
VIEWPORT_W    = _deep_get(_cfg, "display", "viewport_w",    default=_DEFAULTS["display"]["viewport_w"])
VIEWPORT_H    = _deep_get(_cfg, "display", "viewport_h",    default=_DEFAULTS["display"]["viewport_h"])
FPS           = _deep_get(_cfg, "display", "fps",           default=_DEFAULTS["display"]["fps"])

# --- Map ---
MAP_WIDTH  = _deep_get(_cfg, "map", "width",  default=_DEFAULTS["map"]["width"])
MAP_HEIGHT = _deep_get(_cfg, "map", "height", default=_DEFAULTS["map"]["height"])
ROOM_MIN   = _deep_get(_cfg, "map", "room_min", default=_DEFAULTS["map"]["room_min"])
ROOM_MAX   = _deep_get(_cfg, "map", "room_max", default=_DEFAULTS["map"]["room_max"])
CONNECT_CHANCE = _deep_get(_cfg, "map", "connect_chance", default=_DEFAULTS["map"]["connect_chance"])

# --- Player defaults ---
PLAYER_CHAR      = _deep_get(_cfg, "player", "char",      default=_DEFAULTS["player"]["char"])
PLAYER_MAX_HP    = _deep_get(_cfg, "player", "max_hp",    default=_DEFAULTS["player"]["max_hp"])
PLAYER_MAX_MP    = _deep_get(_cfg, "player", "max_mp",    default=_DEFAULTS["player"]["max_mp"])
PLAYER_BASE_ATK  = _deep_get(_cfg, "player", "base_atk",  default=_DEFAULTS["player"]["base_atk"])
PLAYER_BASE_DEF  = _deep_get(_cfg, "player", "base_def",  default=_DEFAULTS["player"]["base_def"])
PLAYER_BASE_SPEED = _deep_get(_cfg, "player", "base_speed", default=_DEFAULTS["player"]["base_speed"])

# --- Game symbols ---
STAIRS_DOWN = _deep_get(_cfg, "display_symbols", "stairs_down", default=_DEFAULTS["display_symbols"]["stairs_down"])
CHEST_CHAR  = _deep_get(_cfg, "display_symbols", "chest",       default=_DEFAULTS["display_symbols"]["chest"])
TRAP_CHAR   = _deep_get(_cfg, "display_symbols", "trap",        default=_DEFAULTS["display_symbols"]["trap"])
SHOP_CHAR   = _deep_get(_cfg, "display_symbols", "shop",        default=_DEFAULTS["display_symbols"]["shop"])
ALTAR       = _deep_get(_cfg, "display_symbols", "altar",       default=_DEFAULTS["display_symbols"]["altar"])

# --- Movement cooldown (ms) ---
MOVE_COOLDOWN  = _deep_get(_cfg, "movement", "move_cooldown",  default=_DEFAULTS["movement"]["move_cooldown"])
SKILL_COOLDOWN = _deep_get(_cfg, "movement", "skill_cooldown", default=_DEFAULTS["movement"]["skill_cooldown"])
MONSTER_TICK   = _deep_get(_cfg, "movement", "monster_tick",   default=_DEFAULTS["movement"]["monster_tick"])

# --- Combat ---
CRIT_MULTIPLIER = _deep_get(_cfg, "combat", "crit_multiplier", default=_DEFAULTS["combat"]["crit_multiplier"])

# --- Inventory ---
INVENTORY_SIZE = _deep_get(_cfg, "inventory", "size", default=_DEFAULTS["inventory"]["size"])
INV_COLS       = _deep_get(_cfg, "inventory", "cols", default=_DEFAULTS["inventory"]["cols"])
INV_ROWS       = _deep_get(_cfg, "inventory", "rows", default=_DEFAULTS["inventory"]["rows"])

# --- Skill slots ---
SKILL_KEYS      = _deep_get(_cfg, "skills", "keys",      default=_DEFAULTS["skills"]["keys"])
NUM_SKILL_SLOTS = _deep_get(_cfg, "skills", "num_slots", default=_DEFAULTS["skills"]["num_slots"])

# --- Rarity ---
_r_w = _deep_get(_cfg, "rarity", "weights", default=_DEFAULTS["rarity"]["weights"])
_r_sm = _deep_get(_cfg, "rarity", "stat_mult", default=_DEFAULTS["rarity"]["stat_mult"])
_r_c = _deep_get(_cfg, "rarity", "colors", default=_DEFAULTS["rarity"]["colors"])

RARITY_ORDER = _deep_get(_cfg, "rarity", "order", default=_DEFAULTS["rarity"]["order"])
RARITY_COLORS = {
    k: (tuple(v) if isinstance(v, list) else v)
    for k, v in _r_c.items()
}
RARITY_WEIGHTS = {k: v for k, v in _r_w.items()}
RARITY_STAT_MULT = {k: v for k, v in _r_sm.items()}

# --- Item types ---
ITEM_WEAPON    = "weapon"
ITEM_ARMOR     = "armor"
ITEM_RING      = "ring"
ITEM_CONSUMABLE = "consumable"
ITEM_SKILL_BOOK = "skill_book"
ITEM_HELMET    = "helmet"
ITEM_CHEST     = "chest"
ITEM_LEGS      = "legs"
ITEM_BOOTS     = "boots"
ITEM_GLOVES    = "gloves"
ITEM_NECKLACE  = "necklace"
ITEM_CAPE      = "cape"

EQUIPABLE_TYPES = ["weapon", "helmet", "chest", "legs", "boots", "gloves", "necklace", "ring", "cape"]

WEAPON_TYPES = _deep_get(_cfg, "weapons", default=_DEFAULTS["weapons"])
ARMOR_TYPES  = _deep_get(_cfg, "armor",   default=_DEFAULTS["armor"])

# --- Equipment slot types ---
HELMET_TYPES = _deep_get(_cfg, "helmet_types", default=_DEFAULTS["helmet_types"])
CHEST_TYPES  = _deep_get(_cfg, "chest_types",  default=_DEFAULTS["chest_types"])
LEGS_TYPES   = _deep_get(_cfg, "legs_types",   default=_DEFAULTS["legs_types"])
BOOTS_TYPES  = _deep_get(_cfg, "boots_types",  default=_DEFAULTS["boots_types"])
GLOVES_TYPES = _deep_get(_cfg, "gloves_types", default=_DEFAULTS["gloves_types"])
NECKLACE_TYPES = _deep_get(_cfg, "necklace_types", default=_DEFAULTS["necklace_types"])
CAPE_TYPES   = _deep_get(_cfg, "cape_types",   default=_DEFAULTS["cape_types"])

# --- Classes ---
CLASSES = _deep_get(_cfg, "player_classes", default=_DEFAULTS["player_classes"])

# --- Room types ---
ROOM_NORMAL   = "normal"
ROOM_TREASURE = "treasure"
ROOM_BOSS     = "boss"
ROOM_TRAP     = "trap"
ROOM_SHOP     = "shop"
ROOM_EVENT    = "event"
ROOM_CITY     = "city"

_r_w2 = _deep_get(_cfg, "rooms", "weights", default=_DEFAULTS["rooms"]["weights"])
ROOM_WEIGHTS = {
    ROOM_NORMAL:   _r_w2.get("normal", 55),
    ROOM_TREASURE: _r_w2.get("treasure", 18),
    ROOM_BOSS:     _r_w2.get("boss", 12),
    ROOM_TRAP:     _r_w2.get("trap", 10),
    ROOM_EVENT:    _r_w2.get("event", 5),
}

# --- NPC Enemies ---
NPC_ENEMY_CHANCE       = _deep_get(_cfg, "npc_enemies", "chance",       default=_DEFAULTS["npc_enemies"]["chance"])
NPC_ENEMY_MIN_FLOOR    = _deep_get(_cfg, "npc_enemies", "min_floor",    default=_DEFAULTS["npc_enemies"]["min_floor"])
NPC_ENEMY_PER_ROOM_MAX = _deep_get(_cfg, "npc_enemies", "per_room_max", default=_DEFAULTS["npc_enemies"]["per_room_max"])
NPC_ENEMY_CLASSES      = _deep_get(_cfg, "npc_enemies", "classes",      default=_DEFAULTS["npc_enemies"]["classes"])
NPC_ENEMY_CLASS_WEIGHTS = _deep_get(_cfg, "npc_enemies", "class_weights", default=_DEFAULTS["npc_enemies"]["class_weights"])

# --- City ---
CITY_NPC_BASE_PRICE = _deep_get(_cfg, "city", "base_price", default=_DEFAULTS["city"]["base_price"])

# --- Party ---
MAX_PARTY_SIZE = _deep_get(_cfg, "party", "max_size", default=_DEFAULTS["party"]["max_size"])

# --- Monster scaling ---
MONSTER_HP_SCALE         = _deep_get(_cfg, "monster_scaling", "hp_scale",        default=_DEFAULTS["monster_scaling"]["hp_scale"])
MONSTER_ATK_SCALE        = _deep_get(_cfg, "monster_scaling", "atk_scale",       default=_DEFAULTS["monster_scaling"]["atk_scale"])
MONSTER_DEF_SCALE        = _deep_get(_cfg, "monster_scaling", "def_scale",       default=_DEFAULTS["monster_scaling"]["def_scale"])
MONSTERS_PER_FLOOR_BASE  = _deep_get(_cfg, "monster_scaling", "base_per_floor", default=_DEFAULTS["monster_scaling"]["base_per_floor"])
MONSTERS_PER_FLOOR_SCALE = _deep_get(_cfg, "monster_scaling", "scale_per_floor", default=_DEFAULTS["monster_scaling"]["scale_per_floor"])

# --- NPC AI ---
NPC_AI_FLEE_HP          = _deep_get(_cfg, "npc_ai", "flee_hp",          default=_DEFAULTS["npc_ai"]["flee_hp"])
NPC_AI_KITE_RANGE       = _deep_get(_cfg, "npc_ai", "kite_range",       default=_DEFAULTS["npc_ai"]["kite_range"])
NPC_AI_HEAL_HP          = _deep_get(_cfg, "npc_ai", "heal_hp",          default=_DEFAULTS["npc_ai"]["heal_hp"])
NPC_AI_FLANK_CHANCE     = _deep_get(_cfg, "npc_ai", "flank_chance",     default=_DEFAULTS["npc_ai"]["flank_chance"])
NPC_AI_BFS_DEPTH        = _deep_get(_cfg, "npc_ai", "bfs_depth",        default=_DEFAULTS["npc_ai"]["bfs_depth"])
NPC_AI_UPDATE_INTERVAL  = _deep_get(_cfg, "npc_ai", "update_interval",  default=_DEFAULTS["npc_ai"]["update_interval"])

# --- Chest loot ---
CHEST_MIN_ITEMS = _deep_get(_cfg, "chest_loot", "min_items", default=_DEFAULTS["chest_loot"]["min_items"])
CHEST_MAX_ITEMS = _deep_get(_cfg, "chest_loot", "max_items", default=_DEFAULTS["chest_loot"]["max_items"])
CHEST_GOLD_MIN  = _deep_get(_cfg, "chest_loot", "gold_min",  default=_DEFAULTS["chest_loot"]["gold_min"])
CHEST_GOLD_MAX  = _deep_get(_cfg, "chest_loot", "gold_max",  default=_DEFAULTS["chest_loot"]["gold_max"])

# --- Monster gold ---
MONSTER_GOLD_MIN       = _deep_get(_cfg, "combat", "monster_gold_min",       default=_DEFAULTS["combat"]["monster_gold_min"])
MONSTER_GOLD_MAX_BASE  = _deep_get(_cfg, "combat", "monster_gold_max_base",  default=_DEFAULTS["combat"]["monster_gold_max_base"])
MONSTER_GOLD_FLOOR_MULT= _deep_get(_cfg, "combat", "monster_gold_floor_mult", default=_DEFAULTS["combat"]["monster_gold_floor_mult"])
BOSS_GOLD_BASE         = _deep_get(_cfg, "combat", "boss_gold_base",         default=_DEFAULTS["combat"]["boss_gold_base"])
BOSS_GOLD_FLOOR_MULT   = _deep_get(_cfg, "combat", "boss_gold_floor_mult",   default=_DEFAULTS["combat"]["boss_gold_floor_mult"])

# --- Colors (RGB tuples) ---
_c = _deep_get(_cfg, "colors", default=_DEFAULTS["colors"])
COLOR_HUD_BG    = tuple(_c.get("hud_bg", [18,18,28]))
COLOR_HUD_FG    = tuple(_c.get("hud_fg", [180,180,200]))
COLOR_PLAYER    = tuple(_c.get("player", [80,220,255]))
COLOR_WALL      = tuple(_c.get("wall", [90,80,100]))
COLOR_FLOOR     = tuple(_c.get("floor", [50,48,55]))
COLOR_FOG_WALL  = tuple(_c.get("fog_wall", [42,40,50]))
COLOR_FOG_FLOOR = tuple(_c.get("fog_floor", [28,26,32]))
COLOR_STAIR     = tuple(_c.get("stair", [230,200,80]))
COLOR_CHEST     = tuple(_c.get("chest", [200,170,60]))
COLOR_MONSTER   = tuple(_c.get("monster", [220,70,70]))
COLOR_BOSS      = tuple(_c.get("boss", [200,40,200]))
COLOR_TRAP      = tuple(_c.get("trap", [200,120,40]))
COLOR_SHOP      = tuple(_c.get("shop", [80,200,120]))
