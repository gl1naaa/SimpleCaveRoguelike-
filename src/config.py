# ============================================================
#  Stone Dungeon v2 — Configuration
# ============================================================

# --- Display ---
SCREEN_WIDTH = 120
SCREEN_HEIGHT = 40
VIEWPORT_W = 80
VIEWPORT_H = 22
FPS = 30

# --- Map ---
MAP_WIDTH = 80
MAP_HEIGHT = 50
ROOM_MIN = 5
ROOM_MAX = 12
CONNECT_CHANCE = 0.2

# --- Player defaults ---
PLAYER_CHAR = "@"
PLAYER_MAX_HP = 100
PLAYER_MAX_MP = 50
PLAYER_BASE_ATK = 8
PLAYER_BASE_DEF = 3
PLAYER_BASE_SPEED = 150  # ms between moves

# --- Game symbols ---
STAIRS_DOWN = ">"
CHEST_CHAR = "="
TRAP_CHAR = "^"
SHOP_CHAR = "$"
altar = "*"

# --- Movement cooldown (ms) ---
MOVE_COOLDOWN = 150
SKILL_COOLDOWN = 300
MONSTER_TICK = 300  # ms between monster moves

# --- Inventory ---
INVENTORY_SIZE = 20
INV_COLS = 4
INV_ROWS = 5

# --- Skill slots ---
SKILL_KEYS = ["z", "x", "c", "v", "b"]
NUM_SKILL_SLOTS = 5

# --- Rarity ---
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "mythic", "legendary", "unique"]
RARITY_COLORS = {
    "common":    (170, 170, 170),
    "uncommon":  (80, 200, 80),
    "rare":      (80, 130, 255),
    "epic":      (180, 80, 255),
    "mythic":    (255, 60, 60),
    "legendary": (255, 255, 60),
    "unique":    "rainbow",
}
RARITY_WEIGHTS = {
    "common":    40,
    "uncommon":  25,
    "rare":      18,
    "epic":      10,
    "mythic":    5,
    "legendary": 1.5,
    "unique":    0.5,
}
RARITY_STAT_MULT = {
    "common":    1.0,
    "uncommon":  1.3,
    "rare":      1.7,
    "epic":      2.2,
    "mythic":    3.0,
    "legendary": 4.0,
    "unique":    1.0,  # unique items have special stats
}

# --- Item types ---
ITEM_WEAPON = "weapon"
ITEM_ARMOR = "armor"
ITEM_RING = "accessory"
ITEM_CONSUMABLE = "consumable"
ITEM_SKILL_BOOK = "skill_book"

WEAPON_TYPES = {
    "sword": {"atk_base": 5, "atk_range": 4, "class_req": "swordsman"},
    "bow":   {"atk_base": 4, "atk_range": 5, "class_req": "archer"},
    "staff": {"atk_base": 3, "atk_range": 3, "class_req": "mage"},
    "orb":   {"atk_base": 2, "atk_range": 4, "class_req": "summoner"},
}

ARMOR_TYPES = {
    "light":  {"def_base": 2, "def_range": 3},
    "medium": {"def_base": 4, "def_range": 4},
    "heavy":  {"def_base": 7, "def_range": 5},
}

# --- Classes ---
CLASSES = {
    "swordsman": {"weapon": "sword", "desc": "Melee tank, high STR and HP"},
    "archer":    {"weapon": "bow",   "desc": "Ranged DPS, high AGI and crits"},
    "mage":      {"weapon": "staff", "desc": "Glass cannon, high INT and spells"},
    "summoner":  {"weapon": "orb",   "desc": "Universal, all stats scale allies"},
}

# --- Room types ---
ROOM_NORMAL = "normal"
ROOM_TREASURE = "treasure"
ROOM_BOSS = "boss"
ROOM_TRAP = "trap"
ROOM_SHOP = "shop"
ROOM_EVENT = "event"

ROOM_WEIGHTS = {
    ROOM_NORMAL:   55,
    ROOM_TREASURE: 18,
    ROOM_BOSS:     12,
    ROOM_TRAP:     10,
    ROOM_EVENT:    5,
}

# --- Monster scaling ---
MONSTER_HP_SCALE = 5
MONSTER_ATK_SCALE = 1
MONSTER_DEF_SCALE = 0.5
MONSTERS_PER_FLOOR_BASE = 3
MONSTERS_PER_FLOOR_SCALE = 2

# --- Chest loot ---
CHEST_MIN_ITEMS = 1
CHEST_MAX_ITEMS = 3
CHEST_GOLD_MIN = 10
CHEST_GOLD_MAX = 50

# --- Colors (RGB tuples) ---
COLOR_HUD_BG = (18, 18, 28)
COLOR_HUD_FG = (180, 180, 200)
COLOR_PLAYER = (80, 220, 255)
COLOR_WALL = (90, 80, 100)
COLOR_FLOOR = (50, 48, 55)
COLOR_FOG_WALL = (42, 40, 50)
COLOR_FOG_FLOOR = (28, 26, 32)
COLOR_STAIR = (230, 200, 80)
COLOR_CHEST = (200, 170, 60)
COLOR_MONSTER = (220, 70, 70)
COLOR_BOSS = (200, 40, 200)
COLOR_TRAP = (200, 120, 40)
COLOR_SHOP = (80, 200, 120)