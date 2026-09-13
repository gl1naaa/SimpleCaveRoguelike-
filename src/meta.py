# ============================================================
#  Meta-Progression — Dungeon Points
# ============================================================
import os
import json
import tempfile
import copy
from ui import (fg, bg, rst, bold, dim, clear_screen, hide_cursor, show_cursor,
                BOX_H, BOX_V, BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_LT, BOX_RT,
                SH2)
from input import InputState

# --- Save path: meta_save.json in project root (next to src/) ---
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SAVE_PATH = os.path.join(_PROJECT_ROOT, "meta_save.json")

# --- Upgrade costs ---
COST_HP      = 200   # +5 HP per level
COST_ATK     = 300   # +1 ATK per level
COST_POTION  = 150   # Starting health potion (one-time)
COST_MP      = 220   # +8 max MP per level

# --- Default save data ---
_DEFAULT_DATA = {
    "points": 0,
    "upgrades": {
        "max_hp": 0,
        "max_mp": 0,
        "atk": 0,
        "start_potion": 0,
        "unlock_classes": [],
    }
}


class MetaProgression:
    """Persistent meta-progression across runs."""

    def __init__(self):
        self.data = copy.deepcopy(_DEFAULT_DATA)
        self.load()

    # -- IO --

    def load(self):
        try:
            with open(_SAVE_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Merge with defaults so new keys always exist
            for k, v in _DEFAULT_DATA.items():
                if k not in saved:
                    saved[k] = v
            for k, v in _DEFAULT_DATA.get("upgrades", {}).items():
                if k not in saved.get("upgrades", {}):
                    saved["upgrades"][k] = v
            self.data = saved
        except Exception:
            self.data = copy.deepcopy(_DEFAULT_DATA)

    def save(self):
        try:
            directory = os.path.dirname(_SAVE_PATH)
            fd, tmp_path = tempfile.mkstemp(prefix="meta_", suffix=".tmp", dir=directory)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, _SAVE_PATH)
        except Exception:
            pass

    # -- Points --

    @property
    def points(self) -> int:
        return self.data.get("points", 0)

    def add_points(self, floor_reached: int, kills: int, bosses: int):
        """Award points based on run performance. Formula: floor*100 + kills*5 + bosses*200."""
        earned = floor_reached * 100 + kills * 5 + bosses * 200
        self.data["points"] = self.data.get("points", 0) + earned
        self.save()
        return earned

    def spend(self, cost: int) -> bool:
        """Try to spend points. Returns True if successful."""
        if self.data["points"] >= cost:
            self.data["points"] -= cost
            self.save()
            return True
        return False

    # -- Bonuses --

    def get_bonuses(self) -> dict:
        """Return current bonus values for a new run."""
        up = self.data.get("upgrades", {})
        return {
            "bonus_hp": up.get("max_hp", 0) * 5,
            "bonus_mp": up.get("max_mp", 0) * 8,
            "bonus_atk": up.get("atk", 0),
            "start_potion": bool(up.get("start_potion", 0)),
        }

    def get_upgrade_level(self, key: str) -> int:
        return self.data.get("upgrades", {}).get(key, 0)


def apply_meta_bonuses(player, meta: MetaProgression):
    """Apply purchased meta bonuses to a freshly created player."""
    bonuses = meta.get_bonuses()
    if bonuses["bonus_atk"] > 0:
        player.base_atk += bonuses["bonus_atk"]
        player._recalc_stats()
    # Apply flat HP/MP bonuses after the stat recalculation; otherwise a
    # later ATK upgrade would overwrite the already-added HP/MP values.
    if bonuses["bonus_hp"] > 0:
        player.max_hp += bonuses["bonus_hp"]
    if bonuses["bonus_mp"] > 0:
        player.max_mp += bonuses["bonus_mp"]
    if bonuses["bonus_hp"] > 0:
        player.hp = player.max_hp
    if bonuses["bonus_mp"] > 0:
        player.mp = player.max_mp
    if bonuses["start_potion"]:
        from items import Item
        potion = Item(
            name="Health Potion", item_type="consumable", rarity="common",
            stats={}, description="Restores 30 HP.",
            consumable_effect="heal", consumable_value=30,
        )
        player.inventory.add_item(potion)


# ============================================================
#  Meta Shop — terminal UI
# ============================================================

def _shop_lines(meta: MetaProgression) -> list:
    """Build the shop body lines."""
    up = meta.data.get("upgrades", {})
    pts = meta.points

    hp_lvl  = up.get("max_hp", 0)
    mp_lvl  = up.get("max_mp", 0)
    atk_lvl = up.get("atk", 0)
    pot_lvl = up.get("start_potion", 0)

    lines = []
    lines.append("")
    lines.append(fg(255, 215, 0) + bold() + "  Dungeon Points: " + str(pts) + rst())
    lines.append("")

    # 1) +5 Max HP
    can_1 = pts >= COST_HP
    c1 = fg(100, 255, 100) if can_1 else fg(100, 60, 60)
    lines.append(
        c1 + f"  [1] +5 Max HP    " + rst()
        + fg(160, 160, 180) + f"  Lv.{hp_lvl}  Cost: {COST_HP}" + rst()
    )

    can_mp = pts >= COST_MP
    c_mp = fg(100, 255, 100) if can_mp else fg(100, 60, 60)
    lines.append(c_mp + f"  [4] +8 Max MP    " + rst()
                 + fg(160, 160, 180) + f"  Lv.{mp_lvl}  Cost: {COST_MP}" + rst())

    # 2) +1 ATK
    can_2 = pts >= COST_ATK
    c2 = fg(100, 255, 100) if can_2 else fg(100, 60, 60)
    lines.append(
        c2 + f"  [2] +1 ATK       " + rst()
        + fg(160, 160, 180) + f"  Lv.{atk_lvl}  Cost: {COST_ATK}" + rst()
    )

    # 3) Starting Health Potion
    can_3 = pts >= COST_POTION and not pot_lvl
    c3 = fg(100, 255, 100) if can_3 else fg(100, 60, 60)
    status_3 = fg(100, 200, 100) + "OWNED" if pot_lvl else fg(160, 160, 180) + f"Cost: {COST_POTION}"
    lines.append(
        c3 + f"  [3] Start Potion " + rst()
        + status_3 + rst()
    )

    lines.append("")
    lines.append(fg(120, 120, 150) + "  0: Exit shop" + rst())

    # Show bonuses summary
    lines.append("")
    bonuses = meta.get_bonuses()
    parts = []
    if bonuses["bonus_hp"] > 0:
        parts.append(fg(100, 200, 100) + f"+{bonuses['bonus_hp']} HP" + rst())
    if bonuses["bonus_mp"] > 0:
        parts.append(fg(100, 160, 255) + f"+{bonuses['bonus_mp']} MP" + rst())
    if bonuses["bonus_atk"] > 0:
        parts.append(fg(200, 100, 100) + f"+{bonuses['bonus_atk']} ATK" + rst())
    if bonuses["start_potion"]:
        parts.append(fg(200, 200, 100) + "Potion" + rst())
    if parts:
        lines.append(fg(140, 140, 160) + "  Active bonuses: " + rst() + " | ".join(parts))
    else:
        lines.append(fg(80, 80, 100) + "  No bonuses purchased yet." + rst())

    return lines


def open_meta_shop(player, meta: MetaProgression):
    """Interactive meta-upgrade shop in the terminal."""
    inp = InputState()
    try:
        clear_screen()
        hide_cursor()

        while True:
            keys = inp.read()
            if "quit" in keys:
                break

            if "hotkey1" in keys:
                # +5 Max HP
                if meta.spend(COST_HP):
                    up = meta.data["upgrades"]
                    up["max_hp"] = up.get("max_hp", 0) + 1
                    meta.save()
            elif "hotkey2" in keys:
                # +1 ATK
                if meta.spend(COST_ATK):
                    up = meta.data["upgrades"]
                    up["atk"] = up.get("atk", 0) + 1
                    meta.save()
            elif "hotkey3" in keys:
                # Start potion
                up = meta.data["upgrades"]
                if not up.get("start_potion", 0) and meta.spend(COST_POTION):
                    up["start_potion"] = 1
                    meta.save()
            elif "hotkey4" in keys:
                if meta.spend(COST_MP):
                    up = meta.data["upgrades"]
                    up["max_mp"] = up.get("max_mp", 0) + 1
                    meta.save()

            body = _shop_lines(meta)

            # Render
            try:
                import shutil
                tw = shutil.get_terminal_size().columns
            except Exception:
                tw = 120

            PBG = bg(14, 14, 20)
            buf = ["\x1b[H\x1b[2J"]
            buf.append(PBG + fg(220, 180, 80) + bold() + " META PROGRESSION " + rst()
                       + "  " + fg(255, 215, 0) + f"Points: {meta.points}" + rst()
                       + " " * 20 + rst())
            buf.append(PBG + fg(60, 60, 80) + SH2 * 80 + rst())
            for line in body:
                buf.append(PBG + " " * tw + rst())
                # Pad visible length
                buf.append(" " + line)
            buf.append("")

            sys_stdout = __import__("sys").stdout
            # Pad to terminal
            padded = []
            for line in buf:
                # Simple pad
                padded.append(line)
            while len(padded) < 30:
                padded.append("")
            sys_stdout.write("\n".join(padded))
            sys_stdout.flush()
            __import__("time").sleep(0.03)
    finally:
        show_cursor()
