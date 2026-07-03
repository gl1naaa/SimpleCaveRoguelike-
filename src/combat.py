import time
import random
import math
from typing import Optional, Tuple, List, Dict, TYPE_CHECKING
if TYPE_CHECKING:
    from entities import Player, Monster, Boss, Ally


class DamagePopup:
    def __init__(self, x: int, y: int, text: str, color: str = "255,255,255", duration: float = 1.5):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.spawn_time = time.time()
        self.duration = duration
        self.start_y = y

    def alive(self) -> bool:
        return (time.time() - self.spawn_time) < self.duration

    def draw(self) -> str:
        r, g, b = map(int, self.color.split(","))
        age = time.time() - self.spawn_time
        # Float upward
        offset = int(age * 3)
        return f"\x1b[38;2;{r};{g};{b}m{self.text}\x1b[0m"


class Projectile:
    def __init__(self, sx: int, sy: int, tx: int, ty: int, char: str, color: str,
                 speed: float = 8.0, on_hit=None, pierce: bool = False, aoe_radius: int = 0):
        self.sx = sx
        self.sy = sy
        self.tx = tx
        self.ty = ty
        self.x = sx
        self.y = sy
        self.char = char
        self.color = color
        self.speed = speed
        self.on_hit = on_hit
        self.pierce = pierce
        self.aoe_radius = aoe_radius
        self.done = False
        self.hit_targets = set()
        self.spawn_time = time.time()

    def update(self, dt: float) -> bool:
        if self.done:
            return False
        dx = self.tx - self.x
        dy = self.ty - self.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 0.5:
            self.x = self.tx
            self.y = self.ty
            self.done = True
            return True
        step = self.speed * dt
        if step >= dist:
            self.x = self.tx
            self.y = self.ty
            self.done = True
            return True
        self.x += dx / dist * step
        self.y += dy / dist * step
        return False

    def alive(self) -> bool:
        if self.done:
            return (time.time() - self.spawn_time) < 0.3
        return True

    def int_pos(self) -> Tuple[int, int]:
        return int(round(self.x)), int(round(self.y))


class StatusEffect:
    def __init__(self, name: str, duration: float, power: int = 0):
        self.name = name
        self.duration = duration
        self.power = power
        self.start_time = time.time()
        self.tick_time = 0.0

    def expired(self) -> bool:
        return (time.time() - self.start_time) >= self.duration

    def should_tick(self, now: float) -> bool:
        if now - self.tick_time >= 1.0:
            self.tick_time = now
            return True
        return False


class CombatSystem:
    def __init__(self):
        self.popups: List[DamagePopup] = []
        self.projectiles: List[Projectile] = []
        self.attack_cooldown = 0.0
        self.ally_attack_cooldown = 0.0
        self.attack_delay = 0.25
        self.meele_range = 1.5
        self.effects: Dict[int, List[StatusEffect]] = {}  # entity_id -> effects

    def can_attack(self, now: float) -> bool:
        return (now - self.attack_cooldown) >= self.attack_delay

    def _calc_damage(self, attacker_atk: int, defender_def: int, crit: float = 0.0, miss_chance: float = 0.0) -> Tuple[int, bool]:
        if miss_chance > 0 and random.random() < miss_chance:
            return 0, False
        is_crit = random.random() < crit
        base = max(1, attacker_atk - defender_def // 2)
        variance = max(1, base // 4)
        dmg = base + random.randint(-variance, variance)
        if is_crit:
            dmg = int(dmg * 2.0)
        return max(1, dmg), is_crit

    def _add_popup(self, x, y, text, color):
        self.popups.append(DamagePopup(x, y, text, color))

    def add_projectile(self, sx, sy, tx, ty, char, color, speed=8.0, on_hit=None, pierce=False, aoe_radius=0):
        self.projectiles.append(Projectile(sx, sy, tx, ty, char, color, speed, on_hit, pierce, aoe_radius))

    def update_projectiles(self, monsters, bosses, player, log, dt, now):
        for proj in self.projectiles[:]:
            arrived = proj.update(dt)
            if arrived:
                ix, iy = proj.int_pos()
                # Hit monsters/bosses
                for m in list(monsters):
                    if m.alive and m.x == ix and m.y == iy and id(m) not in proj.hit_targets:
                        proj.hit_targets.add(id(m))
                        if proj.on_hit:
                            proj.on_hit(m, ix, iy)
                        if not proj.pierce:
                            proj.done = True
                            break
                for b in list(bosses):
                    if b.alive and b.x == ix and b.y == iy and id(b) not in proj.hit_targets:
                        proj.hit_targets.add(id(b))
                        if proj.on_hit:
                            proj.on_hit(b, ix, iy)
                        if not proj.pierce:
                            proj.done = True
                            break
                # AoE explosion on arrival
                if proj.done and proj.aoe_radius > 0 and proj.on_hit:
                    # Explosion particles
                    import random as _rand
                    for _ in range(8):
                        ex = ix + _rand.randint(-int(proj.aoe_radius), int(proj.aoe_radius))
                        ey = iy + _rand.randint(-int(proj.aoe_radius), int(proj.aoe_radius))
                        ed = math.sqrt((ex - ix)**2 + (ey - iy)**2)
                        if ed <= proj.aoe_radius + 0.5:
                            self._add_popup(ex, ey, "*", proj.color)
                    for m in list(monsters):
                        if m.alive and id(m) not in proj.hit_targets:
                            d = math.sqrt((m.x - ix)**2 + (m.y - iy)**2)
                            if d <= proj.aoe_radius:
                                proj.on_hit(m, m.x, m.y)
                    for b in list(bosses):
                        if b.alive and id(b) not in proj.hit_targets:
                            d = math.sqrt((b.x - ix)**2 + (b.y - iy)**2)
                            if d <= proj.aoe_radius:
                                proj.on_hit(b, b.x, b.y)
        self.projectiles = [p for p in self.projectiles if p.alive()]

    def get_projectile_at(self, x: int, y: int) -> Optional[Projectile]:
        for p in self.projectiles:
            px, py = p.int_pos()
            if px == x and py == y:
                return p
        return None

    def _entity_id(self, entity) -> int:
        return id(entity)

    def add_effect(self, entity, effect: StatusEffect):
        eid = self._entity_id(entity)
        if eid not in self.effects:
            self.effects[eid] = []
        # Don't stack same effect, refresh duration
        for e in self.effects[eid]:
            if e.name == effect.name:
                e.duration = effect.duration
                e.start_time = time.time()
                return
        self.effects[eid].append(effect)

    def has_effect(self, entity, effect_name: str) -> bool:
        eid = self._entity_id(entity)
        return any(e.name == effect_name and not e.expired() for e in self.effects.get(eid, []))

    def get_effect_power(self, entity, effect_name: str) -> int:
        eid = self._entity_id(entity)
        for e in self.effects.get(eid, []):
            if e.name == effect_name and not e.expired():
                return e.power
        return 0

    def process_effects(self, entity, now: float) -> int:
        """Process status effects on entity. Returns total bonus damage."""
        eid = self._entity_id(entity)
        total_dmg = 0
        if eid in self.effects:
            for e in self.effects[eid][:]:
                if e.expired():
                    self.effects[eid].remove(e)
                    continue
                if e.name == "burn" and e.should_tick(now):
                    dmg = e.power
                    entity.hp -= dmg
                    if entity.hp <= 0:
                        entity.hp = 0
                        entity.alive = False
                    total_dmg += dmg
                    self._add_popup(entity.x, entity.y, f"-{dmg}", "255,100,0")
        return total_dmg

    def get_speed_mult(self, entity) -> float:
        """Get speed multiplier from slow effects."""
        if self.has_effect(entity, "slow"):
            power = self.get_effect_power(entity, "slow")
            return 1.0 - (power / 100.0)
        return 1.0

    def is_stunned(self, entity) -> bool:
        return self.has_effect(entity, "stun")

    # ---- Player attacks ----

    def player_attack_monster(self, player, monster, now: float) -> Optional[Tuple[int, bool]]:
        if not self.can_attack(now):
            return None
        self.attack_cooldown = now
        atk = player.atk
        if self.has_effect(player, "buff"):
            atk = int(atk * (1 + self.get_effect_power(player, "buff") / 100.0))
        monster_dodge = getattr(monster, 'dodge', 0.05)
        dmg, crit = self._calc_damage(atk, monster.defense, player.crit_chance, monster_dodge)
        if dmg == 0:
            self._add_popup(monster.x, monster.y, "MISS", "200,200,200")
            return 0, False
        monster.take_damage(dmg)
        color = "255,255,100" if crit else "255,200,200"
        self._add_popup(monster.x, monster.y, f"-{dmg}", color)
        return dmg, crit

    def player_use_skill(self, player, skill, targets: list, now: float, occupied: set = None) -> list:
        results = []
        atk = player.atk
        if self.has_effect(player, "buff"):
            atk = int(atk * (1 + self.get_effect_power(player, "buff") / 100.0))

        for target in targets:
            t_def = target.defense if hasattr(target, 'defense') else 0
            if self.has_effect(target, "slow"):
                t_def = max(0, t_def - 2)
            dmg, crit = self._calc_damage(atk + skill.damage, t_def, player.crit_chance)

            target.take_damage(dmg)

            color = "255,255,100" if crit else "255,150,150"
            self._add_popup(target.x, target.y, f"-{dmg}", color)

            # Apply status effect
            if skill.effect and skill.effect_duration > 0:
                if skill.effect == "burn":
                    self.add_effect(target, StatusEffect("burn", skill.effect_duration, skill.effect_power))
                    self._add_popup(target.x, target.y - 1, "BURN", "255,80,0")
                elif skill.effect == "slow":
                    self.add_effect(target, StatusEffect("slow", skill.effect_duration, skill.effect_power))
                    self._add_popup(target.x, target.y - 1, "SLOW", "100,200,255")
                elif skill.effect == "stun":
                    self.add_effect(target, StatusEffect("stun", skill.effect_duration))
                    self._add_popup(target.x, target.y - 1, "STUN", "255,255,0")
                elif skill.effect == "knockback":
                    dx = target.x - player.x
                    dy = target.y - player.y
                    dist = max(1, abs(dx) + abs(dy))
                    target.x += (dx // dist) * 2
                    target.y += (dy // dist) * 2
                    self._add_popup(target.x, target.y - 1, "KNOCK", "200,200,255")
                elif skill.effect == "lifesteal":
                    heal = int(dmg * skill.effect_power / 100.0)
                    player.heal(heal)
                    self._add_popup(player.x, player.y, f"+{heal}", "0,255,100")

            results.append((dmg, crit))

        # Self-targeted effects — ALWAYS execute
        if skill.effect == "heal":
            heal = int(player.max_hp * skill.effect_power / 100.0)
            player.heal(heal)
            self._add_popup(player.x, player.y, f"+{heal}", "0,255,100")
        elif skill.effect == "buff":
            self.add_effect(player, StatusEffect("buff", skill.effect_duration, skill.effect_power))
            self._add_popup(player.x, player.y - 1, f"+{skill.effect_power}% ATK", "255,200,0")
        elif skill.effect == "shield":
            self.add_effect(player, StatusEffect("shield", skill.effect_duration, skill.effect_power))
            self._add_popup(player.x, player.y - 1, f"SHIELD {skill.effect_power}", "100,200,255")
        elif skill.effect == "teleport":
            pass

        return results

    # ---- Monster/Boss attacks ----

    def monster_attack_player(self, monster, player, now: float) -> Optional[Tuple[int, bool]]:
        dist = abs(monster.x - player.x) + abs(monster.y - player.y)
        if dist > self.meele_range:
            return None
        if self.is_stunned(monster):
            self._add_popup(monster.x, monster.y, "STUNNED", "255,255,0")
            return None
        if (now - monster.last_attack) < monster.attack_delay:
            return None
        monster.last_attack = now
        player_dodge = getattr(player, 'dodge_chance', 0.02)
        dmg, crit = self._calc_damage(monster.atk, player.defense, 0.0, player_dodge)
        if dmg == 0:
            self._add_popup(player.x, player.y, "MISS", "200,200,200")
            return 0, False
        # Shield absorbs damage
        if self.has_effect(player, "shield"):
            shield_power = self.get_effect_power(player, "shield")
            absorbed = min(dmg, shield_power)
            dmg -= absorbed
            new_power = shield_power - absorbed
            if new_power <= 0:
                self.effects[self._entity_id(player)] = [
                    e for e in self.effects.get(self._entity_id(player), [])
                    if e.name != "shield"
                ]
            else:
                for e in self.effects.get(self._entity_id(player), []):
                    if e.name == "shield":
                        e.power = new_power
            if absorbed > 0:
                self._add_popup(player.x, player.y, f"BLOCK {absorbed}", "100,200,255")
        if dmg > 0:
            actual = player.take_damage(dmg)
            return actual, crit
        return 0, False

    def boss_attack_player(self, boss, player, now: float) -> Optional[Tuple[int, bool]]:
        dist = abs(boss.x - player.x) + abs(boss.y - player.y)
        if dist > self.meele_range:
            return None
        if self.is_stunned(boss):
            self._add_popup(boss.x, boss.y, "STUNNED", "255,255,0")
            return None
        if (now - boss.last_attack) < boss.attack_delay:
            return None
        boss.last_attack = now
        base_dmg = boss.atk
        if boss.phase >= 2:
            base_dmg = int(base_dmg * 1.3)
        if boss.phase >= 3:
            base_dmg = int(base_dmg * 1.5)
        player_dodge = getattr(player, 'dodge_chance', 0.02)
        dmg, crit = self._calc_damage(base_dmg, player.defense, 0.0, player_dodge)
        if dmg == 0:
            self._add_popup(player.x, player.y, "MISS", "200,200,200")
            return 0, False
        # Shield absorbs
        if self.has_effect(player, "shield"):
            shield_power = self.get_effect_power(player, "shield")
            absorbed = min(dmg, shield_power)
            dmg -= absorbed
            new_power = shield_power - absorbed
            if new_power <= 0:
                self.effects[self._entity_id(player)] = [
                    e for e in self.effects.get(self._entity_id(player), [])
                    if e.name != "shield"
                ]
            else:
                for e in self.effects.get(self._entity_id(player), []):
                    if e.name == "shield":
                        e.power = new_power
            if absorbed > 0:
                self._add_popup(player.x, player.y, f"BLOCK {absorbed}", "100,200,255")
        if dmg > 0:
            actual = player.take_damage(dmg)
            return actual, crit
        return 0, False

    # ---- Ally AI ----

    def ally_can_attack(self, now: float) -> bool:
        return (now - self.ally_attack_cooldown) >= self.attack_delay

    def ally_attack(self, ally, monster, now: float) -> Optional[Tuple[int, bool]]:
        dist = abs(ally.x - monster.x) + abs(ally.y - monster.y)
        if dist > 1:
            return None
        if (now - ally.last_attack) < ally.attack_delay:
            return None
        ally.last_attack = now
        dmg, crit = self._calc_damage(ally.atk, monster.defense)
        monster.take_damage(dmg)
        self._add_popup(monster.x, monster.y, f"-{dmg}", "150,200,255")
        return dmg, crit

    def monster_attack_ally(self, monster, ally, now: float) -> Optional[Tuple[int, bool]]:
        dist = abs(monster.x - ally.x) + abs(monster.y - ally.y)
        if dist > 1:
            return None
        if self.is_stunned(monster):
            self._add_popup(monster.x, monster.y, "STUNNED", "255,255,0")
            return None
        if (now - monster.last_attack) < monster.attack_delay:
            return None
        monster.last_attack = now
        dmg, crit = self._calc_damage(monster.atk, ally.defense)
        ally.take_damage(dmg)
        self._add_popup(ally.x, ally.y, f"-{dmg}", "255,150,150")
        return dmg, crit

    # ---- Popup management ----

    def update_popups(self):
        self.popups = [p for p in self.popups if p.alive()]

    def get_popups_at(self, x: int, y: int) -> List[DamagePopup]:
        return [p for p in self.popups if p.x == x and p.y == y]

    def calculate_xp(self, monster) -> int:
        return monster.xp_value
