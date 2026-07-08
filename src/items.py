import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

# ============================================================
#  Item system
# ============================================================

@dataclass
class Item:
    name: str
    item_type: str       # "weapon", "helmet", "chest", "legs", "boots", "gloves", "necklace", "ring", "cape", "consumable", "skill_book"
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
            if v == 0:
                continue
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
    "sword":  ["Dagger", "Shortsword", "Longsword", "Claymore", "Greatsword", "Blade"],
    "bow":    ["Shortbow", "Longbow", "Composite Bow", "Crossbow", "Recurve"],
    "staff":  ["Wand", "Staff", "Rod", "Scepter", "Crook"],
    "orb":    ["Orb", "Crystal", "Sphere", "Relic", "Focus"],
    "mace":   ["Mace", "War Hammer", "Flail", "Morning Star", "Cudgel"],
    "dagger": ["Dagger", "Ritual Knife", "Shiv", "Stiletto", "Dirk"],
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

HELMET_NAMES = {
    "leather_helm": ["Leather Cap", "Hide Hood", "Scout Hat"],
    "chain_helm":   ["Chain Coif", "Mail Helm", "Knight Crown"],
    "plate_helm":   ["Plate Helm", "Great Helm", "Iron Visage"],
}

CHEST_NAMES = {
    "leather_chest": ["Leather Tunic", "Hide Vest", "Brigandine"],
    "chain_chest":   ["Chainmail", "Mail Hauberk", "Lamellar"],
    "plate_chest":   ["Plate Cuirass", "Full Plate", "Bulwark"],
}

LEGS_NAMES = {
    "leather_legs": ["Leather Breeches", "Hide Leggings", "Scout Pants"],
    "chain_legs":   ["Chain Chausses", "Mail Leggings", "Knight Greaves"],
    "plate_legs":   ["Plate Greaves", "Iron Legguards", "War Tassets"],
}

BOOTS_NAMES = {
    "leather_boots": ["Leather Boots", "Hide Treads", "Scout Sandals"],
    "chain_boots":   ["Chain Boots", "Mail Sabatons", "Knight Stompers"],
    "plate_boots":   ["Plate Boots", "Iron Treads", "War Boots"],
}

GLOVES_NAMES = {
    "leather_gloves": ["Leather Gloves", "Hide Wraps", "Thief Grips"],
    "chain_gloves":   ["Chain Gauntlets", "Mail Grips", "Knight Fists"],
    "plate_gloves":   ["Plate Gauntlets", "Iron Graspers", "War Claws"],
}

NECKLACE_NAMES = {
    "crystal": ["Crystal Pendant", "Prismatic Amulet", "Shard Necklace"],
    "ruby":    ["Ruby Pendant", "Bloodstone Amulet", "Crimson Chain"],
    "sapphire":["Sapphire Pendant", "Azure Amulet", "Ocean Necklace"],
    "emerald": ["Emerald Pendant", "Verdant Amulet", "Jade Chain"],
}

CAPE_NAMES = {
    "cloth":  ["Woven Cloak", "Traveler's Mantle", "Linen Cape"],
    "fur":    ["Fur-lined Cloak", "Bear Pelt", "Wolf Cape"],
    "shadow": ["Shadow Cloak", "Night Mantle", "Phantom Cape"],
    "arcane": ["Arcane Mantle", "Mystic Cloak", "Runic Cape"],
}

CONSUMABLE_NAMES = {
    "heal":    ["Health Potion", "Healing Salve", "Mend Potion"],
    "mana":    ["Mana Potion", "Arcane Elixir", "Mana Crystal"],
    "buff_atk": ["Berserk Potion", "Battle Elixir", "Strength Tonic"],
    "buff_def": ["Iron Skin Potion", "Stone Elixir", "Shield Brew"],
}

UNIQUE_ITEMS = [
    {"name": "Tapper of Speed", "item_type": "boots", "stats": {"speed": 20, "agi": 5},
     "description": "+20 SPD, +5 AGI. Gotta go fast!", "unique_effect": "fast_feet"},
    {"name": "Nosek of Power", "item_type": "weapon", "weapon_type": "sword", "stats": {"atk": 50},
     "description": "+50 ATK but every 5th attack misses. Literally.", "unique_effect": "miss_chance"},
    {"name": "Banana Peel", "item_type": "consumable", "consumable_effect": "trap",
     "description": "Leave a banana peel behind you. Enemies slip on it.", "unique_effect": "banana_trap"},
    {"name": "Cat Swordsman", "item_type": "ring", "stats": {"atk": 5},
     "description": "A cat sits on your head. Sometimes attacks enemies.", "unique_effect": "cat_attack"},
    {"name": "Random Hat", "item_type": "helmet", "stats": {"def": 2, "hp": 10},
     "description": "Changes hat every floor. Random buff each time.", "unique_effect": "random_hat"},
    {"name": "Infinite Breadstick", "item_type": "consumable", "stackable": False,
     "description": "Restores 1 HP. Never runs out. Ever.", "unique_effect": "infinite_heal",
     "consumable_effect": "heal", "consumable_value": 1},
    {"name": "D20 of Fate", "item_type": "ring", "stats": {},
     "description": "Roll a d20 every room. Natural 20 = instant kill enemy nearby.", "unique_effect": "d20"},
    {"name": "Rubber Duck", "item_type": "gloves", "stats": {"def": 10},
     "description": "+10 DEF. Enemies are too confused to attack effectively.", "unique_effect": "duck_def"},
    {"name": "Existential Crisis", "item_type": "cape", "stats": {"atk": 20, "def": -10, "hp": -30},
     "description": "+20 ATK, -10 DEF, -30 HP. You question everything.", "unique_effect": "crisis"},
    {"name": "Plot Armor", "item_type": "chest", "stats": {"def": 15, "hp": 50},
     "description": "+15 DEF, +50 HP. You literally cannot die to anything below floor 5.", "unique_effect": "plot_armor"},
    {"name": "WiFi Router", "item_type": "necklace", "stats": {"mp": 20, "int": 5},
     "description": "+20 MP, +5 INT. Enemies slow down as if buffering.", "unique_effect": "wifi_slow"},
    {"name": "Procrastination Scroll", "item_type": "consumable",
     "description": "Delays all damage by 3 turns. You'll deal with it later.", "unique_effect": "delay_damage"},
    {"name": "Titan Helm", "item_type": "helmet", "stats": {"def": 10, "hp": 30, "str": 5},
     "description": "+10 DEF, +30 HP, +5 STR. Worn by the titans of old.", "unique_effect": "titan_helm"},
    {"name": "Shadow Cape", "item_type": "cape", "stats": {"speed": 15, "crit": 10, "agi": 5},
     "description": "+15 SPD, +10 CRT, +5 AGI. You become one with the shadows.", "unique_effect": "shadow_cape"},
]

# ============================================================
#  Item generation
# ============================================================

def _pick_rarity(floor: int = 1) -> str:
    from config import RARITY_WEIGHTS
    # Better odds on deeper floors
    adjusted = dict(RARITY_WEIGHTS)
    bonus = floor * 0.3
    adjusted["rare"] = adjusted["rare"] + bonus
    adjusted["epic"] = adjusted["epic"] + bonus * 0.5
    adjusted["mythic"] = adjusted["mythic"] + bonus * 0.2
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

CLASS_WEAPON_MAP = {
    "swordsman": "sword",
    "archer": "bow",
    "mage": "staff",
    "summoner": "orb",
    "healer": "mace",
    "rogue": "dagger",
}


def generate_weapon(floor: int = 1, class_name: str = "") -> Item:
    rarity = _pick_rarity(floor)
    # 65% chance to drop weapon matching player's class
    if class_name and class_name in CLASS_WEAPON_MAP and random.random() < 0.65:
        wtype = CLASS_WEAPON_MAP[class_name]
    else:
        wtype = random.choice(list(WEAPON_NAMES.keys()))
    from config import WEAPON_TYPES, RARITY_STAT_MULT
    base = WEAPON_TYPES[wtype]
    mult = RARITY_STAT_MULT[rarity]
    atk = int((base["atk_base"] + random.randint(0, base["atk_range"])) * mult)
    prefix = _pick_prefix(rarity)
    name_base = random.choice(WEAPON_NAMES[wtype])
    name = f"{prefix} {name_base}".strip()
    primary_stat = {"sword": "str", "bow": "agi", "staff": "int", "orb": "int", "mace": "int", "dagger": "agi"}.get(wtype, "str")
    stat_val = int(random.randint(1, 3) * mult)
    stats = {"atk": atk, primary_stat: stat_val}
    desc = f"A {rarity} {wtype}. Deals {atk} damage. +{stat_val} {primary_stat.upper()}."
    return Item(
        name=name, item_type="weapon", rarity=rarity,
        stats=stats, description=desc,
        weapon_type=wtype,
    )

def generate_armor(floor: int = 1) -> Item:
    """Legacy function - redirects to generate_chest."""
    return generate_chest(floor)

def generate_ring(floor: int = 1) -> Item:
    rarity = _pick_rarity(floor)
    from config import RARITY_STAT_MULT
    mult = RARITY_STAT_MULT[rarity]
    name = random.choice(RING_NAMES)
    stat = random.choice(["atk", "def", "hp", "mp", "str", "agi", "int", "crit"])
    val = int(random.randint(2, 5) * mult)
    return Item(
        name=name, item_type="ring", rarity=rarity,
        stats={stat: val},
        description=f"+{val} {stat.upper()}. A magical ring.",
    )

def generate_helmet(floor: int = 1) -> Item:
    rarity = _pick_rarity(floor)
    from config import HELMET_TYPES, RARITY_STAT_MULT
    htype = random.choice(list(HELMET_TYPES.keys()))
    base = HELMET_TYPES[htype]
    mult = RARITY_STAT_MULT[rarity]
    defense = int((base["def_base"] + random.randint(0, base["def_range"])) * mult)
    prefix = _pick_prefix(rarity)
    name_base = random.choice(HELMET_NAMES[htype])
    name = f"{prefix} {name_base}".strip()
    bonus_stat = random.choice(["hp", "str", "int", "agi"])
    stat_val = int(random.randint(1, 3) * mult)
    stats = {"def": defense, bonus_stat: stat_val, "hp": int(base.get("hp", 0) * mult)}
    return Item(name=name, item_type="helmet", rarity=rarity,
                stats=stats, description=f"+{defense} DEF +{stat_val} {bonus_stat.upper()}.")

def generate_chest(floor: int = 1) -> Item:
    rarity = _pick_rarity(floor)
    from config import CHEST_TYPES, RARITY_STAT_MULT
    ctype = random.choice(list(CHEST_TYPES.keys()))
    base = CHEST_TYPES[ctype]
    mult = RARITY_STAT_MULT[rarity]
    defense = int((base["def_base"] + random.randint(0, base["def_range"])) * mult)
    prefix = _pick_prefix(rarity)
    name_base = random.choice(CHEST_NAMES[ctype])
    name = f"{prefix} {name_base}".strip()
    bonus_stat = random.choice(["str", "hp", "agi"])
    stat_val = int(random.randint(1, 3) * mult)
    stats = {"def": defense, bonus_stat: stat_val, "hp": int(base.get("hp", 0) * mult)}
    return Item(name=name, item_type="chest", rarity=rarity,
                stats=stats, description=f"+{defense} DEF +{stat_val} {bonus_stat.upper()}.")

def generate_legs(floor: int = 1) -> Item:
    rarity = _pick_rarity(floor)
    from config import LEGS_TYPES, RARITY_STAT_MULT
    ltype = random.choice(list(LEGS_TYPES.keys()))
    base = LEGS_TYPES[ltype]
    mult = RARITY_STAT_MULT[rarity]
    defense = int((base["def_base"] + random.randint(0, base["def_range"])) * mult)
    prefix = _pick_prefix(rarity)
    name_base = random.choice(LEGS_NAMES[ltype])
    name = f"{prefix} {name_base}".strip()
    stats = {"def": defense, "agi": int(base.get("agi", 0) * mult) + int(random.randint(0, 2) * mult)}
    return Item(name=name, item_type="legs", rarity=rarity,
                stats=stats, description=f"+{defense} DEF +AGI.")

def generate_boots(floor: int = 1) -> Item:
    rarity = _pick_rarity(floor)
    from config import BOOTS_TYPES, RARITY_STAT_MULT
    btype = random.choice(list(BOOTS_TYPES.keys()))
    base = BOOTS_TYPES[btype]
    mult = RARITY_STAT_MULT[rarity]
    defense = int((base["def_base"] + random.randint(0, base["def_range"])) * mult)
    prefix = _pick_prefix(rarity)
    name_base = random.choice(BOOTS_NAMES[btype])
    name = f"{prefix} {name_base}".strip()
    stats = {"def": defense, "speed": int(base.get("speed", 0) * mult), "agi": int(random.randint(0, 2) * mult)}
    return Item(name=name, item_type="boots", rarity=rarity,
                stats=stats, description=f"+{defense} DEF +SPD.")

def generate_gloves(floor: int = 1) -> Item:
    rarity = _pick_rarity(floor)
    from config import GLOVES_TYPES, RARITY_STAT_MULT
    gtype = random.choice(list(GLOVES_TYPES.keys()))
    base = GLOVES_TYPES[gtype]
    mult = RARITY_STAT_MULT[rarity]
    defense = int((base["def_base"] + random.randint(0, base["def_range"])) * mult)
    prefix = _pick_prefix(rarity)
    name_base = random.choice(GLOVES_NAMES[gtype])
    name = f"{prefix} {name_base}".strip()
    stats = {"def": defense, "atk": int(base.get("atk", 0) * mult), "crit": int(random.randint(0, 2) * mult)}
    return Item(name=name, item_type="gloves", rarity=rarity,
                stats=stats, description=f"+{defense} DEF +ATK +CRT.")

def generate_necklace(floor: int = 1) -> Item:
    rarity = _pick_rarity(floor)
    from config import NECKLACE_TYPES, RARITY_STAT_MULT
    ntype = random.choice(list(NECKLACE_TYPES.keys()))
    base = NECKLACE_TYPES[ntype]
    mult = RARITY_STAT_MULT[rarity]
    prefix = _pick_prefix(rarity)
    name_base = random.choice(NECKLACE_NAMES[ntype])
    name = f"{prefix} {name_base}".strip()
    stats = {}
    for k, v in base.items():
        stats[k] = int(v * mult) + int(random.randint(0, 2) * mult)
    return Item(name=name, item_type="necklace", rarity=rarity,
                stats=stats, description=f"A mystical necklace.")

def generate_cape(floor: int = 1) -> Item:
    rarity = _pick_rarity(floor)
    from config import CAPE_TYPES, RARITY_STAT_MULT
    ctype = random.choice(list(CAPE_TYPES.keys()))
    base = CAPE_TYPES[ctype]
    mult = RARITY_STAT_MULT[rarity]
    prefix = _pick_prefix(rarity)
    name_base = random.choice(CAPE_NAMES[ctype])
    name = f"{prefix} {name_base}".strip()
    stats = {}
    for k, v in base.items():
        stats[k] = int(v * mult) + int(random.randint(0, 2) * mult)
    return Item(name=name, item_type="cape", rarity=rarity,
                stats=stats, description=f"A mystical cape.")

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

def generate_random_item(floor: int = 1, class_name: str = "") -> Item:
    """Generate a random item of any type."""
    roll = random.random()
    if roll < 0.005:
        return generate_unique()
    r = random.random()
    if r < 0.20:
        return generate_weapon(floor, class_name)
    elif r < 0.30:
        return generate_chest(floor)
    elif r < 0.37:
        return generate_helmet(floor)
    elif r < 0.44:
        return generate_legs(floor)
    elif r < 0.51:
        return generate_boots(floor)
    elif r < 0.58:
        return generate_gloves(floor)
    elif r < 0.65:
        return generate_necklace(floor)
    elif r < 0.75:
        return generate_ring(floor)
    elif r < 0.82:
        return generate_cape(floor)
    else:
        return generate_consumable(floor)

def generate_unique() -> Item:
    """Generate a unique (meme) item."""
    template = random.choice(UNIQUE_ITEMS)
    return Item(
        name=template["name"],
        item_type=template.get("item_type", "ring"),
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

def generate_chest_loot(floor: int = 1, count: int = 2, class_name: str = "") -> List[Item]:
    """Generate loot for a chest."""
    items = []
    for _ in range(count):
        items.append(generate_random_item(floor, class_name))
    # Chance for gold
    from config import CHEST_GOLD_MIN, CHEST_GOLD_MAX
    gold = random.randint(CHEST_GOLD_MIN, CHEST_GOLD_MAX) * (1 + floor // 3)
    return items, gold
