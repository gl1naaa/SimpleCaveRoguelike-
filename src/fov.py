import math
from typing import Dict, Set, Tuple, List, Optional


# ---------------------------------------------------------------------------
#  New API: standalone compute_fov + FovCache
# ---------------------------------------------------------------------------

def compute_fov(tiles: List[List[str]], px: int, py: int,
                radius: int) -> Set[Tuple[int, int]]:
    """Raycast FOV.  Returns the *set* of visible cell coordinates (x, y).

    Walls are included in the set (they are visible but block further rays).
    """
    h = len(tiles)
    w = len(tiles[0]) if h else 0
    visible: Set[Tuple[int, int]] = set()
    visible.add((px, py))
    for i in range(720):
        a = i * math.pi / 360
        dx, dy = math.cos(a), math.sin(a)
        rx, ry = px + 0.5, py + 0.5
        for _ in range(radius):
            ix, iy = int(rx), int(ry)
            if not (0 <= ix < w and 0 <= iy < h):
                break
            visible.add((ix, iy))
            if tiles[iy][ix] == "#":
                break
            rx += dx
            ry += dy
    return visible


class FovCache:
    """Caches FOV results.  Recomputes only when the player moves *or* the
    map_version counter changes.

    Usage::

        cache = FovCache()
        while True:
            cells = cache.get(tiles, player_x, player_y, map_version)
    """

    def __init__(self):
        self._last_px: Optional[int] = None
        self._last_py: Optional[int] = None
        self._last_version: Optional[int] = None
        self._cached: Set[Tuple[int, int]] = set()

    def get(self, tiles: List[List[str]], px: int, py: int,
            map_version: int = 0) -> Set[Tuple[int, int]]:
        """Return cached FOV set.  Recomputes only if position or map changed."""
        if (px, py) == (self._last_px, self._last_py) \
                and map_version == self._last_version:
            return self._cached
        self._last_px = px
        self._last_py = py
        self._last_version = map_version
        self._cached = compute_fov(tiles, px, py, radius=min(len(tiles), len(tiles[0])) if tiles else 0)
        return self._cached

    def invalidate(self):
        """Force a recompute on the next get() call."""
        self._last_px = None
        self._last_py = None
        self._last_version = None
        self._cached = set()


# ---------------------------------------------------------------------------
#  Legacy FOV class (backward-compatible)
# ---------------------------------------------------------------------------

class FOV:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.visible: Dict[Tuple[int, int], float] = {}
        self.explored: Set[Tuple[int, int]] = set()

    def compute(self, cx: int, cy: int, radius: int, tiles: List[List[str]]):
        """Compute FOV using the new compute_fov helper, then build the
        brightness dict for backward compatibility."""
        cells = compute_fov(tiles, cx, cy, radius)
        self.visible = {}
        for ix, iy in cells:
            dist = math.sqrt((ix - cx) ** 2 + (iy - cy) ** 2)
            bright = max(0.05, 1.0 - dist / radius)
            self.visible[(ix, iy)] = bright
        self.explored.update(cells)

    def reset(self):
        self.visible.clear()
