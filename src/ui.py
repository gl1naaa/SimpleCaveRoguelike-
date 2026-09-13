import sys, os, time

ESC = "\x1b"

def fg(r, g, b): return f"{ESC}[38;2;{r};{g};{b}m"
def bg(r, g, b): return f"{ESC}[48;2;{r};{g};{b}m"
def rst():       return f"{ESC}[0m"
def bold():      return f"{ESC}[1m"
def dim():       return f"{ESC}[2m"

def vis_len(s):
    """Visible length of string excluding ANSI escape codes."""
    i, length = 0, 0
    while i < len(s):
        if s[i] == '\x1b':
            while i < len(s) and s[i] != 'm':
                i += 1
        else:
            length += 1
        i += 1
    return length

def pad_line(line, width=0):
    """Pad line with spaces to fill width. Auto-detects terminal width if 0."""
    if width <= 0:
        try:
            import shutil
            width = shutil.get_terminal_size().columns
        except Exception:
            width = 120
    return line + ' ' * max(0, width - vis_len(line))

# Unicode
BLK   = "\u2588"
SH1   = "\u2591"
SH2   = "\u2592"
SH3   = "\u2593"
DIAM  = "\u2666"
HEART = "\u2665"
STAR  = "\u2606"
DSTAR = "\u2605"
ARROW = "\u25bc"
DOT   = "\u00b7"

# Box drawing
WALL_H  = "\u2550"
WALL_V  = "\u2551"
WALL_TL = "\u2554"
WALL_TR = "\u2557"
WALL_BL = "\u255a"
WALL_BR = "\u255d"
WALL_LT = "\u2560"
WALL_RT = "\u2563"
WALL_T  = "\u2566"
WALL_B  = "\u2569"
WALL_X  = "\u256c"

BOX_H  = "\u2500"
BOX_V  = "\u2502"
BOX_TL = "\u250c"
BOX_TR = "\u2510"
BOX_BL = "\u2514"
BOX_BR = "\u2518"
BOX_LT = "\u251c"
BOX_RT = "\u2524"
BOX_T  = "\u252c"
BOX_B  = "\u2534"
BOX_X  = "\u253c"

RAINbow_COLORS = [
    (255, 0, 0), (255, 127, 0), (255, 255, 0),
    (0, 255, 0), (0, 0, 255), (75, 0, 130), (148, 0, 211),
]

def rainbow(text, t=0.0):
    """Text with rainbow cycling effect."""
    result = ""
    for i, ch in enumerate(text):
        ci = (i + int(t * 10)) % len(RAINbow_COLORS)
        r, g, b = RAINbow_COLORS[ci]
        result += fg(r, g, b) + ch
    return result + rst()

def rarity_color(rarity):
    """Return ANSI color code for rarity."""
    from config import RARITY_COLORS
    c = RARITY_COLORS.get(rarity, (170, 170, 170))
    if c == "rainbow":
        return fg(255, 255, 255)  # fallback, caller should use rainbow()
    return fg(*c)

def draw_box(x, y, w, h, title="", fg_color=(120, 120, 140)):
    """Draw a box with optional title. Returns list of strings."""
    lines = []
    r, g, b = fg_color
    top = BOX_TL + BOX_H * (w - 2) + BOX_TR
    if title:
        pad = w - 4 - len(title)
        left = pad // 2
        right = pad - left
        top = BOX_TL + BOX_H * left + " " + title + " " + BOX_H * right + BOX_TR
    lines.append(fg(r, g, b) + top + rst())
    for i in range(h - 2):
        lines.append(fg(r, g, b) + BOX_V + rst() + " " * (w - 2) + fg(r, g, b) + BOX_V + rst())
    bot = BOX_BL + BOX_H * (w - 2) + BOX_BR
    lines.append(fg(r, g, b) + bot + rst())
    return lines

def clear_screen():
    sys.stdout.write(f"{ESC}[2J")
    sys.stdout.flush()

def cursor_home():
    sys.stdout.write(f"{ESC}[H")

def hide_cursor():
    sys.stdout.write(f"{ESC}[?25l")

def show_cursor():
    sys.stdout.write(f"{ESC}[?25h")

def combo_popup_text(text, r=255, g=255, b=100):
    """Create bright styled text for combo popups."""
    return f"\x1b[1m\x1b[38;2;{r};{g};{b}m{text}\x1b[0m"

def write_lines(buf):
    sys.stdout.write("\n".join(buf))
    sys.stdout.flush()