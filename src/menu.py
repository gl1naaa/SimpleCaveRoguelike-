import sys
import time
import msvcrt
from ui import fg, bg, rst, bold, dim, BLK, SH2, DIAM, HEART, DSTAR, BOX_H, BOX_V, BOX_TL, BOX_TR, BOX_BL, BOX_BR, BOX_LT, BOX_RT, rainbow, clear_screen, hide_cursor, show_cursor, vis_len, pad_line
from input import InputState, wait_for_any_key
from config import CLASSES

try:
    import shutil
    TERM_W = max(shutil.get_terminal_size().columns, 120)
    TERM_H = max(shutil.get_terminal_size().lines, 40)
except Exception:
    TERM_W, TERM_H = 120, 40


def _center(text, width):
    return text.center(width)

def _pad_line(line, width=TERM_W):
    return pad_line(line, width)

def _draw_frame(title, subtitle, body_lines, footer=None):
    """Draw a consistent frame for all menu screens."""
    buf = ["\x1b[H\x1b[2J"]
    c = bg(14, 14, 20)

    # Top decorative bar
    buf.append(c + fg(60, 60, 80) + SH2 * TERM_W + rst())

    # Title
    buf.append(c + ' ' * TERM_W + rst())
    title_line = c + '  ' + fg(255, 215, 0) + bold() + _center(title, TERM_W - 4) + rst()
    buf.append(_pad_line(title_line))
    buf.append(c + ' ' * TERM_W + rst())

    # Subtitle
    if subtitle:
        sub_line = c + '  ' + fg(120, 120, 150) + dim() + _center(subtitle, TERM_W - 4) + rst()
        buf.append(_pad_line(sub_line))
        buf.append(c + ' ' * TERM_W + rst())

    # Separator
    buf.append(c + fg(60, 60, 80) + '  ' + BOX_TL + BOX_H * (TERM_W - 4) + BOX_TR + rst())
    buf.append(c + ' ' * TERM_W + rst())

    # Body
    for line in body_lines:
        buf.append(_pad_line(c + '  ' + rst() + line))

    # Fill to footer area
    used = 7 + len(body_lines)
    target = TERM_H - 4 if footer else TERM_H - 3
    while used < target:
        buf.append(_pad_line(c + ' ' * TERM_W))
        used += 1

    # Footer
    if footer:
        buf.append(c + ' ' * TERM_W + rst())
        foot_line = c + '  ' + fg(80, 80, 100) + dim() + _center(footer, TERM_W - 4) + rst()
        buf.append(_pad_line(foot_line))

    # Bottom bar
    buf.append(c + fg(60, 60, 80) + SH2 * TERM_W + rst())

    return buf


# ============================================================
#  Name Input
# ============================================================

def show_name_input() -> str:
    """Show name input screen, return entered name."""
    show_cursor()
    # Clear any stuck keys from previous screen
    _drain_keys()

    body = []
    body.append('')
    body.append(fg(180, 180, 200) + '  Give your hero a name. It is only cosmetic.' + rst())
    body.append(fg(120, 120, 150) + '  Type a name and press Enter to continue, or leave it blank.' + rst())
    body.append('')
    body.append('')

    # Input box
    box_w = 40
    top = BOX_TL + BOX_H * (box_w - 2) + BOX_TR
    bot = BOX_BL + BOX_H * (box_w - 2) + BOX_BR
    body.append(fg(80, 80, 100) + '  ' + top + rst())
    body.append(fg(80, 80, 100) + '  ' + BOX_V + rst() + fg(80, 80, 100) + BOX_V + rst())
    body.append(fg(80, 80, 100) + '  ' + bot + rst())
    body.append('')
    body.append('')
    body.append(fg(120, 120, 150) + '  Suggestions: Adventurer, Shadow, Nova, Blaze, Storm' + rst())
    body.append(fg(120, 120, 150) + '  Blank name = Adventurer' + rst())

    buf = _draw_frame('NAME YOUR HERO', 'Who dares descend?', body)

    # Position cursor inside the box (line 9 from top of screen, after "  " + BOX_V)
    # We need to place cursor at the right position
    # The box inner line is at buf line index ~8 (0-based), which is screen line ~10
    sys.stdout.write('\n'.join(buf))
    sys.stdout.flush()
    time.sleep(0.1)

    # Use input() for reliable text entry
    try:
        # Drain any buffered keystrokes from previous screens
        while msvcrt.kbhit():
            msvcrt.getch()
        # Move cursor to the input box position and clear it
        sys.stdout.write(f'\x1b[11;7H{fg(255, 255, 100)}' + ' ' * (box_w - 2) + rst())
        sys.stdout.write(f'\x1b[11;7H')
        sys.stdout.flush()
        name = input(f'{fg(255, 255, 100)}> {rst()}')
    except (EOFError, KeyboardInterrupt):
        name = ''

    hide_cursor()
    return name.strip() if name.strip() else 'Adventurer'


def _drain_keys():
    """Clear any stuck key states from previous screen."""
    import ctypes
    if not hasattr(ctypes, 'windll'):
        return
    user32 = ctypes.windll.user32
    # Wait for all keys to be released
    for _ in range(10):
        any_pressed = False
        for vk in [0x0D, 0x20, 0x1B, 0x41, 0x42, 0x43, 0x44, 0x45, 0x53, 0x57,
                    0x25, 0x26, 0x27, 0x28, 0x5A, 0x58, 0x56, 0x42]:
            if user32.GetAsyncKeyState(vk) & 0x8000:
                any_pressed = True
                break
        if not any_pressed:
            break
        time.sleep(0.05)
    time.sleep(0.1)


# ============================================================
#  Seed Input
# ============================================================

def show_seed_input() -> str:
    """Show seed input screen.  Empty = random seed.  Returns seed string or empty."""
    show_cursor()
    _drain_keys()

    body = []
    body.append('')
    body.append(fg(180, 180, 200) + '  Optional: type a seed to replay the same dungeon.' + rst())
    body.append(fg(120, 120, 150) + '  Leave it blank for a fresh random world.' + rst())
    body.append('')
    body.append('')

    box_w = 40
    top = BOX_TL + BOX_H * (box_w - 2) + BOX_TR
    bot = BOX_BL + BOX_H * (box_w - 2) + BOX_BR
    body.append(fg(80, 80, 100) + '  ' + top + rst())
    body.append(fg(80, 80, 100) + '  ' + BOX_V + rst() + fg(80, 80, 100) + BOX_V + rst())
    body.append(fg(80, 80, 100) + '  ' + bot + rst())
    body.append('')
    body.append('')
    body.append(fg(120, 120, 150) + '  Press Enter on an empty line for a random seed.' + rst())

    buf = _draw_frame('SEED', 'Deterministic dungeon generation', body)

    sys.stdout.write('\n'.join(buf))
    sys.stdout.flush()
    time.sleep(0.1)

    try:
        while msvcrt.kbhit():
            msvcrt.getch()
        sys.stdout.write(f'\x1b[11;7H{fg(255, 255, 100)}' + ' ' * (box_w - 2) + rst())
        sys.stdout.write(f'\x1b[11;7H')
        sys.stdout.flush()
        seed = input(f'{fg(255, 255, 100)}> {rst()}')
    except (EOFError, KeyboardInterrupt):
        seed = ''

    hide_cursor()
    return seed.strip()


# ============================================================
#  ASCII Art Title
# ============================================================

TITLE_ART_2 = [
    r"  _____ _____        _____ ______  _____ _____  ",
    r" /  ___|_   _|      /  ___| ___ \/  __ \_   _/",
    r" \ `--.  | | ______ \ `--.| |_/ /| /  \ | |   ",
    r"  `--. \ | ||______|`--. \    / | |    | |   ",
    r" /\__/ /_| |       /\__/ / |\ \ | \__/\ | |   ",
    r" \____/ \___/       \____/\_| \_|\_____/ \_/   ",
]

# ============================================================
#  Title Screen
# ============================================================

def show_title() -> str:
    """Beginner-friendly title screen with a clear first step and hints."""
    inp = InputState()
    t = 0.0
    selected = 0
    options = ["START A NEW RUN", "HOW TO PLAY", "SETTINGS", "QUIT"]
    option_descs = [
        "Create a hero and enter the dungeon",
        "Learn movement, combat, loot and the city",
        "Adjust display and gameplay options",
        "Return to desktop",
    ]

    while True:
        keys = inp.read()
        if "quit" in keys:
            return "quit"

        if "down" in keys:
            selected = (selected + 1) % len(options)
        if "up" in keys:
            selected = (selected - 1) % len(options)
        if "action" in keys:
            return ["new_game", "controls", "settings", "quit"][selected]

        buf = ["\x1b[H\x1b[2J"]
        c = bg(14, 14, 20)

        # Top bar
        buf.append(c + fg(60, 60, 80) + SH2 * TERM_W + rst())

        # Title art with rainbow
        for i, line in enumerate(TITLE_ART_2):
            colored = rainbow(line, t + i * 0.1)
            buf.append(c + ' ' * max(0, (TERM_W - 50) // 2) + colored + rst())

        # Subtitle and onboarding message
        buf.append('')
        sub = c + fg(120, 170, 210) + dim() + _center('A terminal adventure for your first run', TERM_W) + rst()
        buf.append(_pad_line(sub))
        buf.append('')

        # Decorative separator
        sep = c + fg(60, 60, 80) + '  ' + BOX_TL + BOX_H * (TERM_W - 4) + BOX_TR + rst()
        buf.append(_pad_line(sep))
        buf.append('')

        intro = c + fg(210, 210, 220) + bold() + 'YOUR GOAL  ' + rst() + \
                c + fg(150, 155, 175) + 'Explore 10 floors, collect random loot, reach the city, and defeat the final boss.' + rst()
        buf.append(_pad_line(intro))
        hint = c + fg(100, 220, 180) + 'NEW PLAYER TIP  ' + rst() + \
               c + fg(150, 155, 175) + 'Start with HOW TO PLAY if this is your first visit.' + rst()
        buf.append(_pad_line(hint))
        buf.append(c + ' ' * TERM_W + rst())

        # Menu options
        for i, opt in enumerate(options):
            is_sel = (i == selected)
            if is_sel:
                marker = c + fg(255, 215, 0) + bold() + f'  {DIAM} {opt}' + rst()
                desc = c + fg(180, 160, 100) + f'    {option_descs[i]}' + rst()
            else:
                marker = c + fg(80, 80, 100) + f'    {opt}' + rst()
                desc = c + fg(60, 60, 80) + f'    {option_descs[i]}' + rst()
            buf.append(_pad_line(marker))
            buf.append(_pad_line(desc))
            buf.append('')

        # Persistent progress summary (read-only, never blocks starting a run)
        try:
            from meta import MetaProgression
            points = MetaProgression().points
            progress = f'Persistent progress: {points} Dungeon Points  |  Upgrades carry into new runs'
        except Exception:
            progress = 'Persistent progress is saved automatically after each run.'
        buf.append(_pad_line(c + ' ' + fg(150, 130, 80) + progress + rst()))
        buf.append('')

        # Fill
        used = 11 + len(TITLE_ART_2) + 3 + len(options) * 3
        while used < TERM_H - 3:
            buf.append(c + ' ' * TERM_W + rst())
            used += 1

        # Footer
        foot = c + fg(80, 80, 100) + dim() + _center('WASD / Arrows: move  |  Space: choose  |  ESC: back', TERM_W) + rst()
        buf.append(_pad_line(foot))
        buf.append(c + fg(60, 60, 80) + SH2 * TERM_W + rst())

        sys.stdout.write('\n'.join(buf))
        sys.stdout.flush()
        t += 0.05
        time.sleep(0.03)


# ============================================================
#  Class Selection
# ============================================================

def show_class_select() -> str:
    """Show class selection screen, return chosen class name."""
    # Drain any lingering key presses from name input
    while msvcrt.kbhit():
        msvcrt.getch()
    time.sleep(0.15)
    inp = InputState()
    selected = 0
    class_names = list(CLASSES.keys())
    t = 0.0

    class_art = {
        "swordsman": [
            "    /\\    ",
            "   /  \\   ",
            "  / == \\  ",
            " |  ||  | ",
            " |  ||  | ",
            "  \\    /  ",
            "   \\  /   ",
            "    O     ",
        ],
        "archer": [
            "      |   ",
            "     /|   ",
            "    / |   ",
            "   /  |   ",
            "  ( o |   ",
            "   \\  |   ",
            "    \\ |   ",
            "     O    ",
        ],
        "mage": [
            "    *     ",
            "   /|\\    ",
            "  / | \\   ",
            " /  |  \\  ",
            "   /|\\    ",
            "  / | \\   ",
            "   / \\    ",
            "    O     ",
        ],
        "summoner": [
            "  (o_o)   ",
            "   /|\\    ",
            "  / | \\   ",
            " /  |  \\  ",
            "   /|\\    ",
            "  / | \\   ",
            "   / \\    ",
            "  /   \\   ",
        ],
        "healer": [
            "    +     ",
            "   /|\\    ",
            "  / | \\   ",
            "   /|\\    ",
            "   /|\\    ",
            "  / | \\   ",
            "   / \\    ",
            "    O     ",
        ],
        "rogue": [
            "   /\\     ",
            "  /  \\    ",
            " / <> \\   ",
            "  |  |    ",
            "  /\\ /\\   ",
            " /  V  \\  ",
            "    O     ",
            "   / \\    ",
        ],
    }

    class_stats = {
        "swordsman": [("ATK", "★★★★"), ("DEF", "★★★"), ("SPD", "★★"), ("MAG", "★")],
        "archer":    [("ATK", "★★★"), ("DEF", "★★"), ("SPD", "★★★★"), ("MAG", "★")],
        "mage":      [("ATK", "★★"), ("DEF", "★"), ("SPD", "★★"), ("MAG", "★★★★")],
        "summoner":  [("ATK", "★★★"), ("DEF", "★★★"), ("SPD", "★★★"), ("MAG", "★★★")],
        "healer":    [("ATK", "★"), ("DEF", "★★"), ("SPD", "★"), ("MAG", "★★★★")],
        "rogue":     [("ATK", "★★★"), ("DEF", "★"), ("SPD", "★★★★"), ("MAG", "★")],
    }

    skill_names = {
        "swordsman": ["Cleave", "Whirlwind", "Shield Bash", "War Cry", "Berserk"],
        "archer":    ["Quick Shot", "Volley", "Poison Arrow", "Frost Arrow", "Arrow Rain"],
        "mage":      ["Fireball", "Chain Lightning", "Blizzard", "Mana Shield", "Blink"],
        "summoner":  ["Raise Dead", "Spirit Drain", "Fire Nova", "Bone Wall", "Army of Dead"],
        "healer":    ["Holy Light", "Greater Heal", "Radiance", "Blessing", "Divine Surge"],
        "rogue":     ["Backstab", "Shadow Strike", "Fan of Knives", "Poison Blade", "Evasion"],
    }

    while True:
        keys = inp.read()
        if "quit" in keys:
            return ""

        if "left" in keys:
            selected = (selected - 1) % len(class_names)
            t = 0.0
        if "right" in keys:
            selected = (selected + 1) % len(class_names)
            t = 0.0
        if "action" in keys:
            return class_names[selected]

        buf = ["\x1b[H\x1b[2J"]
        c = bg(14, 14, 20)

        # Top bar
        buf.append(c + fg(60, 60, 80) + SH2 * TERM_W + rst())
        buf.append('')
        title_line = c + '  ' + fg(255, 215, 0) + bold() + _center('CHOOSE YOUR CLASS', TERM_W - 4) + rst()
        buf.append(_pad_line(title_line))
        sub_line = c + '  ' + fg(120, 120, 150) + dim() + _center('Browse a class with LEFT/RIGHT  |  Space selects it  |  ESC goes back', TERM_W - 4) + rst()
        buf.append(_pad_line(sub_line))
        buf.append('')
        buf.append(c + fg(60, 60, 80) + '  ' + BOX_TL + BOX_H * (TERM_W - 4) + BOX_TR + rst())
        buf.append('')

        # Class cards - horizontal layout
        card_w = 18
        gap = 1
        total_w = len(class_names) * card_w + (len(class_names) - 1) * gap
        start_x = (TERM_W - total_w) // 2

        # Build each card as lines, then interleave
        card_lines = []
        for i, cname in enumerate(class_names):
            is_sel = (i == selected)
            lines = []
            cls = CLASSES[cname]
            art = class_art.get(cname, [""] * 8)
            stats = class_stats.get(cname, [])
            skls = skill_names.get(cname, [])

            if is_sel:
                bc = fg(255, 215, 0)
                tc = fg(255, 215, 0) + bold()
                ac = fg(100, 255, 100)
                sc = fg(200, 200, 100)
            else:
                bc = fg(50, 50, 70)
                tc = fg(80, 80, 100)
                ac = fg(50, 70, 50)
                sc = fg(70, 70, 80)

            # Card: 12 lines total
            top = BOX_TL + BOX_H * (card_w - 2) + BOX_TR
            lines.append(bc + top + rst())

            # Name
            nm = cname.upper().center(card_w - 2)
            lines.append(bc + BOX_V + rst() + tc + nm + rst() + bc + BOX_V + rst())

            # Separator
            lines.append(bc + BOX_LT + BOX_H * (card_w - 2) + BOX_RT + rst())

            # Description
            desc = cls["desc"].center(card_w - 2)[:card_w - 2]
            lines.append(bc + BOX_V + rst() + fg(140, 140, 160) + desc + rst() + bc + BOX_V + rst())

            # Weapon
            wpn = f"Weapon: {cls['weapon'].upper()}".center(card_w - 2)
            lines.append(bc + BOX_V + rst() + sc + wpn + rst() + bc + BOX_V + rst())

            # Stats
            for stat_name, stars in stats:
                txt = f"  {stat_name}: {stars}".ljust(card_w - 2)
                lines.append(bc + BOX_V + rst() + ac + txt + rst() + bc + BOX_V + rst())

            # Art
            for j in range(4):
                if j < len(art):
                    padded = art[j].center(card_w - 2)[:card_w - 2]
                else:
                    padded = " " * (card_w - 2)
                lines.append(bc + BOX_V + rst() + ac + padded + rst() + bc + BOX_V + rst())

            # Bottom
            bot = BOX_BL + BOX_H * (card_w - 2) + BOX_BR
            lines.append(bc + bot + rst())

            card_lines.append(lines)

        # Interleave cards line by line
        max_lines = max(len(cl) for cl in card_lines)
        for row in range(max_lines):
            parts = []
            for i, cl in enumerate(card_lines):
                if row < len(cl):
                    parts.append(cl[row])
                else:
                    parts.append(' ' * card_w)
            # Calculate indent
            line_str = c + ' ' * start_x + rst().join(parts)
            buf.append(_pad_line(c + ' ' * start_x + ''.join(parts)))

        buf.append('')

        # Skills preview
        sel_class = class_names[selected]
        sk_line = c + '  ' + fg(120, 170, 210) + bold() + f'Skills for {sel_class.upper()}:' + rst()
        buf.append(_pad_line(sk_line))
        keys_list = ["Z", "X", "C", "V", "B"]
        skls = skill_names.get(sel_class, [])
        for j, sk in enumerate(skls):
            sk_entry = c + f'    {fg(80, 80, 100)}{keys_list[j]}:{rst()} {fg(180, 180, 200)}{sk}{rst()}'
            buf.append(_pad_line(sk_entry))

        class_tips = {
            "swordsman": "Beginner-friendly: high HP and forgiving melee combat.",
            "archer": "Keep distance and use corridors to control enemies.",
            "mage": "Powerful spells, but watch your MP carefully.",
            "summoner": "Let summons distract enemies while you cast.",
            "healer": "Support-only class: heal and buff your random party.",
            "rogue": "Fast critical strikes; avoid standing in open fights.",
        }
        buf.append(_pad_line(c + '  ' + fg(100, 220, 180) + 'STARTER TIP: ' + rst()
                             + fg(170, 175, 190) + class_tips.get(sel_class, '') + rst()))

        # Fill to bottom
        used = len(buf) + 1
        while used < TERM_H - 2:
            buf.append(c + ' ' * TERM_W + rst())
            used += 1

        foot = c + fg(80, 80, 100) + dim() + _center('LEFT/RIGHT: browse  |  Space: confirm  |  ESC: back', TERM_W) + rst()
        buf.append(_pad_line(foot))
        buf.append(c + fg(60, 60, 80) + SH2 * TERM_W + rst())

        sys.stdout.write('\n'.join(buf))
        sys.stdout.flush()
        t += 0.05
        time.sleep(0.03)


# ============================================================
#  Controls Screen
# ============================================================

def show_controls():
    """Show controls help."""
    inp = InputState()
    t = 0.0

    while True:
        keys = inp.read()
        if "quit" in keys or "action" in keys:
            return

        controls = [
            ("WASD / Arrows", "Move through the dungeon"),
            ("SPACE",         "Interact, open chests, descend and buy"),
            ("Z X C V B",     "Use skills (5 slots)"),
            ("E",             "Open inventory"),
            ("DEL",           "Delete item from inventory"),
            ("TAB",           "Inspect nearby tiles and enemies"),
            ("ESC",           "Leave the current screen / run"),
        ]

        body = []
        body.append('')
        body.append('')
        for key, desc in controls:
            body.append(fg(255, 215, 0) + f'    {key:<20s}' + rst() + fg(180, 180, 200) + desc + rst())
            body.append('')
        body.append('')
        body.append(fg(120, 120, 150) + '    Combat: walk into enemies to attack' + rst())
        body.append(fg(120, 120, 150) + '    Find stairs (>) to go deeper' + rst())
        body.append(fg(120, 120, 150) + '    Open chests (=) for loot' + rst())
        body.append(fg(100, 220, 180) + '    City tip: visit the tavern ($) to hire or dismiss allies' + rst())
        body.append(fg(100, 220, 180) + '    Healers only support; damage classes attack by moving into range' + rst())

        buf = _draw_frame('CONTROLS', 'Master the dungeon', body,
                          footer='Space or ESC: go back')

        sys.stdout.write('\n'.join(buf))
        sys.stdout.flush()
        t += 0.05
        time.sleep(0.03)


# ============================================================
#  Death Screen
# ============================================================

def show_death(floor: int, turns: int, killed: int, player_name: str, class_name: str, stats=None):
    """Show death screen.  *stats* is an optional RunTracker.to_dict() for the extended view."""
    from run_stats import RunTracker

    inp = InputState()
    t = 0.0
    time.sleep(0.3)

    # Pre-fetch best record once
    best = RunTracker.get_best_record()

    while True:
        keys = inp.read()
        if "quit" in keys or "action" in keys:
            return

        body = []
        body.append('')

        # Death banner
        death_top = bg(40, 10, 10) + fg(200, 50, 50) + '  ' + BLK * 48 + rst()
        death_mid = bg(40, 10, 10) + fg(200, 50, 50) + '  ' + BLK + rst() + bg(40, 10, 10) + fg(200, 50, 50) + ' ' * 18 + 'Y O U   D I E D' + ' ' * 17 + BLK + rst()
        death_bot = bg(40, 10, 10) + fg(200, 50, 50) + '  ' + BLK * 48 + rst()

        body.append(death_top)
        body.append(death_mid)
        body.append(death_bot)
        body.append('')
        body.append('')

        if stats:
            # ---- Extended death screen ----
            elapsed_str = stats.get("elapsed_formatted", "?")
            cause = stats.get("cause_of_death", "Unknown")
            dmg_dealt = stats.get("damage_dealt", 0)
            dmg_taken = stats.get("damage_taken", 0)
            total_kills = stats.get("kills", killed)
            top_skills = stats.get("top_skills", [])
            unique_items = stats.get("unique_items", [])

            lines = [
                (fg(160, 160, 180) + '  Player:',    fg(255, 255, 100) + bold() + f' {player_name}' + rst()),
                (fg(160, 160, 180) + '  Class:',      fg(255, 255, 100) + f' {class_name}' + rst()),
                (fg(160, 160, 180) + '  Floor:',      fg(220, 190, 80) + f' {floor}' + rst()),
                (fg(160, 160, 180) + '  Time:',       fg(220, 190, 80) + f' {elapsed_str}' + rst()),
                (fg(160, 160, 180) + '  Cause:',      fg(200, 80, 80) + f' {cause}' + rst()),
                (fg(160, 160, 180) + '  Turns:',      fg(220, 190, 80) + f' {turns}' + rst()),
                (fg(160, 160, 180) + '  Dealt:',      fg(255, 150, 150) + f' {dmg_dealt}' + rst()),
                (fg(160, 160, 180) + '  Taken:',      fg(255, 100, 100) + f' {dmg_taken}' + rst()),
                (fg(160, 160, 180) + '  Kills:',      fg(220, 190, 80) + f' {total_kills}' + rst()),
            ]
            for label, val in lines:
                body.append(f'    {label}{val}')

            # Top 3 skills
            if top_skills:
                body.append('')
                body.append(f'    {fg(160, 160, 180)}  Top skills:{rst()}')
                for sk_name, sk_count in top_skills[:3]:
                    body.append(f'      {fg(100, 200, 100)}{sk_name}{rst()} x{sk_count}')

            # Unique items
            if unique_items:
                body.append('')
                body.append(f'    {fg(160, 160, 180)}  Loot ({len(unique_items)} unique):{rst()}')
                shown = unique_items[:5]
                body.append(f'      {fg(220, 190, 80)}{", ".join(shown)}{rst()}')
                if len(unique_items) > 5:
                    body.append(f'      {fg(120, 120, 150)}...and {len(unique_items) - 5} more{rst()}')

            # Best record
            if best and best.get("floor", 0) > 0:
                body.append('')
                best_floor = best.get("floor", "?")
                best_time = best.get("elapsed_formatted", "?")
                body.append(f'    {fg(100, 180, 255)}  Best record: Floor {best_floor} ({best_time}){rst()}')
        else:
            # ---- Legacy death screen (no stats) ----
            legacy_stats = [
                (fg(160, 160, 180) + '  Player:', fg(255, 255, 100) + bold() + f' {player_name}' + rst()),
                (fg(160, 160, 180) + '  Class:',  fg(255, 255, 100) + f' {class_name}' + rst()),
                (fg(160, 160, 180) + '  Floor:',  fg(220, 190, 80) + f' {floor}' + rst()),
                (fg(160, 160, 180) + '  Turns:',  fg(220, 190, 80) + f' {turns}' + rst()),
                (fg(160, 160, 180) + '  Killed:', fg(220, 190, 80) + f' {killed}' + rst()),
            ]
            for label, val in legacy_stats:
                body.append(f'    {label}{val}')

        body.append('')
        body.append('')
        body.append(fg(120, 120, 150) + '    The dungeon claims another soul...' + rst())

        footer_text = 'Press any key to return to menu  |  R - retry with same class'
        buf = _draw_frame('GAME OVER', f'You fell on floor {floor}', body,
                          footer=footer_text)

        sys.stdout.write('\n'.join(buf))
        sys.stdout.flush()
        t += 0.05
        time.sleep(0.03)


# ============================================================
#  Level Up Notification
# ============================================================

def show_level_up(level: int):
    """Flash level up message."""
    buf = f"\x1b[2;33;1m" + f" " * 20 + f"LEVEL UP! Now level {level}!" + f" " * 20 + "\x1b[0m"
    sys.stdout.write(f"\x1b[1H{buf}")
    sys.stdout.flush()
    time.sleep(1.0)


# ============================================================
#  Victory Screen
# ============================================================

def show_victory(floor: int, turns: int, killed: int):
    """Show victory screen, then return to main menu."""
    inp = InputState()
    t = 0.0
    time.sleep(0.3)

    while True:
        keys = inp.read()
        if "quit" in keys or "action" in keys:
            return

        body = []
        body.append('')

        # Victory text
        vt = rainbow('   V I C T O R Y !', t)
        body.append(vt)
        body.append('')
        body.append(fg(200, 200, 220) + '  You conquered the dungeon!' + rst())
        body.append('')

        stats = [
            (fg(160, 160, 180) + '  Floor:', fg(220, 190, 80) + f' {floor}' + rst()),
            (fg(160, 160, 180) + '  Turns:', fg(220, 190, 80) + f' {turns}' + rst()),
            (fg(160, 160, 180) + '  Kills:', fg(220, 190, 80) + f' {killed}' + rst()),
        ]
        for label, val in stats:
            body.append(f'    {label}{val}')

        body.append('')
        body.append('')
        body.append(fg(180, 180, 200) + '  Your legend will be remembered.' + rst())

        buf = _draw_frame('VICTORY', 'The dungeon has been conquered', body,
                          footer='Press any key to return to menu')

        sys.stdout.write('\n'.join(buf))
        sys.stdout.flush()
        t += 0.05
        time.sleep(0.03)
