import math
from typing import Dict, Set, Tuple, List

class FOV:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.visible: Dict[Tuple[int, int], float] = {}
        self.explored: Set[Tuple[int, int]] = set()

    def compute(self, cx: int, cy: int, radius: int, tiles: List[List[str]]):
        self.visible = {}
        self.visible[(cx, cy)] = 1.0
        for i in range(720):
            a = i * math.pi / 360
            dx, dy = math.cos(a), math.sin(a)
            rx, ry = cx + 0.5, cy + 0.5
            for _ in range(radius):
                ix, iy = int(rx), int(ry)
                if not (0 <= ix < self.w and 0 <= iy < self.h):
                    break
                dist = math.sqrt((ix - cx) ** 2 + (iy - cy) ** 2)
                bright = max(0.05, 1.0 - dist / radius)
                if (ix, iy) not in self.visible or self.visible[(ix, iy)] < bright:
                    self.visible[(ix, iy)] = bright
                self.explored.add((ix, iy))
                if tiles[iy][ix] == "#":
                    break
                rx += dx
                ry += dy

    def reset(self):
        self.visible.clear()