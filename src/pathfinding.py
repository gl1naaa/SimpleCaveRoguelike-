from collections import deque
from typing import Set, Tuple, List, Optional


def bfs_path(start: Tuple[int, int], goal: Tuple[int, int],
             walls: Set[Tuple[int, int]], occupied: Set[Tuple[int, int]],
             max_depth: int = 15) -> List[Tuple[int, int]]:
    if start == goal:
        return []
    sx, sy = start
    gx, gy = goal
    if (gx, gy) in walls:
        return []
    visited = {start}
    queue = deque([(sx, sy, [])])
    while queue:
        x, y, path = queue.popleft()
        if len(path) >= max_depth:
            continue
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if (nx, ny) in visited or (nx, ny) in walls:
                continue
            if (nx, ny) != goal and (nx, ny) in occupied:
                continue
            new_path = path + [(nx, ny)]
            if (nx, ny) == goal:
                return new_path
            visited.add((nx, ny))
            queue.append((nx, ny, new_path))
    return []


def flee_path(start: Tuple[int, int], threat: Tuple[int, int],
              walls: Set[Tuple[int, int]], occupied: Set[Tuple[int, int]],
              depth: int = 3) -> List[Tuple[int, int]]:
    sx, sy = start
    tx, ty = threat
    dx = sx - tx
    dy = sy - ty
    best_dir = (0, 0)
    best_dist = 0
    for ddx, ddy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nx, ny = sx + ddx, sy + ddy
        if (nx, ny) in walls or (nx, ny) in occupied:
            continue
        dist = abs(nx - tx) + abs(ny - ty)
        if dist > best_dist:
            best_dist = dist
            best_dir = (ddx, ddy)
    if best_dir == (0, 0):
        return []
    path = []
    cx, cy = sx, sy
    for _ in range(depth):
        nx, ny = cx + best_dir[0], cy + best_dir[1]
        if (nx, ny) in walls or (nx, ny) in occupied:
            break
        path.append((nx, ny))
        cx, cy = nx, ny
    return path


def flank_positions(start: Tuple[int, int], target: Tuple[int, int],
                    walls: Set[Tuple[int, int]], occupied: Set[Tuple[int, int]],
                    depth: int = 3) -> List[Tuple[int, int]]:
    sx, sy = start
    tx, ty = target
    candidates = []
    for dx in range(-depth, depth + 1):
        for dy in range(-depth, depth + 1):
            if dx == 0 and dy == 0:
                continue
            fx, fy = tx + dx, ty + dy
            if (fx, fy) in walls or (fx, fy) in occupied:
                continue
            dist_to_target = abs(fx - tx) + abs(fy - ty)
            dist_to_self = abs(fx - sx) + abs(fy - sy)
            behind = abs(dx) > abs(dy) and ((dx > 0) != (tx > sx))
            score = (10 - dist_to_target) * 2 + (10 - dist_to_self) + (20 if behind else 0)
            candidates.append((score, (fx, fy)))
    candidates.sort(reverse=True)
    return [pos for _, pos in candidates[:5]]
