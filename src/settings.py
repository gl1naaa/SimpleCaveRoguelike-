import sys
import os
import json
import time

from ui import fg, bg, rst, bold, dim, SH2, DIAM, BOX_H, BOX_V, BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_LT, BOX_RT, rainbow, clear_screen, hide_cursor, show_cursor, vis_len, pad_line
from input import InputState, wait_for_any_key

try:
    import shutil
    TERM_W = max(shutil.get_terminal_size().columns, 120)
    TERM_H = max(shutil.get_terminal_size().lines, 40)
except Exception:
    TERM_W, TERM_H = 120, 40

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _pad_line(line, width=TERM_W):
    return pad_line(line, width)


def _center(text, width):
    return text.center(width)


def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def _default_config():
    try:
        from config import _DEFAULTS
        return json.loads(json.dumps(_DEFAULTS))
    except Exception:
        pass
    cfg = _load_config()
    if cfg:
        return cfg
    return {}


def _flatten(data, prefix=""):
    items = []
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.extend(_flatten(v, key))
        else:
            items.append((key, v))
    return items


def _get_nested(data, path):
    parts = path.split(".")
    cur = data
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur


def _set_nested(data, path, value):
    parts = path.split(".")
    cur = data
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _format_value(val):
    if isinstance(val, bool):
        return "ON" if val else "OFF"
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return f"{val:.2f}"
    if isinstance(val, list):
        return str(val)
    return str(val)


def _is_togglable(val):
    return isinstance(val, bool)


def _is_numeric(val):
    return isinstance(val, (int, float)) and not isinstance(val, bool)


CATEGORY_ICONS = {
    "display": "[Screen]",
    "map": "[Dungeon]",
    "player": "[Hero]",
    "combat": "[Fight]",
    "movement": "[Speed]",
    "inventory": "[Pack]",
    "skills": "[Abilities]",
    "rarity": "[Loot]",
    "weapons": "[Arms]",
    "armor": "[Armor]",
    "helmet_types": "[Helm]",
    "chest_types": "[Plate]",
    "legs_types": "[Legs]",
    "boots_types": "[Boots]",
    "gloves_types": "[Hands]",
    "necklace_types": "[Neck]",
    "cape_types": "[Back]",
    "rooms": "[Rooms]",
    "monster_scaling": "[Monsters]",
    "monster_unlocks": "[Unlock]",
    "monsters_per_room": "[Density]",
    "traps_per_room": "[Traps]",
    "extra_chests_per_floor": "[Chests]",
    "npc_enemies": "[Rivals]",
    "npc_ai": "[AI Brain]",
    "party": "[Allies]",
    "fov": "[Vision]",
    "chest_loot": "[Loot Table]",
    "unique_items": "[Uniques]",
    "consumable_value": "[Potions]",
    "item_type_weights": "[Drop Rates]",
    "city": "[City]",
    "gameplay": "[Rules]",
    "colors": "[Palette]",
    "display_symbols": "[Glyphs]",
    "player_classes": "[Classes]",
    "skills_data": "[Skill Stats]",
    "boss_scaling": "[Bosses]",
    "monster_base_stats": "[Mob Stats]",
    "starting_weapons": "[Starter]",
}


def _get_category_label(cat):
    return CATEGORY_ICONS.get(cat, f"[{cat}]")


def _get_category_description(cat):
    descs = {
        "display": "Screen resolution, FPS, font",
        "map": "Dungeon generation parameters",
        "player": "Base stats, XP, leveling",
        "combat": "Damage, crits, gold drops",
        "movement": "Cooldowns and tick rates",
        "inventory": "Bag size and grid layout",
        "skills": "Key bindings",
        "rarity": "Drop weights and stat multipliers",
        "weapons": "Weapon base stats per type",
        "armor": "Armor defense values",
        "helmet_types": "Helmet stat bonuses",
        "chest_types": "Chest armor bonuses",
        "legs_types": "Leg armor bonuses",
        "boots_types": "Boot speed/defense",
        "gloves_types": "Glove attack bonuses",
        "necklace_types": "Necklace stat bonuses",
        "cape_types": "Cape special bonuses",
        "rooms": "Room type spawn weights",
        "monster_scaling": "HP/ATK/DEF scaling per floor",
        "monster_unlocks": "When new monsters appear",
        "monsters_per_room": "Enemy density",
        "traps_per_room": "Trap room danger",
        "extra_chests_per_floor": "Bonus chest spawns",
        "npc_enemies": "Player-class NPC enemies",
        "npc_ai": "NPC behavior tuning",
        "party": "Ally system limits",
        "fov": "Field of view radius and rays",
        "chest_loot": "Chest item/gold rewards",
        "unique_items": "Unique item drop chance",
        "consumable_value": "Potion healing amounts",
        "item_type_weights": "Loot table distribution",
        "city": "Shop pricing and layout",
        "gameplay": "Total floors, victory condition",
        "colors": "All UI color RGB values",
        "display_symbols": "Map tile characters",
        "player_classes": "Class base stats",
        "skills_data": "All 30 skill stats",
        "boss_scaling": "Boss phase thresholds",
        "monster_base_stats": "Monster base values",
        "starting_weapons": "Level 1 starter weapons",
    }
    return descs.get(cat, "")


def show_settings():
    """Show the full settings menu. Returns when user presses ESC or selects 'back'."""
    cfg = _load_config()
    if not cfg:
        cfg = _default_config()
    original_cfg = json.loads(json.dumps(cfg))

    inp = InputState()
    t = 0.0

    categories = [k for k in cfg.keys() if not k.startswith("_")]
    cat_idx = 0
    item_idx = 0
    editing = False
    scroll_offset = 0

    max_visible = TERM_H - 10

    def _get_items(cat):
        val = cfg.get(cat)
        if isinstance(val, dict):
            return [(f"{k}", v) for k, v in val.items() if not k.startswith("_")]
        return []

    while True:
        keys = inp.read()
        if "quit" in keys:
            if editing:
                editing = False
            else:
                _save_config(cfg)
                return

        if not editing:
            if "up" in keys:
                cat_idx = (cat_idx - 1) % len(categories)
                item_idx = 0
                scroll_offset = 0
            if "down" in keys:
                cat_idx = (cat_idx + 1) % len(categories)
                item_idx = 0
                scroll_offset = 0
            if "action" in keys:
                editing = True
                item_idx = 0
                scroll_offset = 0
        else:
            cat = categories[cat_idx]
            items = _get_items(cat)

            if "up" in keys:
                item_idx = (item_idx - 1) % max(1, len(items))
                if item_idx < scroll_offset:
                    scroll_offset = item_idx
                if item_idx >= scroll_offset + max_visible:
                    scroll_offset = item_idx - max_visible + 1
            if "down" in keys:
                item_idx = (item_idx + 1) % max(1, len(items))
                if item_idx >= scroll_offset + max_visible:
                    scroll_offset = item_idx - max_visible + 1
                if item_idx < scroll_offset:
                    scroll_offset = item_idx

            if "action" in keys:
                if items:
                    key, val = items[item_idx]
                    full_key = f"{cat}.{key}"
                    if _is_togglable(val):
                        _set_nested(cfg, full_key, not val)
                    elif _is_numeric(val):
                        pass
                    else:
                        pass

            if "left" in keys and items:
                key, val = items[item_idx]
                full_key = f"{cat}.{key}"
                if _is_numeric(val):
                    if isinstance(val, int):
                        step = 1
                        if val > 100:
                            step = 10
                        elif val > 10:
                            step = 5
                        _set_nested(cfg, full_key, max(0, val - step))
                    else:
                        step = 0.05
                        if val > 1.0:
                            step = 0.1
                        elif val > 10.0:
                            step = 1.0
                        _set_nested(cfg, full_key, max(0.0, round(val - step, 2)))
                elif _is_togglable(val):
                    _set_nested(cfg, full_key, not val)

            if "right" in keys and items:
                key, val = items[item_idx]
                full_key = f"{cat}.{key}"
                if _is_numeric(val):
                    if isinstance(val, int):
                        step = 1
                        if val >= 100:
                            step = 10
                        elif val >= 10:
                            step = 5
                        _set_nested(cfg, full_key, val + step)
                    else:
                        step = 0.05
                        if val >= 1.0:
                            step = 0.1
                        elif val >= 10.0:
                            step = 1.0
                        _set_nested(cfg, full_key, round(val + step, 2))
                elif _is_togglable(val):
                    _set_nested(cfg, full_key, not val)

        cat = categories[cat_idx]
        items = _get_items(cat)
        cat_label = _get_category_label(cat)
        cat_desc = _get_category_description(cat)

        buf = ["\x1b[H\x1b[2J"]
        c = bg(14, 14, 20)

        buf.append(c + fg(60, 60, 80) + SH2 * TERM_W + rst())
        buf.append(c + ' ' * TERM_W + rst())
        title_line = c + '  ' + fg(255, 215, 0) + bold() + _center('SETTINGS', TERM_W - 4) + rst()
        buf.append(_pad_line(title_line))
        sub_line = c + '  ' + fg(120, 120, 150) + dim() + _center('Configure every aspect of the game', TERM_W - 4) + rst()
        buf.append(_pad_line(sub_line))
        buf.append(c + ' ' * TERM_W + rst())
        buf.append(c + fg(60, 60, 80) + '  ' + BOX_TL + BOX_H * (TERM_W - 4) + BOX_TR + rst())
        buf.append(c + ' ' * TERM_W + rst())

        cat_line = c + '  ' + fg(100, 200, 230) + bold() + f'{cat_label}' + rst() + fg(80, 80, 100) + f'  {cat_desc}' + rst()
        buf.append(_pad_line(cat_line))

        cat_nav = c + '  '
        for i, cn in enumerate(categories):
            if i == cat_idx:
                cat_nav += fg(255, 215, 0) + bold() + f' {cn[:8]} ' + rst()
            else:
                cat_nav += fg(50, 50, 70) + f' {cn[:8]} ' + rst()
        buf.append(_pad_line(cat_nav))
        buf.append(c + ' ' * TERM_W + rst())

        visible_items = items[scroll_offset:scroll_offset + max_visible]

        if not items:
            buf.append(_pad_line(c + '  ' + fg(80, 80, 100) + 'No configurable parameters in this category.' + rst()))
        else:
            for vi, (key, val) in enumerate(visible_items):
                gi = scroll_offset + vi
                is_sel = (gi == item_idx and editing)
                is_hl = (gi == item_idx and not editing)

                formatted = _format_value(val)
                max_key_w = 28
                key_display = key[:max_key_w].ljust(max_key_w)

                if is_sel:
                    if _is_numeric(val):
                        arrow_l = fg(255, 215, 0) + '<<' + rst()
                        arrow_r = fg(255, 215, 0) + '>>' + rst()
                        val_str = fg(255, 255, 100) + bold() + f' {formatted:>10s} ' + rst()
                    elif _is_togglable(val):
                        arrow_l = fg(255, 215, 0) + '<' + rst()
                        arrow_r = fg(255, 215, 0) + '>' + rst()
                        color = fg(100, 255, 100) if val else fg(255, 80, 80)
                        val_str = color + bold() + f' {formatted:>10s} ' + rst()
                    else:
                        arrow_l = ' '
                        arrow_r = ' '
                        val_str = fg(180, 180, 200) + f' {formatted:>10s} ' + rst()
                    line = (c + '  ' + rst()
                            + fg(255, 215, 0) + DIAM + ' '
                            + fg(200, 200, 220) + key_display + rst()
                            + arrow_l + val_str + arrow_r)
                elif is_hl:
                    line = (c + '  ' + rst()
                            + fg(80, 80, 100) + '> '
                            + fg(180, 180, 200) + key_display + rst()
                            + fg(140, 140, 160) + f' {formatted:>10s} ' + rst())
                else:
                    line = (c + '     '
                            + fg(80, 80, 100) + key_display + rst()
                            + fg(60, 60, 70) + f' {formatted:>10s} ' + rst())

                buf.append(_pad_line(line))

            if len(items) > max_visible:
                total_h = max_visible
                scroll_h = max(1, int(total_h * max_visible / len(items)))
                scroll_pos = int((item_idx / max(1, len(items) - 1)) * (total_h - scroll_h))
                scroll_bar = c + '     ' + fg(40, 40, 50) + '|' + rst()
                for si in range(total_h):
                    if scroll_pos <= si < scroll_pos + scroll_h:
                        scroll_bar_line = c + '     ' + fg(120, 120, 150) + '|' + rst()
                    else:
                        scroll_bar_line = c + '     ' + fg(40, 40, 50) + '|' + rst()
                    if vi + si < len(buf):
                        pass

        used = len(buf)
        while used < TERM_H - 4:
            buf.append(c + ' ' * TERM_W + rst())
            used += 1

        buf.append(c + ' ' * TERM_W + rst())
        if editing:
            foot_text = 'UP/DOWN: select  |  LEFT/RIGHT: adjust  |  Space: toggle  |  ESC: back to categories'
        else:
            foot_text = 'UP/DOWN: category  |  Space: edit  |  ESC: save & exit'
        foot_line = c + '  ' + fg(80, 80, 100) + dim() + _center(foot_text, TERM_W - 4) + rst()
        buf.append(_pad_line(foot_line))
        buf.append(c + fg(60, 60, 80) + SH2 * TERM_W + rst())

        sys.stdout.write('\n'.join(buf))
        sys.stdout.flush()
        t += 0.05
        time.sleep(0.03)


if __name__ == "__main__":
    show_settings()
