import random
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from config import (
    MAP_WIDTH, MAP_HEIGHT, ROOM_MIN, ROOM_MAX, CONNECT_CHANCE,
    ROOM_NORMAL, ROOM_TREASURE, ROOM_BOSS, ROOM_TRAP, ROOM_EVENT,
    ROOM_WEIGHTS, ALTAR,
)


@dataclass
class Room:
    x: int
    y: int
    w: int
    h: int
    room_type: str = ROOM_NORMAL

    @property
    def center(self):
        return (self.x + self.w // 2, self.y + self.h // 2)

    @property
    def inner(self):
        return [(x, y) for x in range(self.x + 1, self.x + self.w - 1)
                for y in range(self.y + 1, self.y + self.h - 1)]

    @property
    def area(self):
        return (self.w - 2) * (self.h - 2)


@dataclass
class Node:
    x: int
    y: int
    w: int
    h: int
    left: Optional["Node"] = None
    right: Optional["Node"] = None
    room: Optional[Room] = None

    def is_leaf(self):
        return self.left is None and self.right is None


def _pick_room_type(floor: int, is_first: bool, is_last: bool) -> str:
    if is_first:
        return ROOM_NORMAL
    if is_last:
        return ROOM_BOSS
    types = list(ROOM_WEIGHTS.keys())
    weights = list(ROOM_WEIGHTS.values())
    # Increase trap/boss weight on deeper floors
    for i, t in enumerate(types):
        if t == ROOM_TRAP:
            weights[i] += floor * 2
        elif t == ROOM_BOSS:
            weights[i] += floor
        elif t == ROOM_TREASURE:
            weights[i] += floor * 0.5
    return random.choices(types, weights=weights, k=1)[0]


class Dungeon:
    def __init__(self, w=MAP_WIDTH, h=MAP_HEIGHT, floor: int = 1):
        self.w, self.h = w, h
        self.floor = floor
        self.rooms: List[Room] = []
        self.corridors: List[Tuple[int, int]] = []
        self.walls: set = set()

    def generate(self):
        root = Node(0, 0, self.w, self.h)
        self._split(root, 0)
        self._create_rooms(root)
        self._assign_room_types()
        self._connect()
        tiles = self._build()
        self._compute_walls(tiles)
        first = self.rooms[0]
        last = self.rooms[-1]
        tiles[last.center[1]][last.center[0]] = ">"
        return tiles, first, last, self.rooms

    def _split(self, node, depth):
        if depth > 5 or (node.w < ROOM_MIN * 2 and node.h < ROOM_MIN * 2):
            return
        horiz = node.w > node.h
        if horiz:
            lo, hi = ROOM_MIN, node.w - ROOM_MIN
        else:
            lo, hi = ROOM_MIN, node.h - ROOM_MIN
        if hi <= lo:
            return
        sp = random.randint(lo, hi)
        if horiz:
            node.left = Node(node.x, node.y, sp, node.h)
            node.right = Node(node.x + sp, node.y, node.w - sp, node.h)
        else:
            node.left = Node(node.x, node.y, node.w, sp)
            node.right = Node(node.x, node.y + sp, node.w, node.h - sp)
        self._split(node.left, depth + 1)
        self._split(node.right, depth + 1)

    def _create_rooms(self, node):
        if node.is_leaf():
            if node.w >= ROOM_MIN + 2 and node.h >= ROOM_MIN + 2 and random.random() < 0.8:
                rw = random.randint(ROOM_MIN, min(ROOM_MAX, node.w - 2))
                rh = random.randint(ROOM_MIN, min(ROOM_MAX, node.h - 2))
                rx = random.randint(node.x + 1, node.x + node.w - rw - 1)
                ry = random.randint(node.y + 1, node.y + node.h - rh - 1)
                r = Room(rx, ry, rw, rh)
                node.room = r
                self.rooms.append(r)
        else:
            if node.left:
                self._create_rooms(node.left)
            if node.right:
                self._create_rooms(node.right)

    def _assign_room_types(self):
        if len(self.rooms) < 2:
            for r in self.rooms:
                r.room_type = ROOM_NORMAL
            return
        for i, room in enumerate(self.rooms):
            is_first = (i == 0)
            is_last = (i == len(self.rooms) - 1)
            room.room_type = _pick_room_type(self.floor, is_first, is_last)

    def _connect(self):
        if len(self.rooms) < 2:
            return
        for i in range(len(self.rooms) - 1):
            self._corridor(self.rooms[i].center, self.rooms[i + 1].center)
        for _ in range(max(1, len(self.rooms) // 3)):
            if random.random() < CONNECT_CHANCE and len(self.rooms) >= 2:
                a, b = random.sample(self.rooms, 2)
                self._corridor(a.center, b.center)

    def _corridor(self, a, b):
        x1, y1 = a
        x2, y2 = b
        w = 3  # corridor width
        if random.random() < 0.5:
            for x in range(min(x1, x2), max(x1, x2) + 1):
                for dy in range(-(w // 2), (w // 2) + 1):
                    self.corridors.append((x, y1 + dy))
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for dx in range(-(w // 2), (w // 2) + 1):
                    self.corridors.append((x2 + dx, y))
            # Widen at intersection
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    self.corridors.append((x2 + dx, y1 + dy))
        else:
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for dx in range(-(w // 2), (w // 2) + 1):
                    self.corridors.append((x1 + dx, y))
            for x in range(min(x1, x2), max(x1, x2) + 1):
                for dy in range(-(w // 2), (w // 2) + 1):
                    self.corridors.append((x, y2 + dy))
            # Widen at intersection
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    self.corridors.append((x1 + dx, y2 + dy))

    def _build(self):
        t = [["#" for _ in range(self.w)] for _ in range(self.h)]
        for r in self.rooms:
            for x, y in r.inner:
                if 0 <= x < self.w and 0 <= y < self.h:
                    t[y][x] = "."
        for x, y in self.corridors:
            if 0 <= x < self.w and 0 <= y < self.h:
                t[y][x] = "."
        return t

    def _compute_walls(self, tiles):
        self.walls = set()
        for y in range(self.h):
            for x in range(self.w):
                if tiles[y][x] == "#":
                    self.walls.add((x, y))

    def get_floor_tiles(self, tiles) -> List[Tuple[int, int]]:
        floors = []
        for y in range(self.h):
            for x in range(self.w):
                if tiles[y][x] == ".":
                    floors.append((x, y))
        return floors

    def get_room_center(self, room: Room) -> Tuple[int, int]:
        return room.center


def generate_dungeon(floor: int = 1):
    return Dungeon(floor=floor).generate()


# ============================================================
#  City generation — safe zone between floors
# ============================================================

def generate_city(floor: int = 1):
    """Generate a city map. Returns (tiles, walls, shop_items, player_start)."""
    w, h = 60, 40
    tiles = [["#" for _ in range(w)] for _ in range(h)]

    # Big open room
    for y in range(3, h - 3):
        for x in range(3, w - 3):
            tiles[y][x] = "."

    # Inner walls for atmosphere (pillars)
    for px in [15, 30, 45]:
        for py in [10, 20, 30]:
            if 3 < py < h - 3 and 3 < px < w - 3:
                tiles[py][px] = "#"

    walls = set()
    for y in range(h):
        for x in range(w):
            if tiles[y][x] == "#":
                walls.add((x, y))

    # Multiple shops with different themes
    from items import (generate_random_item, generate_weapon, generate_chest,
                       generate_helmet, generate_legs, generate_boots,
                       generate_gloves, generate_necklace, generate_ring,
                       generate_cape, generate_consumable)
    import random as _rand

    # Arrange shops in a grid: 2 rows x 5 cols
    shop_defs = [
        {"x": 8,  "y": 6,  "name": "Weapon Shop",   "gen": lambda fl: generate_weapon(fl, "")},
        {"x": 20, "y": 6,  "name": "Helmet Shop",   "gen": lambda fl: generate_helmet(fl)},
        {"x": 32, "y": 6,  "name": "Chest Shop",    "gen": lambda fl: generate_chest(fl)},
        {"x": 44, "y": 6,  "name": "Legs Shop",     "gen": lambda fl: generate_legs(fl)},
        {"x": 8,  "y": 12, "name": "Boots Shop",    "gen": lambda fl: generate_boots(fl)},
        {"x": 20, "y": 12, "name": "Gloves Shop",   "gen": lambda fl: generate_gloves(fl)},
        {"x": 32, "y": 12, "name": "Necklace Shop", "gen": lambda fl: generate_necklace(fl)},
        {"x": 44, "y": 12, "name": "Ring Shop",     "gen": lambda fl: generate_ring(fl)},
        {"x": 55, "y": 6,  "name": "Cape Shop",     "gen": lambda fl: generate_cape(fl)},
        {"x": 55, "y": 12, "name": "Potion Shop",   "gen": lambda fl: generate_consumable(fl)},
    ]

    shops = []
    for sd in shop_defs:
        tiles[sd["y"]][sd["x"]] = "$"
        items_list = []
        for _ in range(3):
            items_list.append(sd["gen"](floor))
        shops.append({"x": sd["x"], "y": sd["y"], "name": sd["name"], "items": items_list})

    # Place altar at center
    altar_x, altar_y = w // 2, h // 2
    tiles[altar_y][altar_x] = ALTAR

    # Place stairs (>) at right side
    stairs_x, stairs_y = w - 8, h // 2
    tiles[stairs_y][stairs_x] = ">"

    # Player start
    player_start = (5, h // 2)

    return tiles, walls, shops, player_start
