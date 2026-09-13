"""
fx.py — Terminal particle / flash / shake / banner effects for SimpleCaveRoguelike.

Pure stdlib.  Only imports from ui (fg/bg/rst/bold) and time/math/random.
"""

import time
import math
import random
from typing import List, Dict, Optional, Tuple

from ui import fg, bg, rst, bold


# ============================================================
#  FXSystem
# ============================================================

class FXSystem:
    """Centralised visual-effects manager.

    State
    -----
    particles : list[dict]    – floating spark chars  {x,y,char,color_fg,ttl,created}
    flashes   : dict (x,y) -> (r,g,b,until)          – tile highlights
    trauma    : float 0..1    – screen-shake intensity (decays automatically)
    banners   : list[str]     – queued combo / kill banners (text strings)
    """

    def __init__(self):
        self.particles: List[dict] = []
        self.flashes: Dict[Tuple[int, int], Tuple[int, int, int, float]] = {}
        self.trauma: float = 0.0
        self.banners: List[str] = []

    # ---- Spawners -------------------------------------------------------

    def spawn_hit(self, x: int, y: int,
                  color: str = "255,200,100", n: int = 4) -> None:
        """Small burst of characters around (x, y)."""
        try:
            r, g, b = (int(v) for v in color.split(","))
        except Exception:
            r, g, b = 255, 200, 100
        now = time.time()
        for _ in range(n):
            dx = random.randint(-1, 1)
            dy = random.randint(-1, 1)
            ch = random.choice([".", "*", "+", "\u00b7"])
            self.particles.append(
                {"x": x + dx, "y": y + dy, "char": ch,
                 "color_fg": (r, g, b), "ttl": 0.3 + random.random() * 0.2,
                 "created": now}
            )

    def spawn_explosion(self, x: int, y: int, n: int = 10) -> None:
        """Radial burst of fire-coloured particles."""
        now = time.time()
        for _ in range(n):
            angle = random.random() * math.tau
            dist = random.random() * 1.5
            px = x + int(round(math.cos(angle) * dist))
            py = y + int(round(math.sin(angle) * dist))
            ch = random.choice(["*", "\u25cf", "\u2666", "\u00b7"])
            r = min(255, 200 + random.randint(0, 55))
            g = random.randint(60, 180)
            b = random.randint(0, 40)
            self.particles.append(
                {"x": px, "y": py, "char": ch,
                 "color_fg": (r, g, b), "ttl": 0.4 + random.random() * 0.3,
                 "created": now}
            )

    def spawn_heal(self, x: int, y: int, n: int = 4) -> None:
        """Upward-drifting green '+' particles."""
        now = time.time()
        for _ in range(n):
            dx = random.randint(-1, 1)
            dy = random.randint(-1, 0)
            self.particles.append(
                {"x": x + dx, "y": y + dy, "char": "+",
                 "color_fg": (0, 255, 100), "ttl": 0.5 + random.random() * 0.3,
                 "created": now}
            )

    # ---- Shake -----------------------------------------------------------

    def add_shake(self, amount: float) -> None:
        """Increase screen-shake trauma (clamped to 0..1)."""
        try:
            self.trauma = min(1.0, self.trauma + float(amount))
        except Exception:
            pass

    # ---- Flash -----------------------------------------------------------

    def flash(self, x: int, y: int, r: int, g: int, b: int,
              duration: float = 0.12) -> None:
        """Highlight a tile with a coloured flash for *duration* seconds."""
        try:
            self.flashes[(int(x), int(y))] = (
                int(r), int(g), int(b),
                time.time() + max(0.01, float(duration))
            )
        except Exception:
            pass

    # ---- Banner ----------------------------------------------------------

    def banner(self, text: str, r: int = 255, g: int = 255, b: int = 100) -> None:
        """Queue a styled banner string (drawn by caller)."""
        try:
            self.banners.append(f"{bold()}{fg(int(r), int(g), int(b))}{text}{rst()}")
        except Exception:
            self.banners.append(str(text))

    # ---- Tick / cleanup --------------------------------------------------

    def update(self, now: float) -> None:
        """Remove dead particles, expire flashes, decay trauma.
        Call once per frame with the current *now* timestamp.
        """
        try:
            self.particles = [
                p for p in self.particles
                if (now - p["created"]) < p["ttl"]
            ]
        except Exception:
            self.particles.clear()

        try:
            self.flashes = {
                k: v for k, v in self.flashes.items() if now < v[3]
            }
        except Exception:
            self.flashes.clear()

        # Decay trauma towards 0 (fast-ish exponential falloff)
        try:
            if self.trauma > 0:
                self.trauma = max(0.0, self.trauma - 0.05)
        except Exception:
            self.trauma = 0.0

    # ---- Queries ---------------------------------------------------------

    def get_shake_offset(self) -> Tuple[int, int]:
        """Return (dx, dy) integer offset for the viewport, derived from *trauma*.
        Each component is in {-1, 0, 1}.  Returns (0, 0) when trauma is zero.
        """
        try:
            if self.trauma <= 0:
                return (0, 0)
            mag = self.trauma
            dx = int(round((random.random() * 2 - 1) * mag))
            dy = int(round((random.random() * 2 - 1) * mag))
            # Clamp to -1..1
            dx = max(-1, min(1, dx))
            dy = max(-1, min(1, dy))
            return (dx, dy)
        except Exception:
            return (0, 0)

    def particles_at(self, x: int, y: int, now: float) -> List[dict]:
        """Return alive particles at tile (x, y)."""
        try:
            return [
                p for p in self.particles
                if p["x"] == x and p["y"] == y and (now - p["created"]) < p["ttl"]
            ]
        except Exception:
            return []

    def flash_at(self, x: int, y: int, now: float) -> Optional[Tuple[int, int, int]]:
        """Return (r, g, b) if (x, y) has an active flash, else None."""
        try:
            entry = self.flashes.get((int(x), int(y)))
            if entry and now < entry[3]:
                return (entry[0], entry[1], entry[2])
        except Exception:
            pass
        return None


# ============================================================
#  Tile animation helpers
# ============================================================

def water_char(t: float, fancy: bool = True) -> str:
    """Animated water glyph: toggles between two chars every ~0.5 s.
    If *fancy* is False, always use plain ASCII."""
    if not fancy:
        return "~"
    try:
        if int(t * 2) % 2 == 0:
            return "~"
        return "\u2248"  # ≈
    except Exception:
        return "~"


def torch_char(t: float, fancy: bool = True) -> str:
    """Animated torch / fire glyph: toggles between two chars.
    If *fancy* is False, always use plain asterisk."""
    if not fancy:
        return "*"
    try:
        if int(t * 3) % 2 == 0:
            return "*"
        return "\u2726"  # ✦
    except Exception:
        return "*"


# ============================================================
#  Single-character ANSI renderer
# ============================================================

def render_particle(p: dict, brightness: float = 1.0) -> str:
    """Render one particle as a styled ANSI escape string.

    *brightness* 0..1 scales the RGB values (1.0 = full colour).
    Returns a safe empty string on any error.
    """
    try:
        r, g, b = p["color_fg"]
        # Apply brightness
        if brightness < 1.0:
            r = int(r * brightness)
            g = int(g * brightness)
            b = int(b * brightness)
        return fg(r, g, b) + p["char"] + rst()
    except Exception:
        try:
            return p.get("char", "")
        except Exception:
            return ""


# ============================================================
#  Integration example (this block does NOT execute on import)
# ============================================================

# --- Хук интеграции в игровой цикл (псевдокод) ---
#
#   from fx import FXSystem, water_char, torch_char, render_particle
#
#   fx = FXSystem()                          # создать один раз при старте
#
#   # Каждый кадр (в основном цикле):
#   now = time.time()
#   fx.update(now)                            # чистка протухшего
#   sx, sy = fx.get_shake_offset()            # дрожание камеры
#   vp_x, vp_y = viewport_x + sx, viewport_y + sy   # сдвинуть вьюпорт
#
#   # Рисуя клетку (x, y):
#   flash_rgb = fx.flash_at(x, y, now)
#   if flash_rgb:
#       cell_str = bg(*flash_rgb) + tile_char + rst()
#   else:
#       cell_str = tile_char
#   for part in fx.particles_at(x, y, now):
#       cell_str = render_particle(part, brightness=0.9)
