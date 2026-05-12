import random
from collections import deque
from constants import (
    GRID_SIZE, EMPTY, BRICK, STEEL, WATER, FOREST, EAGLE,
    EAGLE_POS, SPAWN_ENEMY, SPAWN_PLAYER
)


class CSPMapGenerator:
    def __init__(self, level=1):
        self.level = level

    def generate(self):
        for _ in range(80):
            grid = self._fresh()
            self._fill_terrain(grid)
            self._place_fixed(grid)
            self._protect_eagle(grid)
            if self._validate(grid):
                return grid
        # Fallback: minimal open map with just eagle protection
        grid = self._fresh()
        self._place_fixed(grid)
        self._protect_eagle(grid)
        return grid

    # ──────────────────────────────────────────────────────────────────
    #  Terrain filling
    # ──────────────────────────────────────────────────────────────────

    def _fill_terrain(self, grid):
        """
        Fill the grid with NES-accurate densities:
          Level 1: ~50-55% brick (dense maze), ~3% steel, ~5% forest, ~3% water
          Level 2: ~35% brick, ~15% steel (fortress walls), ~4% forest, ~3% water
        """
        lv = self.level

        if lv == 1:
            # Dense brick maze — fill almost everything with brick first,
            # then carve corridors (inverted maze generation)
            self._fill_brick_maze(grid)
        elif lv == 2:
            self._fill_steel_fortress(grid)
        else:
            self._fill_brick_maze(grid)

    def _fill_brick_maze(self, grid):
        """
        NES-style Level 1: Start with ~55% brick, add corridors.
        Uses block-placement to create natural-looking brick clusters.
        """
        lv = self.level
        # Place brick in 2×2 and 3×2 blocks across the map
        for y in range(0, GRID_SIZE, 3):
            for x in range(0, GRID_SIZE, 3):
                # Skip ~50% of positions — 2×2 blocks on a 3-step grid give
                # ~(4/9)*50% ≈ 22% brick density; steel/water/forest add ~8%
                # keeping total well under the C4 40% cap.
                if random.random() < 0.50:
                    continue
                # Place a 2×2 brick block
                for dy in range(2):
                    for dx in range(2):
                        nx, ny = x+dx, y+dy
                        if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                            grid[ny][nx] = BRICK

        # Add some steel (sparse in level 1)
        for _ in range(12):
            x = random.randint(2, GRID_SIZE-3)
            y = random.randint(2, GRID_SIZE-5)
            for dy in range(random.randint(1, 2)):
                for dx in range(random.randint(1, 2)):
                    if 0 <= x+dx < GRID_SIZE and 0 <= y+dy < GRID_SIZE:
                        grid[y+dy][x+dx] = STEEL

        # Add forest patches
        for _ in range(8):
            x = random.randint(1, GRID_SIZE-3)
            y = random.randint(1, GRID_SIZE-4)
            for dy in range(2):
                for dx in range(2):
                    if 0 <= x+dx < GRID_SIZE and 0 <= y+dy < GRID_SIZE:
                        if grid[y+dy][x+dx] == EMPTY:
                            grid[y+dy][x+dx] = FOREST

        # Add water patches (small)
        for _ in range(5):
            x = random.randint(2, GRID_SIZE-4)
            y = random.randint(4, GRID_SIZE-6)
            for dy in range(2):
                for dx in range(3):
                    if 0 <= x+dx < GRID_SIZE and 0 <= y+dy < GRID_SIZE:
                        if grid[y+dy][x+dx] == EMPTY:
                            grid[y+dy][x+dx] = WATER

    def _fill_steel_fortress(self, grid):
        """
        Level 2: Steel walls form barriers, brick fills gaps.
        """
        # First lay down brick base (~35%)
        for y in range(0, GRID_SIZE, 3):
            for x in range(0, GRID_SIZE, 3):
                if random.random() < 0.50:   # ~22% brick base; steel adds ~10%
                    continue
                for dy in range(2):
                    for dx in range(2):
                        nx, ny = x+dx, y+dy
                        if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                            grid[ny][nx] = BRICK

        # Steel barrier walls (horizontal/vertical runs)
        for _ in range(14):
            x = random.randint(2, GRID_SIZE-6)
            y = random.randint(2, GRID_SIZE-6)
            # Horizontal or vertical
            if random.random() < 0.5:
                length = random.randint(3, 5)
                for dx in range(length):
                    if x+dx < GRID_SIZE:
                        grid[y][x+dx] = STEEL
            else:
                length = random.randint(3, 5)
                for dy in range(length):
                    if y+dy < GRID_SIZE:
                        grid[y+dy][x] = STEEL

        # Forest patches
        for _ in range(6):
            x = random.randint(1, GRID_SIZE-3)
            y = random.randint(1, GRID_SIZE-4)
            for dy in range(2):
                for dx in range(2):
                    if 0 <= x+dx < GRID_SIZE and 0 <= y+dy < GRID_SIZE:
                        if grid[y+dy][x+dx] == EMPTY:
                            grid[y+dy][x+dx] = FOREST

        # Water patches
        for _ in range(4):
            x = random.randint(2, GRID_SIZE-4)
            y = random.randint(4, GRID_SIZE-6)
            for dy in range(2):
                for dx in range(3):
                    if 0 <= x+dx < GRID_SIZE and 0 <= y+dy < GRID_SIZE:
                        if grid[y+dy][x+dx] == EMPTY:
                            grid[y+dy][x+dx] = WATER

    # ──────────────────────────────────────────────────────────────────
    #  Fixed tile placement
    # ──────────────────────────────────────────────────────────────────

    def _fresh(self):
        return [[EMPTY]*GRID_SIZE for _ in range(GRID_SIZE)]

    def _place_fixed(self, grid):
        """Eagle and spawn points must always be clear."""
        ex, ey = EAGLE_POS
        grid[ey][ex] = EAGLE
        for sx, sy in SPAWN_ENEMY:
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    nx, ny = sx+dx, sy+dy
                    if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                        if grid[ny][nx] != EAGLE:
                            grid[ny][nx] = EMPTY
        px, py = SPAWN_PLAYER
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                nx, ny = px+dx, py+dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                    if grid[ny][nx] != EAGLE:
                        grid[ny][nx] = EMPTY

    def _protect_eagle(self, grid):
        """
        C1: Eagle must have 2 rings of brick protection.
        Inner 1-tile ring: always brick.
        Outer ring: brick on level 1, also brick on level 2.
        """
        ex, ey = EAGLE_POS
        # Inner ring (distance 1)
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                if dx == 0 and dy == 0: continue
                nx, ny = ex+dx, ey+dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                    if grid[ny][nx] != EAGLE:
                        grid[ny][nx] = BRICK
        # Outer ring (distance 2) — only sides, not corners to allow some passage
        for d in [-2, 2]:
            for o in range(-1, 2):
                for nx, ny in [(ex+d, ey+o), (ex+o, ey+d)]:
                    if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                        if grid[ny][nx] == EMPTY:
                            grid[ny][nx] = BRICK

    def _clear_corridors(self, grid):
        """Removed — was creating straight center corridor defeating maze purpose.
        Reachability is guaranteed by CSP C2 validation instead."""
        pass

    # ──────────────────────────────────────────────────────────────────
    #  CSP Validation
    # ──────────────────────────────────────────────────────────────────

    def _validate(self, grid):
        # C4: wall density ≤ 40% (brick+steel combined)
        walls = sum(
            1 for y in range(GRID_SIZE) for x in range(GRID_SIZE)
            if grid[y][x] in (BRICK, STEEL)
        )
        density = walls / (GRID_SIZE * GRID_SIZE)
        if density > 0.40:   # C4: spec requires ≤ 40% wall density
            return False

        # C2: reachability from every spawn to Eagle
        # Note: _reachable treats brick as passable (tanks can shoot through)
        # only steel/water are hard barriers
        for sx, sy in SPAWN_ENEMY:
            if not self._reachable(grid, sx, sy, *EAGLE_POS):
                return False

        # C3: spawn points must be clear
        for sx, sy in SPAWN_ENEMY:
            if grid[sy][sx] not in (EMPTY, FOREST):
                return False

        # C5: water must not be the only blocker (checked via reachability above)
        return True

    def _reachable(self, grid, sx, sy, gx, gy):
        """
        BFS reachability treating brick as passable (tanks shoot through brick).
        Only steel and water are hard barriers for this check.
        """
        visited = {(sx, sy)}
        q = deque([(sx, sy)])
        while q:
            x, y = q.popleft()
            if x == gx and y == gy:
                return True
            for dx, dy in [(0,-1),(0,1),(-1,0),(1,0)]:
                nx, ny = x+dx, y+dy
                if (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE
                        and (nx, ny) not in visited
                        and grid[ny][nx] not in (STEEL, WATER)):
                    visited.add((nx, ny))
                    q.append((nx, ny))
        return False
