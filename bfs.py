"""
bfs.py — Standalone BFS pathfinding for Battle City
Coordinate system matches game.py: x = col, y = row
grid is accessed as grid[y][x]
Passable tiles: EMPTY(0), FOREST(4)
"""

from collections import deque

PASSABLE = {0, 4}   # Empty, Forest
GRID_W   = 26
GRID_H   = 26


def bfs(grid, start, goal):
    """
    BFS on the 26x26 grid.
    start, goal: (x, y) tuples  — x=col, y=row
    Returns full path as list of (x, y) tuples from start to goal (inclusive).
    Returns [] if no path exists.
    The goal tile (Eagle=5) is treated as reachable destination even though it's not passable.
    """
    if start == goal:
        return [start]

    queue   = deque([start])
    visited = {start: None}   # node -> parent

    while queue:
        current = queue.popleft()

        if current == goal:
            # Reconstruct path
            path = []
            node = current
            while node is not None:
                path.append(node)
                node = visited[node]
            path.reverse()
            return path

        cx, cy = current
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < GRID_W and 0 <= ny < GRID_H):
                continue
            nb = (nx, ny)
            if nb in visited:
                continue
            tile = grid[ny][nx]   # grid[row][col]
            if tile in PASSABLE or nb == goal:
                visited[nb] = current
                queue.append(nb)

    return []   # no path


def bfs_next_step(grid, start, goal):
    """Returns only the next (x, y) step, or None if unreachable / already there."""
    path = bfs(grid, start, goal)
    return path[1] if len(path) >= 2 else None
