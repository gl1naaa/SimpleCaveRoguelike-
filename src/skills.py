import time
import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List

@dataclass
class Skill:
    id: str
    name: str
    description: str
    class_req: str
    weapon_req: str
    slot: int
    cooldown: float
    mana_cost: int
    damage: int
    range: int
    aoe: int = 0         # 0=single, 1=3x3, 2=5x5, 3=line
    effect: str = ""     # burn, freeze, slow, stun, knockback, heal, buff, shield, teleport, summon, decoy, lifesteal, cleave, dash, aura
    effect_duration: float = 0.0
    effect_power: int = 0
    last_used: float = 0.0
    mana_regen: int = 0  # bonus mp regen on hit

    def ready(self, now: float) -> bool:
        return (now - self.last_used) >= self.cooldown

    def use(self, now: float):
        self.last_used = now


ALL_SKILLS: Dict[str, Skill] = {}

def _reg(s):
    ALL_SKILLS[s.id] = s


# ============================================================
#  SWORDSMAN — melee warrior, high burst, self-buff
# ============================================================
_reg(Skill("sword_0", "Cleave",
    "Wide slash hitting 3 enemies in front",
    "swordsman", "sword", 0, 0.4, 4, 20, 1, aoe=3))

_reg(Skill("sword_1", "Whirlwind",
    "Spin attack, hits all enemies in 3x3",
    "swordsman", "sword", 1, 1.2, 8, 14, 1, aoe=1))

_reg(Skill("sword_2", "Shield Bash",
    "Bash enemy, stun 1.5s + knockback",
    "swordsman", "sword", 2, 2.0, 6, 8, 1, effect="stun", effect_duration=1.5))

_reg(Skill("sword_3", "War Cry",
    "Heal 20% HP, gain 30% ATK for 4s",
    "swordsman", "sword", 3, 6.0, 10, 0, 0, effect="heal", effect_power=20, effect_duration=4.0))

_reg(Skill("sword_4", "Berserk",
    "+80% ATK, +50% speed, -20% DEF for 6s",
    "swordsman", "sword", 4, 10.0, 18, 0, 0, effect="buff", effect_power=80, effect_duration=6.0))


# ============================================================
#  ARCHER — ranged DPS, DOT, crowd control
# ============================================================
_reg(Skill("archer_0", "Quick Shot",
    "Fast arrow, low cooldown",
    "archer", "bow", 0, 0.5, 2, 9, 8))

_reg(Skill("archer_1", "Volley",
    "3 arrows in a spread",
    "archer", "bow", 1, 1.0, 6, 10, 5, aoe=3))

_reg(Skill("archer_2", "Poison Arrow",
    "Poison DOT for 4s, -3 dmg/tick",
    "archer", "bow", 2, 2.5, 5, 10, 6, effect="burn", effect_duration=4.0, effect_power=3))

_reg(Skill("archer_3", "Frost Arrow",
    "Slow enemy 60% for 3s",
    "archer", "bow", 3, 3.0, 4, 10, 6, effect="slow", effect_duration=3.0, effect_power=60))

_reg(Skill("archer_4", "Arrow Rain",
    "Massive 5x5 AoE barrage",
    "archer", "bow", 4, 5.0, 18, 8, 10, aoe=2))


# ============================================================
#  MAGE — AoE king, burst, utility
# ============================================================
_reg(Skill("mage_0", "Fireball",
    "Explosive fireball, burn 3s",
    "mage", "staff", 0, 1.2, 10, 14, 4, effect="burn", effect_duration=3.0, effect_power=4))

_reg(Skill("mage_1", "Chain Lightning",
    "Lightning bounces to 3 targets",
    "mage", "staff", 1, 2.5, 8, 10, 3, aoe=3))

_reg(Skill("mage_2", "Blizzard",
    "5x5 ice storm, slow 50% 2s",
    "mage", "staff", 2, 4.5, 14, 8, 10, aoe=2, effect="slow", effect_duration=2.0, effect_power=50))

_reg(Skill("mage_3", "Mana Shield",
    "Absorb next 40 damage for 8s",
    "mage", "staff", 3, 12.0, 25, 0, 0, effect="shield", effect_duration=8.0, effect_power=40))

_reg(Skill("mage_4", "Blink",
    "Teleport 5 tiles in facing direction",
    "mage", "staff", 4, 4.0, 0, 0, 0, effect="teleport"))


# ============================================================
#  SUMMONER — allies, debuffs, sustain
# ============================================================
_reg(Skill("summon_0", "Raise Dead",
    "Summon 1 skeleton warrior (infinite, max 3)",
    "summoner", "orb", 0, 4.0, 0, 0, 0, effect="summon", effect_duration=float('inf'), effect_power=1))

_reg(Skill("summon_1", "Spirit Drain",
    "Drain HP from nearby enemy, heal self",
    "summoner", "orb", 1, 2.5, 8, 6, 1, effect="lifesteal", effect_duration=1.0, effect_power=50))

_reg(Skill("summon_2", "Fire Nova",
    "AoE fire explosion around self",
    "summoner", "orb", 2, 2.0, 12, 0, 3, aoe=1, effect="burn", effect_duration=2.0, effect_power=5))

_reg(Skill("summon_3", "Bone Wall",
    "Summon bone wall for 6s, blocks enemies",
    "summoner", "orb", 3, 8.0, 0, 0, 0, effect="decoy", effect_duration=6.0))

_reg(Skill("summon_4", "Army of the Dead",
    "Summon 5 temporary skeletons (30s)",
    "summoner", "orb", 4, 15.0, 0, 0, 0, effect="summon", effect_duration=30.0, effect_power=5))


# ============================================================
#  Skill management
# ============================================================

def get_skill_for_slot(class_name: str, slot: int) -> Optional[Skill]:
    prefix = {"swordsman": "sword", "archer": "archer", "mage": "mage", "summoner": "summon"}.get(class_name, "")
    skill_id = f"{prefix}_{slot}"
    return ALL_SKILLS.get(skill_id)

def can_use_skill(skill: Skill, weapon_type: str, mp: int, now: float) -> Tuple[bool, str]:
    if not skill.ready(now):
        remaining = skill.cooldown - (now - skill.last_used)
        return False, f"CD {remaining:.1f}s"
    if weapon_type != skill.weapon_req:
        return False, f"Need {skill.weapon_req}!"
    if mp < skill.mana_cost:
        return False, "No MP!"
    return True, ""

def get_all_skills_for_class(class_name: str) -> List[Skill]:
    result = []
    for i in range(5):
        s = get_skill_for_slot(class_name, i)
        if s:
            result.append(s)
    return result
