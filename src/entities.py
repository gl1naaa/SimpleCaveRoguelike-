import time
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from inventory import Inventory, rarity_color
from skills import Skill, get_skill_for_slot, can_use_skill
from items import Item


def has_line_of_sight(x1: int, y1: int, x2: int, y2: int, walls) -> bool:
    """Bresenham line-of-sight: returns True if no wall blocks the path."""
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x2 > x1 else -1
    sy = 1 if y2 > y1 else -1
    err = dx - dy
    cx, cy = x1, y1
    while True:
        if (cx, cy) in walls and (cx, cy) != (x1, y1):
            return False
        if cx == x2 and cy == y2:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            cx += sx
        if e2 < dx:
            err += dx
            cy += sy
    return True


class Entity:
    def __init__(self, x: int, y: int, char: str, name: str, color: str):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.hp = 10
        self.max_hp = 10
        self.alive = True

    @property
    def rgb(self):
        parts = self.color.split(",")
        return int(parts[0]), int(parts[1]), int(parts[2])

    def draw(self, brightness: float = 1.0) -> str:
        r, g, b = self.rgb
        r = int(r * brightness)
        g = int(g * brightness)
        b = int(b * brightness)
        return f"\x1b[1m\x1b[38;2;{r};{g};{b}m{self.char}\x1b[0m"


# ============================================================
#  Player
# ============================================================

CLASS_PRIMARY_STAT = {
    "swordsman": "str",
    "archer": "agi",
    "mage": "int",
    "summoner": "int",
    "healer": "int",
    "rogue": "agi",
}

CLASS_BASE_STATS = {
    "swordsman": {"str": 12, "agi": 8, "int": 6},
    "archer":    {"str": 8,  "agi": 12, "int": 6},
    "mage":      {"str": 6,  "agi": 8, "int": 12},
    "summoner":  {"str": 6,  "agi": 8, "int": 12},
    "healer":    {"str": 6,  "agi": 6, "int": 14},
    "rogue":     {"str": 7,  "agi": 15, "int": 5},
}

CLASS_BASE_HP = {
    "swordsman": 18,
    "archer":    12,
    "mage":      10,
    "summoner":  14,
    "healer":    12,
    "rogue":     11,
}


class Player(Entity):
    def __init__(self, x: int, y: int, class_name: str = "swordsman"):
        super().__init__(x, y, "@", "Hero", "255,255,100")
        self.class_name = class_name
        self.level = 1
        self.xp = 0
        self.xp_to_next = 40
        self.base_atk = 10
        self.base_def = 5
        self.inventory = Inventory()
        self.floor = 1
        self.monsters_killed = 0
        self.turns = 0
        self.move_cooldown = 0.0
        self.move_delay = 0.12

        base = CLASS_BASE_STATS.get(class_name, CLASS_BASE_STATS["swordsman"])
        self.base_str = base["str"]
        self.base_agi = base["agi"]
        self.base_int = base["int"]
        self.bonus_str = 0
        self.bonus_agi = 0
        self.bonus_int = 0
        self.mp = 0
        self.cooldown = 100

        self._recalc_stats()
        self.hp = self.max_hp
        self.mp = self.max_mp

        # Assign starting skills for the class
        self.skills: List[Optional[Skill]] = [None, None, None, None, None, None]
        self.learned_skills: List[str] = []
        for slot in range(6):
            sk = get_skill_for_slot(class_name, slot)
            if sk:
                self.skills[slot] = sk
                self.learned_skills.append(sk.id)

        # Give starting weapon so skills work
        from items import Item
        weapon_map = {
            "swordsman": ("Rusty Sword", "weapon", "sword", {"atk": 3}),
            "archer":    ("Short Bow",   "weapon", "bow",   {"atk": 2}),
            "mage":      ("Wooden Wand", "weapon", "staff", {"atk": 2}),
            "summoner":  ("Old Orb",     "weapon", "orb",   {"atk": 1}),
            "healer":    ("Wooden Mace", "weapon", "mace",  {"atk": 2}),
            "rogue":     ("Rusty Dagger","weapon", "dagger",{"atk": 3}),
        }
        wname, wtype, wsub, wstats = weapon_map.get(class_name, ("Rusty Sword", "weapon", "sword", {"atk": 3}))
        starter_weapon = Item(
            name=wname, item_type=wtype, rarity="common",
            stats=wstats, description="A basic starter weapon.",
            weapon_type=wsub,
        )
        self.inventory.equipment["weapon"] = starter_weapon
        self._recalc_stats()

    def _recalc_stats(self):
        eq = self.inventory.get_stats()
        s = self.base_str + self.bonus_str + eq.get("str", 0)
        a = self.base_agi + self.bonus_agi + eq.get("agi", 0)
        i = self.base_int + self.bonus_int + eq.get("int", 0)
        self._str = s
        self._agi = a
        self._int = i
        base_hp = CLASS_BASE_HP.get(self.class_name, 30)
        self._max_hp = base_hp + s * 2 + self.level * 3 + eq.get("hp", 0)
        self._max_mp = 30 + i * 3 + self.level * 3 + eq.get("mp", 0)
        self._atk = self.base_atk + int(s * 0.5) + eq.get("atk", 0)
        self._defense = self.base_def + int(a * 0.4) + eq.get("def", 0)
        self._crit = 0.05 + a * 0.003 + eq.get("crit", 0) * 0.01
        self._dodge = 0.02 + a * 0.004
        self._hp_regen = s * 0.03
        self._mp_regen = 1.5 + i * 0.15
        self._magic_power = int(i * 0.5)
        # Apply speed from equipment
        eq_speed = eq.get("speed", 0)
        if eq_speed > 0:
            self.cooldown = max(50, self.cooldown - eq_speed)
        # Universal summoner: all stats contribute
        if self.class_name == "summoner":
            self._max_hp += i * 1
            self._atk += int(i * 0.2) + int(a * 0.1)
            self._defense += int(s * 0.15) + int(i * 0.1)
            self._magic_power = int(i * 0.4 + s * 0.15 + a * 0.1)
        # Healer: higher magic power, lower atk
        if self.class_name == "healer":
            self._magic_power = int(i * 0.7 + s * 0.1)
            self._atk = int(self._atk * 0.7)
            self._hp_regen = s * 0.02 + 0.5
            self._mp_regen = 2.0 + i * 0.2
        # Rogue: higher crit, higher dodge
        if self.class_name == "rogue":
            self._crit = 0.12 + a * 0.005
            self._dodge = 0.08 + a * 0.006
        if self.hp > self._max_hp:
            self.hp = self._max_hp
        if self.mp > self._max_mp:
            self.mp = self._max_mp

    @property
    def str(self):
        return self._str

    @property
    def agi(self):
        return self._agi

    @property
    def int_stat(self):
        return self._int

    @property
    def max_hp(self):
        return self._max_hp

    @max_hp.setter
    def max_hp(self, val):
        self._max_hp = val

    @property
    def max_mp(self):
        return self._max_mp

    @max_mp.setter
    def max_mp(self, val):
        self._max_mp = val

    @property
    def atk(self):
        return self._atk

    @property
    def defense(self):
        return self._defense

    @property
    def crit_chance(self):
        return self._crit

    @property
    def dodge_chance(self):
        return min(0.40, self._dodge)

    @property
    def hp_regen(self):
        return self._hp_regen

    @property
    def mp_regen(self):
        return self._mp_regen

    @property
    def magic_power(self):
        return self._magic_power

    @property
    def weapon_type(self) -> str:
        w = self.inventory.get_equipped("weapon")
        return w.weapon_type if w else ""

    def learn_skill(self, skill_id: str) -> bool:
        if skill_id in self.learned_skills:
            return False
        from skills import ALL_SKILLS
        skill = ALL_SKILLS.get(skill_id)
        if not skill:
            return False
        if skill.class_req != self.class_name:
            return False
        self.learned_skills.append(skill_id)
        if skill.slot < len(self.skills):
            self.skills[skill.slot] = skill
        else:
            self.skills.append(skill)
        return True

    def can_move(self, now: float) -> bool:
        return (now - self.move_cooldown) >= self.move_delay

    def move(self, dx: int, dy: int, now: float, walls, occupied: set = None):
        nx, ny = self.x + dx, self.y + dy
        if (nx, ny) in walls:
            return None
        if occupied and (nx, ny) in occupied:
            return None
        self.x, self.y = nx, ny
        self.move_cooldown = now
        self.turns += 1
        return (nx, ny)

    def use_skill(self, slot: int, now: float) -> Tuple[bool, str]:
        if slot >= len(self.skills):
            return False, "No skill!"
        skill = self.skills[slot]
        if skill is None:
            return False, "No skill learned!"
        ok, reason = can_use_skill(skill, self.weapon_type, self.mp, now)
        if not ok:
            return False, reason
        self.mp -= skill.mana_cost
        skill.use(now)
        return True, f"Used {skill.name}!"

    def gain_xp(self, amount: int) -> bool:
        self.xp += amount
        if self.xp >= self.xp_to_next:
            self.level += 1
            self.xp -= self.xp_to_next
            self.xp_to_next = int(40 * (1.4 ** self.level))
            primary = CLASS_PRIMARY_STAT.get(self.class_name, "str")
            if primary == "str":
                self.bonus_str += 3
                self.bonus_agi += 1
                self.bonus_int += 1
            elif primary == "agi":
                self.bonus_agi += 3
                self.bonus_str += 1
                self.bonus_int += 1
            else:
                self.bonus_int += 3
                self.bonus_str += 1
                self.bonus_agi += 1
            self._recalc_stats()
            self.hp = self.max_hp
            self.mp = self.max_mp
            return True
        return False

    def take_damage(self, dmg: int) -> int:
        actual = max(1, dmg)
        self.hp -= actual
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return actual

    def heal(self, amount: int):
        self.hp = min(self.hp + amount, self.max_hp)

    def restore_mp(self, amount):
        self.mp = min(self.mp + int(amount), self.max_mp)


# ============================================================
#  Monster
# ============================================================

MONSTER_TYPES = {
    "rat":       {"char": "r", "color": "150,120,80",   "hp": 16,  "atk": 6,  "xp": 5,  "speed": 1.5},
    "bat":       {"char": "b", "color": "120,80,160",   "hp": 12,  "atk": 4,  "xp": 4,  "speed": 2.0},
    "goblin":    {"char": "g", "color": "0,180,0",      "hp": 30,  "atk": 10, "xp": 10, "speed": 1.0},
    "skeleton":  {"char": "S", "color": "220,220,220",  "hp": 40,  "atk": 14, "xp": 15, "speed": 0.8},
    "spider":    {"char": "s", "color": "80,80,80",     "hp": 24,  "atk": 8,  "xp": 8,  "speed": 1.8},
    "slime":     {"char": "J", "color": "50,200,50",    "hp": 50,  "atk": 6,  "xp": 12, "speed": 0.5},
    "orc":       {"char": "O", "color": "100,160,50",   "hp": 70,  "atk": 20, "xp": 25, "speed": 0.7},
    "wraith":    {"char": "W", "color": "150,150,255",  "hp": 60,  "atk": 24, "xp": 30, "speed": 1.2},
    "demon":     {"char": "D", "color": "255,50,0",     "hp": 100, "atk": 30, "xp": 50, "speed": 0.9},
    "dragon":    {"char": "K", "color": "255,100,0",    "hp": 200, "atk": 50, "xp": 100,"speed": 0.6},
    # Ranged mobs
    "skeleton_archer": {"char": "A", "color": "200,200,180", "hp": 25, "atk": 8, "xp": 12, "speed": 1.0,
                        "ranged": True, "attack_range": 5, "projectile_char": "-", "projectile_color": "220,200,140"},
    "fire_mage":       {"char": "f", "color": "255,100,0",   "hp": 20, "atk": 12,"xp": 18, "speed": 0.8,
                        "ranged": True, "attack_range": 6, "spell": "burn",
                        "projectile_char": "*", "projectile_color": "255,120,0"},
    "frost_mage":      {"char": "F", "color": "100,200,255", "hp": 22, "atk": 10,"xp": 16, "speed": 0.8,
                        "ranged": True, "attack_range": 5, "spell": "slow",
                        "projectile_char": "*", "projectile_color": "150,220,255"},
    "dark_mage":       {"char": "X", "color": "180,0,255",   "hp": 18, "atk": 18,"xp": 22, "speed": 0.7,
                        "ranged": True, "attack_range": 7,
                        "projectile_char": "*", "projectile_color": "200,50,255"},
}


class Monster(Entity):
    def __init__(self, x: int, y: int, monster_type: str, floor: int = 1):
        info = MONSTER_TYPES.get(monster_type, MONSTER_TYPES["rat"])
        super().__init__(x, y, info["char"], monster_type.capitalize(), info["color"])
        self.monster_type = monster_type
        self.atk = int(info["atk"] * (1 + floor * 0.2))
        self.speed = info["speed"]
        self.xp_value = int(info["xp"] * (1 + floor * 0.15))
        hp_mult = 1 + floor * 0.3
        self.hp = int(info["hp"] * hp_mult)
        self.max_hp = self.hp
        self.defense = int(floor * 0.8)
        self.dodge = 0.05
        self.aggro_range = 6
        self.last_move = 0.0
        self.last_attack = 0.0
        self.attack_delay = 0.8
        self.color = info["color"]
        # Ranged attack support
        self.ranged = info.get("ranged", False)
        self.attack_range = info.get("attack_range", 1)
        self.spell = info.get("spell", "")
        self.projectile_char = info.get("projectile_char", "-")
        self.projectile_color = info.get("projectile_color", "200,200,200")

    def can_see_player(self, player_x: int, player_y: int) -> bool:
        dx = abs(self.x - player_x)
        dy = abs(self.y - player_y)
        return max(dx, dy) <= self.aggro_range

    def move_towards(self, player_x: int, player_y: int, now: float, walls, occupied: set = None) -> Optional[Tuple[int, int]]:
        if now - self.last_move < 1.0 / self.speed:
            return None
        dx = 0
        dy = 0
        if player_x > self.x: dx = 1
        elif player_x < self.x: dx = -1
        if player_y > self.y: dy = 1
        elif player_y < self.y: dy = -1
        nx, ny = self.x + dx, self.y + dy
        if (nx, ny) not in walls and (not occupied or (nx, ny) not in occupied):
            self.x, self.y = nx, ny
            self.last_move = now
            return (nx, ny)
        nx2 = self.x + dx
        if (nx2, self.y) not in walls and dx != 0 and (not occupied or (nx2, self.y) not in occupied):
            self.x = nx2
            self.last_move = now
            return (nx2, self.y)
        ny2 = self.y + dy
        if (self.x, ny2) not in walls and dy != 0 and (not occupied or (self.x, ny2) not in occupied):
            self.y = ny2
            self.last_move = now
            return (self.x, ny2)
        return None

    def wander(self, now: float, walls, occupied: set = None) -> Optional[Tuple[int, int]]:
        if now - self.last_move < 1.0 / self.speed:
            return None
        dirs = [(0,1),(0,-1),(1,0),(-1,0)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = self.x + dx, self.y + dy
            if (nx, ny) not in walls and (not occupied or (nx, ny) not in occupied):
                self.x, self.y = nx, ny
                self.last_move = now
                return (nx, ny)
        return None

    def take_damage(self, dmg: int) -> int:
        self.hp -= dmg
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return dmg


# ============================================================
#  Ally (Summoned creature)
# ============================================================

class Ally(Entity):
    BASE_STATS = {
        "skeleton":  {"hp": 20, "atk": 6, "speed": 1.0, "def": 1},
        "wraith":    {"hp": 15, "atk": 4, "speed": 1.5, "def": 1},
        "fire_spirit": {"hp": 12, "atk": 10, "speed": 1.2, "def": 1},
    }

    def __init__(self, x: int, y: int, ally_type: str = "skeleton", duration: float = float('inf')):
        info = self.BASE_STATS.get(ally_type, self.BASE_STATS["skeleton"])

        super().__init__(x, y, {"skeleton": "s", "wraith": "w", "fire_spirit": "f"}.get(ally_type, "s"), ally_type.capitalize(), {
            "skeleton": "200,200,180", "wraith": "150,180,255", "fire_spirit": "255,120,0"
        }.get(ally_type, "200,200,180"))
        self.ally_type = ally_type
        self.base_atk = info["atk"]
        self.base_hp = info["hp"]
        self.base_speed = info["speed"]
        self.atk = info["atk"]
        self.speed = info["speed"]
        self.max_hp = info["hp"]
        self.hp = self.max_hp
        self.defense = info["def"]
        self.aggro_range = 8
        self.last_move = 0.0
        self.last_attack = 0.0
        self.attack_delay = 0.6
        self.spawn_time = time.time()
        self.duration = duration
        self.is_ally = True
        self.level = 1
        self.xp = 0
        self.xp_to_next = 15

    def expired(self) -> bool:
        if self.duration == float('inf'):
            return False
        return (time.time() - self.spawn_time) >= self.duration

    @property
    def is_infinite(self) -> bool:
        return self.duration == float('inf')

    def can_see_enemy(self, enemy_x: int, enemy_y: int, walls=None) -> bool:
        dx = abs(self.x - enemy_x)
        dy = abs(self.y - enemy_y)
        if max(dx, dy) > self.aggro_range:
            return False
        if walls is not None:
            return has_line_of_sight(self.x, self.y, enemy_x, enemy_y, walls)
        return True

    def move_towards(self, tx: int, ty: int, now: float, walls, occupied: set = None) -> Optional[Tuple[int, int]]:
        if now - self.last_move < 1.0 / self.speed:
            return None
        dx = 0
        dy = 0
        if tx > self.x: dx = 1
        elif tx < self.x: dx = -1
        if ty > self.y: dy = 1
        elif ty < self.y: dy = -1
        nx, ny = self.x + dx, self.y + dy
        if (nx, ny) not in walls and (not occupied or (nx, ny) not in occupied):
            self.x, self.y = nx, ny
            self.last_move = now
            return (nx, ny)
        # Try axis-aligned fallback
        nx2 = self.x + dx
        if (nx2, self.y) not in walls and dx != 0 and (not occupied or (nx2, self.y) not in occupied):
            self.x = nx2
            self.last_move = now
            return (nx2, self.y)
        ny2 = self.y + dy
        if (self.x, ny2) not in walls and dy != 0 and (not occupied or (self.x, ny2) not in occupied):
            self.y = ny2
            self.last_move = now
            return (self.x, ny2)
        return None

    def take_damage(self, dmg: int) -> int:
        self.hp -= dmg
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return dmg

    def gain_xp(self, amount: int) -> bool:
        self.xp += amount
        if self.xp >= self.xp_to_next:
            self.level += 1
            self.xp -= self.xp_to_next
            self.xp_to_next = int(15 * (1.3 ** self.level))
            self._recalc_level_stats()
            return True
        return False

    def _recalc_level_stats(self):
        info = self.BASE_STATS.get(self.ally_type, self.BASE_STATS["skeleton"])
        lv = self.level - 1
        self.max_hp = info["hp"] + lv * 4
        self.hp = self.max_hp
        self.atk = info["atk"] + lv * 2
        self.defense = info["def"] + lv
        self.speed = info["speed"] + lv * 0.05


# ============================================================
#  Boss
# ============================================================

BOSS_TYPES = {
    "Goblin King":  {"char": "G", "color": "0,255,0",   "hp": 180, "atk": 28, "xp": 80},
    "Lich":         {"char": "L", "color": "100,0,255", "hp": 270, "atk": 40, "xp": 150},
    "Minotaur":     {"char": "M", "color": "180,100,0", "hp": 340, "atk": 50, "xp": 200},
    "Dragon Lord":  {"char": "F", "color": "255,80,0",  "hp": 450, "atk": 68, "xp": 300},
}


class Boss(Entity):
    def __init__(self, x: int, y: int, boss_type: str, floor: int = 1):
        info = BOSS_TYPES.get(boss_type, BOSS_TYPES["Goblin King"])
        super().__init__(x, y, info["char"], boss_type, info["color"])
        self.boss_type = boss_type
        hp_mult = 1 + floor * 0.4
        self.hp = int(info["hp"] * hp_mult)
        self.max_hp = self.hp
        self.atk = int(info["atk"] * (1 + floor * 0.25))
        self.xp_value = int(info["xp"] * (1 + floor * 0.25))
        self.defense = int(floor * 1.2)
        self.dodge = 0.10
        self.aggro_range = 10
        self.last_move = 0.0
        self.last_attack = 0.0
        self.attack_delay = 1.0
        self.speed = 0.5
        self.phase = 1
        self.color = info["color"]

    def can_see_player(self, player_x: int, player_y: int) -> bool:
        dx = abs(self.x - player_x)
        dy = abs(self.y - player_y)
        return max(dx, dy) <= self.aggro_range

    def move_towards(self, player_x: int, player_y: int, now: float, walls, occupied: set = None) -> Optional[Tuple[int, int]]:
        if now - self.last_move < 1.0 / self.speed:
            return None
        dx = 0
        dy = 0
        if player_x > self.x: dx = 1
        elif player_x < self.x: dx = -1
        if player_y > self.y: dy = 1
        elif player_y < self.y: dy = -1
        nx, ny = self.x + dx, self.y + dy
        if (nx, ny) not in walls and (not occupied or (nx, ny) not in occupied):
            self.x, self.y = nx, ny
            self.last_move = now
            return (nx, ny)
        nx2 = self.x + dx
        if (nx2, self.y) not in walls and dx != 0 and (not occupied or (nx2, self.y) not in occupied):
            self.x = nx2
            self.last_move = now
            return (nx2, self.y)
        ny2 = self.y + dy
        if (self.x, ny2) not in walls and dy != 0 and (not occupied or (self.x, ny2) not in occupied):
            self.y = ny2
            self.last_move = now
            return (self.x, ny2)
        return None

    def take_damage(self, dmg: int) -> int:
        self.hp -= dmg
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        if self.alive and self.hp < self.max_hp * 0.5 and self.phase == 1:
            self.phase = 2
            self.speed = 0.8
        if self.alive and self.hp < self.max_hp * 0.3 and self.phase == 2:
            self.phase = 3
            self.speed = 1.2
            self.atk = int(self.atk * 1.2)
        return dmg


# ============================================================
#  Chest
# ============================================================

class Chest(Entity):
    def __init__(self, x: int, y: int):
        super().__init__(x, y, "=", "Chest", "255,215,0")
        self.opened = False
        self.items: List[Item] = []
        self.gold = 0

    def generate_loot(self, floor: int = 1, class_name: str = ""):
        from items import generate_random_item
        count = random.randint(1, 3)
        for _ in range(count):
            self.items.append(generate_random_item(floor, class_name))
        from config import CHEST_GOLD_MIN, CHEST_GOLD_MAX
        self.gold = random.randint(CHEST_GOLD_MIN, CHEST_GOLD_MAX)

    def open(self):
        self.opened = True
        self.char = "x"
        self.name = "Opened Chest"

    def draw(self, brightness: float = 1.0) -> str:
        if self.opened:
            return "\x1b[38;2;100;100;100mx\x1b[0m"
        return "\x1b[1m\x1b[38;2;255;215;0m=\x1b[0m"


# ============================================================
#  NPC Enemy (dungeon hostile NPC with class)
# ============================================================

NPC_NAMES = [
    "Артём", "Богдан", "Вадим", "Глеб", "Даниил", "Егор", "Жан", "Захар",
    "Илья", "Кирилл", "Лев", "Максим", "Никита", "Олег", "Пётр", "Роман",
    "Семён", "Тимур", "Фёдор", "Эдуард", "Ярослав", "Андрей", "Борис",
    "Виктор", "Григорий", "Дмитрий", "Евгений", "Игорь", "Константин",
    "Леонид", "Михаил", "Николай", "Павел", "Сергей", "Валерий", "Алексей",
]

NPC_CLASS_NAMES_RU = {
    "swordsman": "Мечник",
    "archer": "Лучник",
    "mage": "Маг",
    "healer": "Целитель",
    "rogue": "Разбойник",
}

class NPCEnemy(Entity):
    def __init__(self, x: int, y: int, class_name: str, floor: int = 1):
        self.class_name = class_name
        name = random.choice(NPC_NAMES)
        class_ru = NPC_CLASS_NAMES_RU.get(class_name, class_name)
        display = f"{name} ({class_ru})"
        color_map = {
            "swordsman": "220,180,80",
            "archer": "180,220,80",
            "mage": "120,150,255",
            "healer": "100,255,180",
            "rogue": "200,80,200",
        }
        super().__init__(x, y, "@", display, color_map.get(class_name, "200,200,200"))
        self.class_name = class_name
        self.level = max(1, floor)
        base = CLASS_BASE_STATS.get(class_name, CLASS_BASE_STATS["swordsman"])
        self.base_str = base["str"] + floor
        self.base_agi = base["agi"] + floor
        self.base_int = base["int"] + floor
        self._recalc_stats()
        self.hp = self.max_hp
        self.mp = self.max_mp
        self.floor = floor
        self.xp_value = int(15 * (1 + floor * 0.2))
        # Skills
        self.skills: List[Optional[Skill]] = [None, None, None, None, None, None]
        self.learned_skills: List[str] = []
        for slot in range(6):
            sk = get_skill_for_slot(class_name, slot)
            if sk:
                self.skills[slot] = sk
                self.learned_skills.append(sk.id)
        # AI timers
        self.last_move = 0.0
        self.last_attack = 0.0
        self.last_spell = 0.0
        self.attack_delay = 0.6 if class_name == "rogue" else 0.8
        self.speed = 1.0
        self.aggro_range = 8
        self.dodge = 0.10 if class_name == "rogue" else 0.05
        self.ranged = class_name in ("archer", "mage")
        self.attack_range = 5 if class_name == "archer" else 6 if class_name == "mage" else 1
        self.healer = class_name == "healer"
        self.ai_state = "idle"
        self.ai_target_pos = None
        self.last_ai_update = 0.0

    def _recalc_stats(self):
        s = self.base_str
        a = self.base_agi
        i = self.base_int
        base_hp_map = {"swordsman": 40, "archer": 25, "mage": 20, "healer": 22, "rogue": 23}
        base_hp = base_hp_map.get(self.class_name, 30)
        self.max_hp = base_hp + s * 2 + self.level * 3
        self.max_mp = 30 + i * 3 + self.level * 2
        self.mp = self.max_mp
        self._atk = 10 + int(s * 0.5)
        self.defense = 3 + int(a * 0.3)
        self._crit = 0.05 + a * 0.003
        if self.class_name == "rogue":
            self._crit = 0.12 + a * 0.005
        if self.class_name == "healer":
            self._atk = int(self._atk * 0.7)
        self._magic_power = int(i * 0.5)
        if self.class_name == "healer":
            self._magic_power = int(i * 0.7)

    @property
    def atk(self):
        return self._atk

    @property
    def crit(self):
        return self._crit

    @property
    def magic_power(self):
        return self._magic_power

    def can_see_player(self, player_x: int, player_y: int) -> bool:
        dx = abs(self.x - player_x)
        dy = abs(self.y - player_y)
        return max(dx, dy) <= self.aggro_range

    def move_towards(self, player_x: int, player_y: int, now: float, walls, occupied: set = None):
        if now - self.last_move < 1.0 / self.speed:
            return None
        dx = 0
        dy = 0
        if player_x > self.x: dx = 1
        elif player_x < self.x: dx = -1
        if player_y > self.y: dy = 1
        elif player_y < self.y: dy = -1
        nx, ny = self.x + dx, self.y + dy
        if (nx, ny) not in walls and (not occupied or (nx, ny) not in occupied):
            self.x, self.y = nx, ny
            self.last_move = now
            return (nx, ny)
        nx2 = self.x + dx
        if (nx2, self.y) not in walls and dx != 0 and (not occupied or (nx2, self.y) not in occupied):
            self.x = nx2
            self.last_move = now
            return (nx2, self.y)
        ny2 = self.y + dy
        if (self.x, ny2) not in walls and dy != 0 and (not occupied or (self.x, ny2) not in occupied):
            self.y = ny2
            self.last_move = now
            return (self.x, ny2)
        return None

    def wander(self, now: float, walls, occupied: set = None):
        if now - self.last_move < 1.0 / self.speed:
            return None
        dirs = [(0,1),(0,-1),(1,0),(-1,0)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = self.x + dx, self.y + dy
            if (nx, ny) not in walls and (not occupied or (nx, ny) not in occupied):
                self.x, self.y = nx, ny
                self.last_move = now
                return (nx, ny)
        return None

    def take_damage(self, dmg: int) -> int:
        self.hp -= dmg
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return dmg

    def heal(self, amount: int):
        self.hp = min(self.hp + amount, self.max_hp)

    def restore_mp(self, amount: int):
        self.mp = min(self.mp + int(amount), self.max_mp)

    def use_skill(self, slot: int, now: float):
        if slot >= len(self.skills):
            return None
        skill = self.skills[slot]
        if skill is None:
            return None
        if not skill.ready(now):
            return None
        if self.mp < skill.mana_cost:
            return None
        self.mp -= skill.mana_cost
        skill.use(now)
        return skill


# ============================================================
#  NPC Ally (hired in city, follows player)
# ============================================================

class NPCAlly(Entity):
    def __init__(self, x: int, y: int, class_name: str, floor: int = 1, name: str = ""):
        self.class_name = class_name
        if not name:
            name = random.choice(NPC_NAMES)
        class_ru = NPC_CLASS_NAMES_RU.get(class_name, class_name)
        display = f"{name} ({class_ru})"
        color_map = {
            "swordsman": "255,220,100",
            "archer": "200,255,100",
            "mage": "150,180,255",
            "healer": "100,255,200",
            "rogue": "220,100,255",
        }
        super().__init__(x, y, "@", display, color_map.get(class_name, "200,255,200"))
        self.class_name = class_name
        self.level = max(1, floor)
        base = CLASS_BASE_STATS.get(class_name, CLASS_BASE_STATS["swordsman"])
        self.base_str = base["str"] + floor
        self.base_agi = base["agi"] + floor
        self.base_int = base["int"] + floor
        self._recalc_stats()
        self.hp = self.max_hp
        self.mp = self.max_mp
        self.floor = floor
        self.xp = 0
        self.xp_to_next = 30
        # Skills
        self.skills: List[Optional[Skill]] = [None, None, None, None, None, None]
        self.learned_skills: List[str] = []
        for slot in range(6):
            sk = get_skill_for_slot(class_name, slot)
            if sk:
                self.skills[slot] = sk
                self.learned_skills.append(sk.id)
        # AI
        self.last_move = 0.0
        self.last_attack = 0.0
        self.last_spell = 0.0
        self.attack_delay = 0.6 if class_name == "rogue" else 0.8
        self.speed = 1.0
        self.aggro_range = 8
        self.dodge = 0.10 if class_name == "rogue" else 0.05
        self.ranged = class_name in ("archer", "mage")
        self.attack_range = 5 if class_name == "archer" else 6 if class_name == "mage" else 1
        self.healer = class_name == "healer"
        self.is_ally = True

    def _recalc_stats(self):
        s = self.base_str
        a = self.base_agi
        i = self.base_int
        base_hp_map = {"swordsman": 40, "archer": 25, "mage": 20, "healer": 22, "rogue": 23}
        base_hp = base_hp_map.get(self.class_name, 30)
        self.max_hp = base_hp + s * 2 + self.level * 3
        self.max_mp = 30 + i * 3 + self.level * 2
        self._atk = 10 + int(s * 0.5)
        self.defense = 3 + int(a * 0.3)
        self._crit = 0.05 + a * 0.003
        if self.class_name == "rogue":
            self._crit = 0.12 + a * 0.005
        if self.class_name == "healer":
            self._atk = int(self._atk * 0.7)
        self._magic_power = int(i * 0.5)
        if self.class_name == "healer":
            self._magic_power = int(i * 0.7)

    @property
    def atk(self):
        return self._atk

    @property
    def crit(self):
        return self._crit

    @property
    def magic_power(self):
        return self._magic_power

    @property
    def weapon_type(self) -> str:
        return {"swordsman": "sword", "archer": "bow", "mage": "staff",
                "healer": "mace", "rogue": "dagger"}.get(self.class_name, "sword")

    def move_towards(self, tx: int, ty: int, now: float, walls, occupied: set = None):
        if now - self.last_move < 1.0 / self.speed:
            return None
        dx = 0
        dy = 0
        if tx > self.x: dx = 1
        elif tx < self.x: dx = -1
        if ty > self.y: dy = 1
        elif ty < self.y: dy = -1
        nx, ny = self.x + dx, self.y + dy
        if (nx, ny) not in walls and (not occupied or (nx, ny) not in occupied):
            self.x, self.y = nx, ny
            self.last_move = now
            return (nx, ny)
        nx2 = self.x + dx
        if (nx2, self.y) not in walls and dx != 0 and (not occupied or (nx2, self.y) not in occupied):
            self.x = nx2
            self.last_move = now
            return (nx2, self.y)
        ny2 = self.y + dy
        if (self.x, ny2) not in walls and dy != 0 and (not occupied or (self.x, ny2) not in occupied):
            self.y = ny2
            self.last_move = now
            return (self.x, ny2)
        return None

    def take_damage(self, dmg: int) -> int:
        self.hp -= dmg
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return dmg

    def heal(self, amount: int):
        self.hp = min(self.hp + amount, self.max_hp)

    def restore_mp(self, amount: int):
        self.mp = min(self.mp + int(amount), self.max_mp)

    def use_skill(self, slot: int, now: float):
        if slot >= len(self.skills):
            return None
        skill = self.skills[slot]
        if skill is None:
            return None
        if not skill.ready(now):
            return None
        if self.mp < skill.mana_cost:
            return None
        self.mp -= skill.mana_cost
        skill.use(now)
        return skill

    def gain_xp(self, amount: int) -> bool:
        self.xp += amount
        if self.xp >= self.xp_to_next:
            self.level += 1
            self.xp -= self.xp_to_next
            self.xp_to_next = int(30 * (1.3 ** self.level))
            self.base_str += 1
            self.base_agi += 1
            self.base_int += 1
            self._recalc_stats()
            self.hp = self.max_hp
            self.mp = self.max_mp
            return True
        return False
