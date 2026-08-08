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
    "swordsman", "sword", 0, 0.4, 8, 20, 1, aoe=3))

_reg(Skill("sword_1", "Whirlwind",
    "Spin attack, hits all enemies in 3x3",
    "swordsman", "sword", 1, 1.2, 14, 14, 1, aoe=1))

_reg(Skill("sword_2", "Shield Bash",
    "Bash enemy, stun 1.5s + knockback",
    "swordsman", "sword", 2, 2.0, 12, 8, 1, effect="stun", effect_duration=1.5))

_reg(Skill("sword_3", "War Cry",
    "Heal 20% HP, gain 30% ATK for 4s",
    "swordsman", "sword", 3, 6.0, 18, 0, 0, effect="heal", effect_power=20, effect_duration=4.0))

_reg(Skill("sword_4", "Berserk",
    "+80% ATK, +50% speed, -20% DEF for 6s",
    "swordsman", "sword", 4, 10.0, 28, 0, 0, effect="buff", effect_power=80, effect_duration=6.0))


# ============================================================
#  ARCHER — ranged DPS, DOT, crowd control
# ============================================================
_reg(Skill("archer_0", "Quick Shot",
    "Fast arrow, low cooldown",
    "archer", "bow", 0, 0.5, 5, 9, 8))

_reg(Skill("archer_1", "Volley",
    "3 arrows in a spread",
    "archer", "bow", 1, 1.0, 12, 10, 5, aoe=3))

_reg(Skill("archer_2", "Poison Arrow",
    "Poison DOT for 4s, -3 dmg/tick",
    "archer", "bow", 2, 2.5, 10, 10, 6, effect="burn", effect_duration=4.0, effect_power=3))

_reg(Skill("archer_3", "Frost Arrow",
    "Slow enemy 60% for 3s",
    "archer", "bow", 3, 3.0, 8, 10, 6, effect="slow", effect_duration=3.0, effect_power=60))

_reg(Skill("archer_4", "Arrow Rain",
    "Massive 5x5 AoE barrage",
    "archer", "bow", 4, 5.0, 28, 8, 10, aoe=2))


# ============================================================
#  MAGE — AoE king, burst, utility
# ============================================================
_reg(Skill("mage_0", "Fireball",
    "Explosive fireball, burn 3s",
    "mage", "staff", 0, 2.0, 16, 14, 12, effect="burn", effect_duration=3.0, effect_power=4))

_reg(Skill("mage_1", "Chain Lightning",
    "Lightning bounces to 3 targets",
    "mage", "staff", 1, 3.0, 14, 12, 14, aoe=3))

_reg(Skill("mage_2", "Blizzard",
    "5x5 ice storm, slow 50% 2s",
    "mage", "staff", 2, 5.5, 22, 10, 16, aoe=2, effect="slow", effect_duration=2.0, effect_power=50))

_reg(Skill("mage_3", "Mana Shield",
    "Absorb next 40 damage for 8s",
    "mage", "staff", 3, 14.0, 35, 0, 0, effect="shield", effect_duration=8.0, effect_power=40))

_reg(Skill("mage_4", "Blink",
    "Teleport 5 tiles in facing direction",
    "mage", "staff", 4, 5.0, 10, 0, 0, effect="teleport"))


# ============================================================
#  SUMMONER — allies, debuffs, sustain
# ============================================================
_reg(Skill("summon_0", "Raise Dead",
    "Summon 1 skeleton warrior (infinite, max 3)",
    "summoner", "orb", 0, 4.0, 10, 0, 0, effect="summon", effect_duration=float('inf'), effect_power=1))

_reg(Skill("summon_1", "Spirit Drain",
    "Drain HP from nearby enemy, heal self",
    "summoner", "orb", 1, 2.5, 14, 6, 1, effect="lifesteal", effect_duration=1.0, effect_power=50))

_reg(Skill("summon_2", "Fire Nova",
    "AoE fire explosion around self",
    "summoner", "orb", 2, 2.0, 18, 0, 3, aoe=1, effect="burn", effect_duration=2.0, effect_power=5))

_reg(Skill("summon_3", "Bone Wall",
    "Summon bone wall for 6s, blocks enemies",
    "summoner", "orb", 3, 8.0, 12, 0, 0, effect="decoy", effect_duration=6.0))

_reg(Skill("summon_4", "Army of the Dead",
    "Summon 5 temporary skeletons (30s)",
    "summoner", "orb", 4, 15.0, 30, 0, 0, effect="summon", effect_duration=30.0, effect_power=5))


# ============================================================
#  HEALER — support, heals allies, buffs, restores MP
# ============================================================
#  HEALER — support, heals, buffs, utility
# ============================================================
_reg(Skill("heal_0", "Holy Light",
    "Fast heal self (15% HP)",
    "healer", "mace", 0, 1.5, 10, 0, 0, effect="heal", effect_power=15))

_reg(Skill("heal_1", "Greater Heal",
    "Powerful self heal (30% HP)",
    "healer", "mace", 1, 5.0, 22, 0, 0, effect="heal", effect_power=30))

_reg(Skill("heal_2", "Radiance",
    "AoE heal self (12% HP) + shield 30 for 5s",
    "healer", "mace", 2, 8.0, 26, 0, 0, effect="heal", effect_power=12))

_reg(Skill("heal_3", "Blessing",
    "Buff self +40% ATK for 8s + shield 30",
    "healer", "mace", 3, 10.0, 32, 0, 0, effect="buff", effect_power=40, effect_duration=8.0))

_reg(Skill("heal_4", "Divine Surge",
    "Heal self 18% HP + restore 60 MP",
    "healer", "mace", 4, 12.0, 40, 0, 0, effect="heal", effect_power=18, mana_regen=60))


# ============================================================
#  ROGUE — melee DPS, crits, poison, evasion
# ============================================================
_reg(Skill("rogue_0", "Backstab",
    "Melee attack with +100% crit, high damage (25)",
    "rogue", "dagger", 0, 0.8, 4, 25, 1, effect="crit_boost", effect_power=100))

_reg(Skill("rogue_1", "Shadow Strike",
    "Teleport behind enemy + hit (20 dmg, +50% crit)",
    "rogue", "dagger", 1, 3.0, 10, 20, 6, effect="crit_boost", effect_power=50))

_reg(Skill("rogue_2", "Fan of Knives",
    "AoE 3x3, each target gets 15 dmg + separate crit",
    "rogue", "dagger", 2, 2.0, 8, 15, 1, aoe=1))

_reg(Skill("rogue_3", "Poison Blade",
    "Hit 15 dmg + burn DOT 6dmg/s for 5s",
    "rogue", "dagger", 3, 3.0, 7, 15, 1, effect="burn", effect_duration=5.0, effect_power=6))

_reg(Skill("rogue_4", "Vanish",
    "+50% dodge, +30% speed for 6s",
    "rogue", "dagger", 4, 8.0, 8, 0, 0, effect="evasion", effect_duration=6.0, effect_power=50))


# ============================================================
#  Skill management
# ============================================================

def get_skill_for_slot(class_name: str, slot: int) -> Optional[Skill]:
    prefix = {"swordsman": "sword", "archer": "archer", "mage": "mage", "summoner": "summon", "healer": "heal", "rogue": "rogue"}.get(class_name, "")
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
    for i in range(6):
        s = get_skill_for_slot(class_name, i)
        if s:
            result.append(s)
    return result
