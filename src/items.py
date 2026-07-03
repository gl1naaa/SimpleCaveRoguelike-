import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

# ============================================================
#  Item system
# ============================================================

@dataclass
class Item:
    name: str
    item_type: str       # "weapon", "armor", "accessory", "consumable", "skill_book"
    rarity: str          # common, uncommon, rare, epic, mythic, legendary, unique
    stats: Dict[str, int] = field(default_factory=dict)  # {"atk": 5, "def": 2, etc}
    description: str = ""
    weapon_type: str = ""   # "sword", "bow", "staff", "orb" if weapon
    armor_type: str = ""    # "light", "medium", "heavy" if armor
    skill_id: str = ""      # skill learned if skill_book
    consumable_effect: str = ""  # "heal", "mana", "buff_atk", "buff_def"
    consumable_value: int = 0
    stackable: bool = True
    quantity: int = 1
    is_unique: bool = False
    unique_effect: str = ""

    def stat_text(self) -> str:
        parts = []
        for k, v in self.stats.items():
            sign = "+" if v > 0 else ""
            label = {"atk": "ATK", "def": "DEF", "hp": "HP", "mp": "MP",
                     "speed": "SPD", "crit": "CRT", "str": "STR",
                     "agi": "AGI", "int": "INT"}.get(k, k.upper())
            parts.append(f"{label}{sign}{v}")
        return " ".join(parts) if parts else "---"

    def short_text(self) -> str:
        return f"{self.name} [{self.rarity}] {self.stat_text()}"

# ============================================================
#  Name generation
# ============================================================

PREFIXES_WEAPON = {
    "common":    ["Rusty", "Old", "Worn", "Basic", "Simple"],
    "uncommon":  ["Sharp", "Sturdy", "Fine", "Tempered"],
    "rare":      ["Enchanted", "Blazing", "Frozen", "Venomous", "Shadow"],
    "epic":      ["Cursed", "Radiant", "Storm", "Abyssal", "Divine"],
    "mythic":    ["Infernal", "Celestial", "Eternal", "Blood"],
    "legendary": ["World-Ender", "Dragon's", "God-Killer", "Star-Forge"],
    "unique":    [],
}

WEAPON_NAMES = {
    "sword": ["Dagger", "Shortsword", "Longsword", "Claymore", "Greatsword", "Blade"],
    "bow":   ["Shortbow", "Longbow", "Composite Bow", "Crossbow", "Recurve"],
    "staff": ["Wand", "Staff", "Rod", "Scepter", "Crook"],
    "orb":   ["Orb", "Crystal", "Sphere", "Relic", "Focus"],
}

PREFIXES_ARMOR = {
    "common":    ["Torn", "Patched", "Basic", "Worn"],
    "uncommon":  ["Reinforced", "Sturdy", "Lined"],
    "rare":      ["Enchanted", "Runed", "Blessed", "Mithril"],
    "epic":      ["Demonic", "Angelic", "Dragon", "Void"],
    "mythic":    ["Celestial", "Infernal", "Eternal"],
    "legendary": ["Titan", "World-Breaker", "Primordial"],
    "unique":    [],
}

ARMOR_NAMES = {
    "light": ["Cloth Armor", "Leather Armor", "Hide Armor", "Brigandine"],
    "medium": ["Chainmail", "Lamellar", "Scale Mail", "Breastplate"],
    "heavy": ["Plate Armor", "Full Plate", "Tower Shield", "Bulwark"],
}

RING_NAMES = [
    "Ring of Power", "Ring of Protection", "Ring of Vitality",
    "Ring of Fortune", "Ring of Shadows", "Ring of Flames",
    "Ring of Frost", "Ring of Lightning", "Ring of Swiftness",
]

CONSUMABLE_NAMES = {
    "heal":    ["Health Potion", "Healing Salve", "Mend Potion"],
    "mana":    ["Mana Potion", "Arcane Elixir", "Mana Crystal"],
    "buff_atk": ["Berserk Potion", "Battle Elixir", "Strength Tonic"],
    "buff_def": ["Iron Skin Potion", "Stone Elixir", "Shield Brew"],
}

UNIQUE_ITEMS = [
    {"name": "Tapper of Speed", "item_type": "accessory", "stats": {"speed": -80, "hp": -50},
     "description": "+200% speed, -50% HP. Gotta go fast!", "unique_effect": "fast_feet"},
    {"name": "Nosek of Power", "item_type": "weapon", "weapon_type": "sword", "stats": {"atk": 50},
     "description": "+50 ATK but every 5th attack misses. Literally.", "unique_effect": "miss_chance"},
    {"name": "Banana Peel", "item_type": "consumable", "consumable_effect": "trap",
     "description": "Leave a banana peel behind you. Enemies slip on it.", "unique_effect": "banana_trap"},
    {"name": "Cat Swordsman", "item_type": "accessory", "stats": {"atk": 5},
     "description": "A cat sits on your head. Sometimes attacks enemies.", "unique_effect": "cat_attack"},
    {"name": "Random Hat", "item_type": "accessory", "stats": {},
     "description": "Changes hat every floor. Random buff each time.", "unique_effect": "random_hat"},
    {"name": "Infinite Breadstick", "item_type": "consumable", "stackable": False,
     "description": "Restores 1 HP. Never runs out. Ever.", "unique_effect": "infinite_heal",
     "consumable_effect": "heal", "consumable_value": 1},
    {"name": "D20 of Fate", "item_type": "accessory", "stats": {},
     "description": "Roll a d20 every room. Natural 20 = instant kill enemy nearby.", "unique_effect": "d20"},
    {"name": "Rubber Duck", "item_type": "accessory", "stats": {"def": 10},
     "description": "+10 DEF. Enemies are too confused to attack effectively.", "unique_effect": "duck_def"},
    {"name": "Existential Crisis", "item_type": "accessory", "stats": {"atk": 20, "def": -10, "hp": -30},
     "description": "+20 ATK, -10 DEF, -30 HP. You question everything.", "unique_effect": "crisis"},
    {"name": "Plot Armor", "item_type": "armor", "armor_type": "light", "stats": {"def": 1},
     "description": "+1 DEF. But you literally cannot die to anything below floor 5.", "unique_effect": "plot_armor"},
    {"name": "WiFi Router", "item_type": "accessory", "stats": {},
     "description": "Enemies in range slow down as if buffering.", "unique_effect": "wifi_slow"},
    {"name": "Procrastination Scroll", "item_type": "consumable",
     "description": "Delays all damage by 3 turns. You'll deal with it later.", "unique_effect": "delay_damage"},
]

# ============================================================
#  Item generation
# ============================================================

def _pick_rarity(floor: int = 1) -> str:
    from config import RARITY_WEIGHTS
    # Better odds on deeper floors
    adjusted = dict(RARITY_WEIGHTS)
    bonus = floor * 0.3
    adjusted["rare"] += bonus
    adjusted["epic"] += bonus * 0.5
    adjusted["mythic"] += bonus * 0.2
    total = sum(adjusted.values())
    r = random.random() * total
    acc = 0
    for rarity, weight in adjusted.items():
        acc += weight
        if r <= acc:
            return rarity
    return "common"

def _pick_prefix(rarity: str) -> str:
    from config import RARITY_ORDER
    prefixes = PREFIXES_WEAPON.get(rarity, PREFIXES_WEAPON["common"])
    return random.choice(prefixes) if prefixes else ""

def generate_weapon(floor: int = 1) -> Item:
    rarity = _pick_rarity(floor)
    wtype = random.choice(list(WEAPON_NAMES.keys()))
    from config import WEAPON_TYPES, RARITY_STAT_MULT
    base = WEAPON_TYPES[wtype]
    mult = RARITY_STAT_MULT[rarity]
    atk = int((base["atk_base"] + random.randint(0, base["atk_range"])) * mult)
    prefix = _pick_prefix(rarity)
    name_base = random.choice(WEAPON_NAMES[wtype])
    name = f"{prefix} {name_base}".strip()
    primary_stat = {"sword": "str", "bow": "agi", "staff": "int", "orb": "int"}.get(wtype, "str")
    stat_val = int(random.randint(1, 3) * mult)
    stats = {"atk": atk, primary_stat: stat_val}
    desc = f"A {rarity} {wtype}. Deals {atk} damage. +{stat_val} {primary_stat.upper()}."
    return Item(
        name=name, item_type="weapon", rarity=rarity,
        stats=stats, description=desc,
        weapon_type=wtype,
    )

def generate_armor(floor: int = 1) -> Item:
    rarity = _pick_rarity(floor)
    atype = random.choice(list(ARMOR_NAMES.keys()))
    from config import ARMOR_TYPES, RARITY_STAT_MULT
    base = ARMOR_TYPES[atype]
    mult = RARITY_STAT_MULT[rarity]
    defense = int((base["def_base"] + random.randint(0, base["def_range"])) * mult)
    prefix = _pick_prefix(rarity)
    name_base = random.choice(ARMOR_NAMES[atype])
    name = f"{prefix} {name_base}".strip()
    bonus_stat = random.choice(["str", "agi", "hp"])
    stat_val = int(random.randint(1, 3) * mult)
    stats = {"def": defense, bonus_stat: stat_val}
    desc = f"{rarity.title()} {atype} armor. +{defense} DEF +{stat_val} {bonus_stat.upper()}."
    return Item(
        name=name, item_type="armor", rarity=rarity,
        stats=stats, description=desc,
        armor_type=atype,
    )

def generate_ring(floor: int = 1) -> Item:
    rarity = _pick_rarity(floor)
    from config import RARITY_STAT_MULT
    mult = RARITY_STAT_MULT[rarity]
    name = random.choice(RING_NAMES)
    stat = random.choice(["atk", "def", "hp", "mp", "str", "agi", "int", "crit"])
    val = int(random.randint(2, 5) * mult)
    return Item(
        name=name, item_type="accessory", rarity=rarity,
        stats={stat: val},
        description=f"+{val} {stat.upper()}. A magical ring.",
    )

def generate_consumable(floor: int = 1) -> Item:
    etype = random.choice(["heal", "mana", "buff_atk", "buff_def"])
    name = random.choice(CONSUMABLE_NAMES[etype])
    val = 15 + floor * 3
    if etype == "heal":
        return Item(name=name, item_type="consumable", rarity="common",
                    stats={}, description=f"Restores {val} HP.",
                    consumable_effect="heal", consumable_value=val)
    elif etype == "mana":
        return Item(name=name, item_type="consumable", rarity="common",
                    stats={}, description=f"Restores {val} MP.",
                    consumable_effect="mana", consumable_value=val)
    else:
        return Item(name=name, item_type="consumable", rarity="uncommon",
                    stats={}, description=f"Temporarily boosts {etype.replace('buff_','')}.",
                    consumable_effect=etype, consumable_value=val)

def generate_random_item(floor: int = 1) -> Item:
    """Generate a random item of any type."""
    roll = random.random()
    if roll < 0.005:
        return generate_unique()
    r = random.random()
    if r < 0.30:
        return generate_weapon(floor)
    elif r < 0.55:
        return generate_armor(floor)
    elif r < 0.70:
        return generate_ring(floor)
    else:
        return generate_consumable(floor)

def generate_unique() -> Item:
    """Generate a unique (meme) item."""
    template = random.choice(UNIQUE_ITEMS)
    return Item(
        name=template["name"],
        item_type=template.get("item_type", "accessory"),
        rarity="unique",
        stats=dict(template.get("stats", {})),
        description=template["description"],
        weapon_type=template.get("weapon_type", ""),
        armor_type=template.get("armor_type", ""),
        consumable_effect=template.get("consumable_effect", ""),
        consumable_value=template.get("consumable_value", 0),
        is_unique=True,
        unique_effect=template.get("unique_effect", ""),
    )

def generate_chest_loot(floor: int = 1, count: int = 2) -> List[Item]:
    """Generate loot for a chest."""
    items = []
    for _ in range(count):
        items.append(generate_random_item(floor))
    # Chance for gold
    from config import CHEST_GOLD_MIN, CHEST_GOLD_MAX
    gold = random.randint(CHEST_GOLD_MIN, CHEST_GOLD_MAX) * (1 + floor // 3)
    return items, gold
