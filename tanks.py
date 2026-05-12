import random
from collections import deque
from constants import (
    GRID_SIZE, FPS,
    EMPTY, BRICK, STEEL, WATER, FOREST, EAGLE,
    UP, DOWN, LEFT, RIGHT, DIRS,
    SPAWN_PLAYER, EAGLE_POS,
    TANK_COLORS,
)
from bullet import Bullet
from search import greedy_next_step, astar, minimax_decision


# ══════════════════════════════════════════════════════════════════════
#  BFS — open tiles only (EMPTY + FOREST)
#  Per spec: "BFS treats all passable tiles (Empty, Forest) as equal
#             cost=1. It does NOT consider shooting through brick."
#  Goal: reach a tile ADJACENT to Eagle (Eagle is surrounded by brick
#        protection, so adjacency is the reachable target).
# ══════════════════════════════════════════════════════════════════════
def bfs_to_eagle(grid, start):
    """
    BFS through Empty and Forest tiles only.
    Returns shortest path (list of (x,y) steps) to any tile adjacent
    to the Eagle, or [] if no open path exists.
    """
    sx, sy = start
    gx, gy = EAGLE_POS

    # Goal = Eagle tile OR any empty/forest tile directly adjacent to it
    goal_set = set()
    goal_set.add((gx, gy))
    for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
        nx, ny = gx+dx, gy+dy
        if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
            if grid[ny][nx] in (EMPTY, FOREST, EAGLE):
                goal_set.add((nx, ny))

    if (sx, sy) in goal_set:
        return []

    visited = {(sx, sy): None}
    queue   = deque([(sx, sy)])

    while queue:
        x, y = queue.popleft()
        if (x, y) in goal_set:
            path, cur = [], (x, y)
            while cur != (sx, sy):
                path.append(cur)
                cur = visited[cur]
            return list(reversed(path))

        # Explore in order: down, right, left, up (bias toward Eagle)
        for dx, dy in [(0,1),(1,0),(-1,0),(0,-1)]:
            nx, ny = x+dx, y+dy
            if (nx, ny) in visited:
                continue
            if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
                continue
            t = grid[ny][nx]
            # Only traverse Empty and Forest — NOT brick
            if t in (EMPTY, FOREST):
                visited[(nx, ny)] = (x, y)
                queue.append((nx, ny))

    return []  # No open path found


# ══════════════════════════════════════════════════════════════════════
#  Base Tank
# ══════════════════════════════════════════════════════════════════════
class Tank:
    def __init__(self, x, y, tank_type='basic'):
        self.x           = x
        self.y           = y
        self.dir         = DOWN
        self.type        = tank_type
        self.hp          = 1
        self.max_hp      = 1
        self.alive       = True
        self.speed       = 4
        self.fire_rate   = 90
        self._mv_tick    = 0
        self._fr_tick    = 0
        self.bullet      = None
        self.flash_timer = 0
        # Position history for oscillation detection
        self._pos_history = []
        self._osc_timer   = 0    # ticks since last forced direction change

    def _tick_move(self):
        self._mv_tick += 1
        if self._mv_tick >= self.speed:
            self._mv_tick = 0
            return True
        return False

    def _fire_ready(self):
        return (self._fr_tick >= self.fire_rate
                and (self.bullet is None or not self.bullet.alive))

    def _tick_fire_timer(self):
        if self._fr_tick < self.fire_rate:
            self._fr_tick += 1

    def _consume_fire(self):
        self._fr_tick = 0

    def try_move(self, dx, dy, grid, all_tanks):
        nx, ny = self.x + dx, self.y + dy
        if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
            return False
        t = grid[ny][nx]
        if t in (STEEL, WATER, EAGLE, BRICK):
            return False
        for other in all_tanks:
            if other is self or not other.alive:
                continue
            if other.x == nx and other.y == ny:
                return False
        self.x, self.y = nx, ny
        return True

    def shoot(self, owner_type=None):
        """
        Bullet spawns AT the tank tile and moves in self.dir.
        This ensures the first tile it checks is the one directly ahead,
        correctly destroying adjacent brick walls.
        """
        ot = owner_type or ('player' if self.type == 'player' else 'enemy')
        # Bullet starts at tank position, travels outward
        self.bullet = Bullet(self.x, self.y, self.dir, owner_type=ot, owner=self)
        self._consume_fire()
        return self.bullet

    def take_hit(self):
        if not self.alive:
            return
        self.hp -= 1
        self.flash_timer = 12
        if self.hp <= 0:
            self.alive = False

    def _los(self, tx, ty, grid):
        """Line of sight: same row or col, no solid walls between."""
        if self.x == tx:
            step = 1 if ty > self.y else -1
            for y in range(self.y + step, ty, step):
                if grid[y][self.x] in (BRICK, STEEL, WATER):
                    return False
            return True
        if self.y == ty:
            step = 1 if tx > self.x else -1
            for x in range(self.x + step, tx, step):
                if grid[self.y][x] in (BRICK, STEEL, WATER):
                    return False
            return True
        return False

    def _aim_at(self, tx, ty):
        dx, dy = tx - self.x, ty - self.y
        if abs(dx) >= abs(dy):
            self.dir = RIGHT if dx > 0 else LEFT
        else:
            self.dir = DOWN if dy > 0 else UP

    def _try_shoot_eagle(self, grid):
        """
        Highest priority rule for all enemy tanks:
        IF the Eagle is in an adjacent tile -> aim at it -> shoot.
        Returns bullet or None.
        Per spec: any bullet hitting Eagle = instant game over.
        """
        ex, ey = EAGLE_POS
        for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            if self.x + dx == ex and self.y + dy == ey:
                self.dir = (dx, dy)
                if self._fire_ready():
                    return self.shoot()
        return None

    def _record_position(self):
        """Track last 8 positions to detect oscillation."""
        self._pos_history.append((self.x, self.y))
        if len(self._pos_history) > 8:
            self._pos_history.pop(0)

    def _is_oscillating(self):
        """True if tank is bouncing between ≤2 positions."""
        if len(self._pos_history) < 6:
            return False
        unique = set(self._pos_history[-6:])
        return len(unique) <= 2

    def _escape_oscillation(self, grid, all_tanks):
        """
        When oscillating, move to a tile NOT in the recent position history.
        Prefer lateral (sideways) moves to break the oscillation pattern.
        Sets a longer cooldown so greedy doesn't immediately undo the escape.
        """
        ex, ey = EAGLE_POS
        recent = set(self._pos_history)

        # Priority 1: sideways moves to tiles NOT recently visited
        # Priority 2: any move to a new tile
        # Priority 3: any valid move at all
        candidates = []
        for d in DIRS:
            nx, ny = self.x + d[0], self.y + d[1]
            if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
                continue
            t = grid[ny][nx]
            if t in (STEEL, WATER, EAGLE, BRICK):
                continue
            # Check tank collision
            blocked = any(
                other is not self and other.alive and other.x == nx and other.y == ny
                for other in all_tanks
            )
            if blocked:
                continue
            not_visited = (nx, ny) not in recent
            is_lateral   = (d[0] != 0)   # horizontal = lateral
            h = abs(nx - ex) + abs(ny - ey)
            # Score: prefer not-visited, prefer lateral, prefer closer to Eagle
            score = (int(not_visited) * 100 + int(is_lateral) * 10 - h)
            candidates.append((score, d, nx, ny))

        if not candidates:
            return False

        candidates.sort(key=lambda c: -c[0])  # highest score first
        _, best_dir, bx, by = candidates[0]
        self.x, self.y = bx, by
        self.dir = best_dir
        self._pos_history.clear()
        self._osc_timer = 30  # 1 second cooldown at 30fps
        return True

    def decide(self, grid, player, all_tanks):
        return None


# ══════════════════════════════════════════════════════════════════════
#  Player Tank
# ══════════════════════════════════════════════════════════════════════
class PlayerTank(Tank):
    def __init__(self):
        super().__init__(*SPAWN_PLAYER, 'player')
        self.dir       = UP
        self.speed     = 2
        self.fire_rate = 18
        self.lives     = 10

    def handle_input(self, keys, grid, all_tanks):
        import pygame
        self._tick_fire_timer()
        moved = False
        for key, direction in [
            (pygame.K_UP,    UP),   (pygame.K_w,    UP),
            (pygame.K_DOWN,  DOWN), (pygame.K_s,    DOWN),
            (pygame.K_LEFT,  LEFT), (pygame.K_a,    LEFT),
            (pygame.K_RIGHT, RIGHT),(pygame.K_d,    RIGHT),
        ]:
            if keys[key]:
                self.dir = direction
                if self._tick_move():
                    self.try_move(*direction, grid, all_tanks)
                moved = True
                break
        if not moved:
            self._mv_tick = 0
        if self.flash_timer > 0:
            self.flash_timer -= 1
        bullet = None
        if keys[pygame.K_SPACE] or keys[pygame.K_j]:
            if self._fire_ready():
                bullet = self.shoot('player')
        return bullet

    def respawn(self):
        self.x, self.y  = SPAWN_PLAYER
        self.alive       = True
        self.hp          = 1
        self.dir         = UP
        self.bullet      = None
        self._mv_tick    = 0
        self._fr_tick    = 0

    def lose_life(self):
        self.lives -= 1
        if self.lives > 0:
            self.respawn()
            return True
        return False


# ══════════════════════════════════════════════════════════════════════
#  TANK TYPE 1 — Basic Tank
#  Simple Reflex Agent + BFS
#
#  Spec rules (implemented exactly):
#  Primary Rule : IF player in same row/col AND LoS → shoot player
#  Movement Rule: follow BFS path (Empty+Forest). ELSE random free dir.
#  Wall Rule    : IF next tile in current dir is Brick → shoot it.
#
#  BFS re-trigger: at spawn, every 5s, when path tile is blocked.
# ══════════════════════════════════════════════════════════════════════
class BasicTank(Tank):
    REPLAN_TICKS = 5 * FPS

    def __init__(self, x, y):
        super().__init__(x, y, 'basic')
        self.speed     = 4
        self.fire_rate = 90
        self._path     = []
        self._path_age = self.REPLAN_TICKS   # triggers replan on first tick
        self._stuck    = 0

    def decide(self, grid, player, all_tanks):
        self._tick_fire_timer()

        # ── HIGHEST PRIORITY: shoot Eagle if adjacent ────────────────
        bullet = self._try_shoot_eagle(grid)
        if bullet:
            if self.flash_timer > 0: self.flash_timer -= 1
            return bullet

        bullet = None

        # ── Replan BFS every 5s (accounts for map changes) ──────────
        self._path_age += 1
        if self._path_age >= self.REPLAN_TICKS:
            self._path     = bfs_to_eagle(grid, (self.x, self.y))
            self._path_age = 0

        # ── Primary Rule: shoot player if in line-of-sight ──────────
        if self._fire_ready() and self._los(player.x, player.y, grid):
            self._aim_at(player.x, player.y)
            bullet = self.shoot()

        # ── Movement ────────────────────────────────────────────────
        if self._osc_timer > 0:
            self._osc_timer -= 1

        if self._tick_move():
            self._record_position()

            # Escape oscillation (e.g. trapped by water causing back-and-forth)
            if self._osc_timer == 0 and self._is_oscillating():
                self._path = []  # clear stale path
                self._escape_oscillation(grid, all_tanks)

            elif self._path:
                nx, ny   = self._path[0]
                ddx, ddy = nx - self.x, ny - self.y
                self.dir = (ddx, ddy)

                # Check what's at the next tile
                tile = grid[ny][nx]
                if tile == BRICK:
                    # Wall Rule: shoot brick blocking path
                    if bullet is None and self._fire_ready():
                        bullet = self.shoot()
                    # Don't move — wait for brick to be destroyed
                    # Replan once brick is gone
                    if grid[ny][nx] != BRICK:
                        self._path.pop(0)
                elif self.try_move(ddx, ddy, grid, all_tanks):
                    self._path.pop(0)
                    self._stuck = 0
                else:
                    # Blocked by another tank — wait, then replan
                    self._stuck += 1
                    if self._stuck >= 8:
                        self._path     = bfs_to_eagle(grid, (self.x, self.y))
                        self._path_age = 0
                        self._stuck    = 0
            else:
                # Movement Rule: no open BFS path → try random free direction
                dirs_shuffled = list(DIRS)
                random.shuffle(dirs_shuffled)
                moved = False
                for d in dirs_shuffled:
                    if self.try_move(*d, grid, all_tanks):
                        self.dir = d
                        moved = True
                        break

                if not moved:
                    # Truly surrounded — Wall Rule: shoot brick toward Eagle
                    gx, gy = EAGLE_POS
                    dx, dy = gx - self.x, gy - self.y
                    if abs(dy) >= abs(dx):
                        self.dir = DOWN if dy > 0 else UP
                    else:
                        self.dir = RIGHT if dx > 0 else LEFT
                    nx, ny = self.x + self.dir[0], self.y + self.dir[1]
                    if (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE
                            and grid[ny][nx] == BRICK
                            and bullet is None and self._fire_ready()):
                        bullet = self.shoot()

        # ── Wall Rule: shoot brick directly ahead (any time) ─────────
        if bullet is None and self._fire_ready():
            nx, ny = self.x + self.dir[0], self.y + self.dir[1]
            if (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE
                    and grid[ny][nx] == BRICK):
                bullet = self.shoot()

        if self.flash_timer > 0:
            self.flash_timer -= 1
        return bullet


# ══════════════════════════════════════════════════════════════════════
#  TANK TYPE 2 — Fast Tank
#  Goal-Based Agent + Greedy Best-First
#
#  Spec: "picks neighbour tile with lowest Manhattan distance to Eagle"
#  "Does NOT compute full path — single step per tick"
#  "Does NOT engage player — ignores completely"
#  "IF next tile is Brick → shoot it. Do NOT detour."
#  Local minima = intentional (pedagogical)
# ══════════════════════════════════════════════════════════════════════
class FastTank(Tank):
    def __init__(self, x, y):
        super().__init__(x, y, 'fast')
        self.speed     = 2
        self.fire_rate = 45
        self._stuck    = 0

    def decide(self, grid, player, all_tanks):
        self._tick_fire_timer()

        # ── HIGHEST PRIORITY: shoot Eagle if adjacent ────────────────
        bullet = self._try_shoot_eagle(grid)
        if bullet:
            if self.flash_timer > 0: self.flash_timer -= 1
            return bullet

        bullet = None

        # Oscillation cooldown countdown
        if self._osc_timer > 0:
            self._osc_timer -= 1

        if self._tick_move():
            self._record_position()

            # Escape oscillation: greedy got stuck bouncing (e.g. blocked by water)
            if self._osc_timer == 0 and self._is_oscillating():
                self._escape_oscillation(grid, all_tanks)
                if self.flash_timer > 0: self.flash_timer -= 1
                return bullet

            nxt = greedy_next_step(grid, (self.x, self.y), EAGLE_POS)

            if nxt:
                nx, ny   = nxt
                tile     = grid[ny][nx]
                ddx, ddy = nx - self.x, ny - self.y
                self.dir = (ddx, ddy)

                if tile == BRICK:
                    # Wall Rule: shoot it, do NOT detour
                    if self._fire_ready():
                        bullet = self.shoot()
                elif self.try_move(ddx, ddy, grid, all_tanks):
                    self._stuck = 0
                else:
                    # Blocked by tank — nudge
                    self._stuck += 1
                    if self._stuck > 5:
                        dirs = list(DIRS)
                        random.shuffle(dirs)
                        for d in dirs:
                            if self.try_move(*d, grid, all_tanks):
                                self.dir = d
                                break
                        self._stuck = 0
            else:
                # At goal or surrounded
                if self._fire_ready():
                    bullet = self.shoot()

        # Wall Rule: shoot brick directly ahead
        if bullet is None and self._fire_ready():
            nx, ny = self.x + self.dir[0], self.y + self.dir[1]
            if (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE
                    and grid[ny][nx] == BRICK):
                bullet = self.shoot()

        if self.flash_timer > 0:
            self.flash_timer -= 1
        return bullet


# ══════════════════════════════════════════════════════════════════════
#  TANK TYPE 3 — Armor Tank
#  Model-Based Reflex + A*
#
#  State: hitCount (0-3). On 3rd hit → retreat to steel cover.
#  A* costs: empty=1, forest=1, brick=3, steel=inf, water=inf
# ══════════════════════════════════════════════════════════════════════
class ArmorTank(Tank):
    REPLAN_TICKS = 5 * FPS
    COVER_WAIT   = 2 * FPS

    def __init__(self, x, y):
        super().__init__(x, y, 'armor')
        self.hp          = 4
        self.max_hp      = 4
        self.speed       = 3
        self.fire_rate   = 60
        self._path       = []
        self._path_age   = self.REPLAN_TICKS
        self._retreating = False
        self._cover_pos  = None
        self._cover_wait = 0
        self._stuck      = 0

    def take_hit(self):
        prev = self.hp
        super().take_hit()
        # Trigger retreat on 3rd hit (hp: 2→1)
        if self.alive and prev == 2:
            self._retreating = True
            self._cover_pos  = None
            self._cover_wait = 0
            self._path       = []

    def decide(self, grid, player, all_tanks):
        self._tick_fire_timer()

        # ── HIGHEST PRIORITY: shoot Eagle if adjacent ────────────────
        bullet = self._try_shoot_eagle(grid)
        if bullet:
            if self.flash_timer > 0: self.flash_timer -= 1
            return bullet

        bullet = None

        if not self._retreating:
            # ── A* navigation toward Eagle ───────────────────────────
            self._path_age += 1
            if self._path_age >= self.REPLAN_TICKS:
                self._path     = astar(grid, (self.x, self.y), EAGLE_POS)
                self._path_age = 0

            # Shoot player on LoS
            if self._fire_ready() and self._los(player.x, player.y, grid):
                self._aim_at(player.x, player.y)
                bullet = self.shoot()

            if self._osc_timer > 0:
                self._osc_timer -= 1

            if self._tick_move():
                self._record_position()

                if self._osc_timer == 0 and self._is_oscillating():
                    self._path = []
                    self._escape_oscillation(grid, all_tanks)
                elif self._path:
                    nx, ny   = self._path[0]
                    tile     = grid[ny][nx]
                    ddx, ddy = nx - self.x, ny - self.y
                    self.dir = (ddx, ddy)

                    if tile == BRICK:
                        # A* chose to drill through brick (cost 3 < long detour)
                        if bullet is None and self._fire_ready():
                            bullet = self.shoot()
                        if grid[ny][nx] != BRICK:
                            self._path.pop(0)
                    elif self.try_move(ddx, ddy, grid, all_tanks):
                        self._path.pop(0)
                        self._stuck = 0
                    else:
                        self._stuck += 1
                        if self._stuck >= 8:
                            self._path     = astar(grid, (self.x, self.y), EAGLE_POS)
                            self._path_age = 0
                            self._stuck    = 0
                else:
                    # No A* path — random
                    dirs = list(DIRS)
                    random.shuffle(dirs)
                    for d in dirs:
                        if self.try_move(*d, grid, all_tanks):
                            self.dir = d
                            break

            # Wall Rule
            if bullet is None and self._fire_ready():
                nx, ny = self.x + self.dir[0], self.y + self.dir[1]
                if (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE
                        and grid[ny][nx] == BRICK):
                    bullet = self.shoot()

        else:
            # ── Retreat to nearest steel cover ───────────────────────
            if self._cover_pos is None:
                self._cover_pos = self._find_cover(grid)
                if self._cover_pos:
                    self._path = bfs_to_eagle(grid, (self.x, self.y))

            if self._cover_pos and (self.x, self.y) == self._cover_pos:
                self._cover_wait += 1
                if self._cover_wait >= self.COVER_WAIT:
                    self._retreating = False
                    self._cover_pos  = None
                    self._path       = astar(grid, (self.x, self.y), EAGLE_POS)
                    self._path_age   = 0
            elif self._tick_move() and self._path:
                nx, ny   = self._path[0]
                ddx, ddy = nx - self.x, ny - self.y
                self.dir = (ddx, ddy)
                if self.try_move(ddx, ddy, grid, all_tanks):
                    self._path.pop(0)

        if self.flash_timer > 0:
            self.flash_timer -= 1
        return bullet

    def _find_cover(self, grid):
        """BFS to nearest empty cell adjacent to a steel wall."""
        visited = {(self.x, self.y)}
        q = deque([(self.x, self.y)])
        while q:
            x, y = q.popleft()
            for dx, dy in DIRS:
                nx, ny = x+dx, y+dy
                if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
                    continue
                if grid[ny][nx] == STEEL:
                    return (x, y)
                if (nx, ny) not in visited and grid[ny][nx] in (EMPTY, FOREST):
                    visited.add((nx, ny))
                    q.append((nx, ny))
        return None


# ══════════════════════════════════════════════════════════════════════
#  TANK TYPE 4 — Power Tank (Utility-Based + A*)
# ══════════════════════════════════════════════════════════════════════
class PowerTank(Tank):
    def __init__(self, x, y):
        super().__init__(x, y, 'power')
        self.hp        = 2
        self.max_hp    = 2
        self.speed     = 3
        self.fire_rate = 40
        self._path     = []
        self._path_age = 5 * FPS
        self._stuck    = 0

    def decide(self, grid, player, all_tanks):
        self._tick_fire_timer()

        # ── HIGHEST PRIORITY: shoot Eagle if adjacent ────────────────
        bullet = self._try_shoot_eagle(grid)
        if bullet:
            if self.flash_timer > 0: self.flash_timer -= 1
            return bullet

        bullet = None

        self._path_age += 1
        if self._path_age >= 5 * FPS:
            self._path     = astar(grid, (self.x, self.y), EAGLE_POS)
            self._path_age = 0

        if self._fire_ready() and self._los(player.x, player.y, grid):
            self._aim_at(player.x, player.y)
            bullet = self.shoot()

        if self._tick_move():
            if self._path:
                nx, ny   = self._path[0]
                tile     = grid[ny][nx]
                ddx, ddy = nx - self.x, ny - self.y
                self.dir = (ddx, ddy)
                if tile == BRICK:
                    if bullet is None and self._fire_ready():
                        bullet = self.shoot()
                    if grid[ny][nx] != BRICK:
                        self._path.pop(0)
                elif self.try_move(ddx, ddy, grid, all_tanks):
                    self._path.pop(0)
                    self._stuck = 0
                else:
                    self._stuck += 1
                    if self._stuck >= 8:
                        self._path     = astar(grid, (self.x, self.y), EAGLE_POS)
                        self._path_age = 0
                        self._stuck    = 0
            else:
                dirs = list(DIRS)
                random.shuffle(dirs)
                for d in dirs:
                    if self.try_move(*d, grid, all_tanks):
                        self.dir = d
                        break

        if bullet is None and self._fire_ready():
            nx, ny = self.x + self.dir[0], self.y + self.dir[1]
            if (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE
                    and grid[ny][nx] == BRICK):
                bullet = self.shoot()

        if self.flash_timer > 0:
            self.flash_timer -= 1
        return bullet


# ══════════════════════════════════════════════════════════════════════
#  BOSS TANK — Tank Commander
#  Adversarial Agent: Minimax + Alpha-Beta, phase system
# ══════════════════════════════════════════════════════════════════════
class BossTank(Tank):
    def __init__(self, x, y):
        super().__init__(x, y, 'boss')
        self.hp         = 10
        self.max_hp     = 10
        self.phase      = 1
        self._depth     = 2
        self._dec_timer = 0
        self._dec_every = 8
        self._last_act  = None

    def _update_phase(self):
        if self.hp >= 7:
            self.phase = 1; self.speed = 5; self.fire_rate = 60; self._depth = 2
        elif self.hp >= 3:
            self.phase = 2; self.speed = 3; self.fire_rate = 45; self._depth = 3
        else:
            self.phase = 3; self.speed = 2; self.fire_rate = 24; self._depth = 4

    def decide(self, grid, player, all_tanks):
        self._update_phase()
        self._tick_fire_timer()
        bullet = None

        self._dec_timer += 1
        if self._dec_timer >= self._dec_every:
            self._dec_timer = 0
            boss_s   = {'x': self.x, 'y': self.y, 'hp': self.hp}
            player_s = {'x': player.x, 'y': player.y, 'hp': player.lives}
            self._last_act = minimax_decision(boss_s, player_s, grid, self._depth)

        act = self._last_act
        if act == 'shoot' or act is None:
            self._aim_at(player.x, player.y)
            if self._fire_ready():
                bullet = self.shoot()
        else:
            dx, dy = act
            self.dir = (dx, dy)
            if self._tick_move():
                if not self.try_move(dx, dy, grid, all_tanks):
                    dirs = list(DIRS)
                    random.shuffle(dirs)
                    for d in dirs:
                        if self.try_move(*d, grid, all_tanks):
                            self.dir = d
                            break

        if self.flash_timer > 0:
            self.flash_timer -= 1
        return bullet