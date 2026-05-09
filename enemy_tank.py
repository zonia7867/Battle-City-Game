"""
enemy_tank.py — BasicTank (BFS + Simple Reflex) + FastTankStub + SpawnManager

Coordinate system matches game.py exactly:
  - x = col (increases right), y = row (increases down)
  - grid accessed as grid[y][x]
  - Directions: DIR_UP=(0,-1), DIR_DOWN=(0,1), DIR_LEFT=(-1,0), DIR_RIGHT=(1,0)
  - DIRS dict matches game.py's DIRS

FPS = 10 (as set in game.py), so:
  - 3 second fire rate  = 30 ticks
  - 5 second BFS refresh = 50 ticks
  - 1.5 second spawn delay = 15 ticks
"""

import random
from collections import deque
from bfs import bfs

# ── Constants ───
TILE_SIZE  = 24
GRID_W     = 26
GRID_H     = 26
FPS        = 10

EMPTY  = 0
BRICK  = 1
STEEL  = 2
WATER  = 3
FOREST = 4
EAGLE  = 5

EAGLE_POS = (12, 24)   # (x=col, y=row)

SPAWN_POINTS = [
    (0,  0),   # Top-Left
    (12, 0),   # Top-Center
    (24, 0),   # Top-Right
]

PLAYER_START = (4, 24)

# Direction vectors 
DIR_UP    = (0, -1)
DIR_DOWN  = (0,  1)
DIR_LEFT  = (-1, 0)
DIR_RIGHT = (1,  0)
ALL_DIRS  = [DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT]

PASSABLE = {EMPTY, FOREST}


# ────────────────────────
#  EnemyBullet
# ────────────────────────
class EnemyBullet:
    """
    Enemy bullet — same logic as game.py's Bullet but owned by enemy tanks.
    Moves 2 tiles per tick (advance_step called twice per tick in game loop).
    """
    def __init__(self, x, y, direction, owner):
        self.x         = x
        self.y         = y
        self.direction = direction   # (dx, dy)
        self.owner     = owner
        self.alive     = True

    def advance_step(self, game_map, all_tanks, all_bullets):
        """Advance one tile and check collisions. Call twice per tick for 2x speed."""
        if not self.alive:
            return

        dx, dy   = self.direction
        self.x  += dx
        self.y  += dy

        # Out of bounds
        if not (0 <= self.x < GRID_W and 0 <= self.y < GRID_H):
            self.alive = False
            return

        # Bullet vs bullet
        for other in all_bullets:
            if other is not self and other.alive and other.x == self.x and other.y == self.y:
                self.alive  = False
                other.alive = False
                return

        tile = game_map[self.y][self.x]

        if tile == BRICK:
            game_map[self.y][self.x] = EMPTY
            self.alive = False
            return

        if tile == STEEL:
            self.alive = False
            return

        if tile == WATER:
            self.alive = False
            return

        if tile == EAGLE:
            # signal handled by game loop (eagle_hit flag)
            self.alive = False
            self._hit_eagle = True
            return

        # Bullet vs tanks
        for tank in all_tanks:
            if tank.alive and tank.x == self.x and tank.y == self.y:
                if tank is self.owner:
                    continue
                tank.take_damage()
                self.alive = False
                return

    def draw(self, surface):
        import pygame
        if self.alive:
            pygame.draw.rect(
                surface,
                (255, 220, 50),
                (self.x * TILE_SIZE + TILE_SIZE // 4,
                 self.y * TILE_SIZE + TILE_SIZE // 4,
                 TILE_SIZE // 2,
                 TILE_SIZE // 2)
            )


# ─────────────────────────────────────────────────────────────────
#  BasicTank  —  Simple Reflex Agent + BFS
# ─────────────────────────────────────────────────────────────────
class BasicTank:
    """
    Simple Reflex Agent.
    Rules (priority order each tick):
      1. SHOOT: player in same row/col with clear LOS → shoot
      2. WALL:  next tile on path is Brick → shoot to clear, don't move
      3. MOVE:  follow BFS path → move one tile; no path → random free direction
    """
    COLOR      = (220, 60, 60)
    HP         = 1
    SPEED      = 4    # move every 4 ticks
    FIRE_RATE  = 30   # 3s at FPS=10
    BFS_EVERY  = 50   # re-run BFS every 5s at FPS=10

    def __init__(self, x, y):
        self.x   = x
        self.y   = y
        self.hp  = self.HP
        self.direction = DIR_DOWN
        self.alive     = True

        self._tick   = 0
        self._fire   = 0
        self._bfs_t  = 0
        self.path    = []      # list of (x, y) remaining steps
        self.bullet  = None

    # ── called once right after spawning ──
    def on_spawn(self, grid):
        self._recompute_bfs(grid)

    # ── called when any brick is destroyed ──
    def on_map_changed(self, grid, destroyed_xy):
        if destroyed_xy in self.path:
            self._recompute_bfs(grid)

    def _recompute_bfs(self, grid):
        start     = (self.x, self.y)
        full_path = bfs(grid, start, EAGLE_POS)
        # drop the first element (current position)
        self.path = full_path[1:] if full_path else []

    def _line_of_sight(self, grid, px, py):
        """
        Returns (True, direction) if player is in same row/col with no Brick/Steel between.
        Otherwise (False, None).
        """
        BLOCKING = {BRICK, STEEL}
        tx, ty = self.x, self.y

        if ty == py:   # same row
            mn, mx = sorted([tx, px])
            for cx in range(mn + 1, mx):
                if grid[ty][cx] in BLOCKING:
                    return False, None
            return True, (DIR_LEFT if px < tx else DIR_RIGHT)

        if tx == px:   # same col
            mn, mx = sorted([ty, py])
            for cy in range(mn + 1, mx):
                if grid[cy][tx] in BLOCKING:
                    return False, None
            return True, (DIR_UP if py < ty else DIR_DOWN)

        return False, None

    def update(self, grid, px, py):
        """
        Main update — call once per game tick.
        Returns new EnemyBullet or None.
        px, py = player's current (x, y).
        """
        if not self.alive:
            return None

        self._tick  += 1
        self._fire  += 1
        self._bfs_t += 1

        new_bullet = None

        # Periodic BFS refresh
        if self._bfs_t >= self.BFS_EVERY:
            self._recompute_bfs(grid)
            self._bfs_t = 0

        can_shoot = (
            self._fire >= self.FIRE_RATE and
            (self.bullet is None or not self.bullet.alive)
        )

        # ── RULE 1: Shoot player if in LOS ──
        los, shoot_dir = self._line_of_sight(grid, px, py)
        if los and can_shoot:
            self.direction = shoot_dir
            self._fire     = 0
            new_bullet     = EnemyBullet(self.x, self.y, shoot_dir, self)
            self.bullet    = new_bullet
            return new_bullet   # skip movement this tick

        # ── Movement throttle ──
        if self._tick < self.SPEED:
            return None
        self._tick = 0

        # ── RULE 2: Shoot brick ahead on path ──
        if self.path:
            nx, ny = self.path[0]
            if grid[ny][nx] == BRICK:
                dx, dy         = nx - self.x, ny - self.y
                self.direction = (dx, dy)
                if can_shoot:
                    self._fire  = 0
                    new_bullet  = EnemyBullet(self.x, self.y, self.direction, self)
                    self.bullet = new_bullet
                return new_bullet   # don't move this tick

        # ── RULE 3: Move along BFS path ──
        if self.path:
            nx, ny = self.path[0]
            if grid[ny][nx] in PASSABLE:
                dx, dy         = nx - self.x, ny - self.y
                self.direction = (dx, dy)
                self.x, self.y = nx, ny
                self.path.pop(0)
            else:
                # path blocked by non-brick (steel/water appeared) — recompute
                self._recompute_bfs(grid)
        else:
            # No path — turn to a random free direction
            dirs = list(ALL_DIRS)
            random.shuffle(dirs)
            for dx, dy in dirs:
                nx, ny = self.x + dx, self.y + dy
                if 0 <= nx < GRID_W and 0 <= ny < GRID_H and grid[ny][nx] in PASSABLE:
                    self.direction = (dx, dy)
                    self.x, self.y = nx, ny
                    break

        return new_bullet

    def take_damage(self):
        self.hp -= 1
        if self.hp <= 0:
            self.alive = False

    def draw(self, surface):
        import pygame
        if not self.alive:
            return
        bx, by = self.x * TILE_SIZE, self.y * TILE_SIZE
        pygame.draw.rect(surface, self.COLOR, (bx + 2, by + 2, TILE_SIZE - 4, TILE_SIZE - 4))
        # Direction nub
        dx, dy = self.direction
        cx = bx + TILE_SIZE // 2 + dx * 7
        cy = by + TILE_SIZE // 2 + dy * 7
        pygame.draw.rect(surface, (255, 180, 180), (cx - 3, cy - 3, 6, 6))


# ────────────────────
#  FastTankStub  — 
# ────────────────────
class FastTankStub:
    """
    Phase 3 placeholder. Moves randomly, shoots occasionally.
    Will be replaced by Greedy Best-First Agent in Phase 4.
    """
    COLOR     = (60, 200, 220)
    HP        = 1
    SPEED     = 2    # faster: moves every 2 ticks
    FIRE_RATE = 15   # ~1.5s at FPS=10

    def __init__(self, x, y):
        self.x   = x
        self.y   = y
        self.hp  = self.HP
        self.direction = DIR_DOWN
        self.alive     = True
        self._tick  = 0
        self._fire  = 0
        self.bullet = None

    def on_spawn(self, grid):
        pass

    def on_map_changed(self, grid, destroyed_xy):
        pass

    def update(self, grid, px, py):
        if not self.alive:
            return None

        self._tick += 1
        self._fire += 1

        # Movement
        if self._tick >= self.SPEED:
            self._tick = 0
            dirs = list(ALL_DIRS)
            random.shuffle(dirs)
            for dx, dy in dirs:
                nx, ny = self.x + dx, self.y + dy
                if 0 <= nx < GRID_W and 0 <= ny < GRID_H and grid[ny][nx] in PASSABLE:
                    self.direction = (dx, dy)
                    self.x, self.y = nx, ny
                    break

        # Occasional random shot
        can_shoot = (
            self._fire >= self.FIRE_RATE and
            (self.bullet is None or not self.bullet.alive)
        )
        if can_shoot and random.random() < 0.4:
            self._fire  = 0
            b           = EnemyBullet(self.x, self.y, self.direction, self)
            self.bullet = b
            return b

        return None

    def take_damage(self):
        self.hp -= 1
        if self.hp <= 0:
            self.alive = False

    def draw(self, surface):
        import pygame
        if not self.alive:
            return
        bx, by = self.x * TILE_SIZE, self.y * TILE_SIZE
        pygame.draw.rect(surface, self.COLOR, (bx + 2, by + 2, TILE_SIZE - 4, TILE_SIZE - 4))
        dx, dy = self.direction
        cx = bx + TILE_SIZE // 2 + dx * 7
        cy = by + TILE_SIZE // 2 + dy * 7
        pygame.draw.rect(surface, (180, 240, 255), (cx - 3, cy - 3, 6, 6))


# ──────────────────────
#  SpawnManager
# ──────────────────────
class SpawnManager:
    """
    Manages the 20-tank pool for a level.
    Level 1: 7 BasicTank + 5 FastTankStub + 8 BasicTank (all 20 defined)
    At most MAX_ACTIVE tanks on map simultaneously.
    Spawns with 1.5s delay (15 ticks at FPS=10).
    Fairness: won't spawn within Manhattan distance 10 of player.
    """
    MAX_ACTIVE    = 4
    SPAWN_DELAY   = 15   # 1.5s at FPS=10
    SAFE_DIST     = 10

    def __init__(self, level=1):
        self.level        = level
        self.pool         = self._build_pool(level)
        self.pool_index   = 0
        self.active       = []        # currently on-map tank objects
        self.all_bullets  = []        # flat list of all live enemy bullets
        self._spawn_idx   = 0         # rotates 0,1,2 through SPAWN_POINTS
        self._spawn_timer = 0
        self.total_killed = 0
        self.eagle_hit    = False     # set True if enemy bullet hits Eagle

    def _build_pool(self, level):
        if level == 1:
            # 7 Basic first, then 5 Fast stubs, then 8 more Basic = 20 total
            return (["basic"] * 7) + (["fast"] * 5) + (["basic"] * 8)
        return ["basic"] * 20

    @staticmethod
    def _manhattan(x1, y1, x2, y2):
        return abs(x1 - x2) + abs(y1 - y2)

    def _pick_spawn(self, px, py):
        for _ in range(3):
            sp = SPAWN_POINTS[self._spawn_idx % 3]
            self._spawn_idx += 1
            if self._manhattan(sp[0], sp[1], px, py) >= self.SAFE_DIST:
                return sp
        # fallback — use next regardless
        sp = SPAWN_POINTS[self._spawn_idx % 3]
        self._spawn_idx += 1
        return sp

    def _make_tank(self, tank_type, x, y):
        if tank_type == "basic":
            return BasicTank(x, y)
        return FastTankStub(x, y)

    def update(self, grid, px, py, all_tanks_for_collision):
        """
        Call once per game tick.
        grid        — current game_map (list of lists, may be mutated by bullets)
        px, py      — player's current (x, y)
        all_tanks_for_collision — list of ALL tank objects (player + enemies) for bullet collision

        Returns list of EnemyBullet objects fired this tick.
        """
        new_bullets = []

        # ── Try to spawn ──
        if len(self.active) < self.MAX_ACTIVE and self.pool_index < len(self.pool):
            self._spawn_timer += 1
            if self._spawn_timer >= self.SPAWN_DELAY:
                self._spawn_timer = 0
                sp        = self._pick_spawn(px, py)
                tank_type = self.pool[self.pool_index]
                tank      = self._make_tank(tank_type, sp[0], sp[1])
                tank.on_spawn(grid)
                self.active.append(tank)
                self.pool_index += 1

        # ── Update tanks ──
        for tank in self.active:
            b = tank.update(grid, px, py)
            if b:
                new_bullets.append(b)
                self.all_bullets.append(b)

        # ── Advance bullets (2 steps per tick for 2x speed) ──
        combined_bullets = self.all_bullets[:]   # snapshot for collision checks
        for _ in range(2):
            for b in self.all_bullets:
                if b.alive:
                    b.advance_step(grid, all_tanks_for_collision, combined_bullets)
                    # Check eagle hit flag
                    if hasattr(b, '_hit_eagle') and b._hit_eagle:
                        self.eagle_hit = True

        # ── Remove dead bullets ──
        self.all_bullets = [b for b in self.all_bullets if b.alive]

        # ── Remove dead tanks ──
        killed = [t for t in self.active if not t.alive]
        self.total_killed += len(killed)
        self.active = [t for t in self.active if t.alive]

        # Return only bullets fired this tick that are still alive
        return [b for b in new_bullets if b.alive]

    def notify_map_changed(self, grid, destroyed_xy):
        """Call whenever a brick tile is destroyed (by player bullet or enemy bullet)."""
        for tank in self.active:
            tank.on_map_changed(grid, destroyed_xy)

    def all_defeated(self):
        return self.pool_index >= len(self.pool) and len(self.active) == 0

    def remaining_count(self):
        """Total enemies not yet destroyed (in pool + active on map)."""
        return (len(self.pool) - self.pool_index) + len(self.active)

    def draw(self, surface):
        for tank in self.active:
            tank.draw(surface)
        for b in self.all_bullets:
            b.draw(surface)
