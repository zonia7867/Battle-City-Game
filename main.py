

import sys, random
import pygame

from constants import (
    GRID_SIZE, TILE_SIZE, SCREEN_W, SCREEN_H, FPS,
    EMPTY, BRICK, STEEL, WATER, FOREST, EAGLE,
    EAGLE_POS, SPAWN_PLAYER, SPAWN_ENEMY,
    MAX_ACTIVE_ENEMIES, SPAWN_FAIRNESS_DIST,
)
from csp_map  import CSPMapGenerator
from bullet   import Bullet
from tanks    import PlayerTank, BasicTank, FastTank, ArmorTank, PowerTank, BossTank
from renderer import Renderer
from search   import reset_minimax_stats

TANK_FACTORIES = {
    "basic": BasicTank,
    "fast" : FastTank,
    "armor": ArmorTank,
    "power": PowerTank,
}

# ── Game states ───────────────────────────────────────────────────────
PLAYING    = "playing"
PAUSED     = "paused"
TRANSITION = "transition"
GAME_OVER  = "game_over"
YOU_WIN    = "you_win"
MENU       = "menu"
LOADING    = "loading"

TRANSITION_SECS = 3
LOADING_SECS    = 2.0


# ══════════════════════════════════════════════════════════════════════
#  Boss Arena  (spec: small closed arena, steel border, mixed terrain)
# ══════════════════════════════════════════════════════════════════════
def _build_boss_arena():
    E, B, S, W, F, G = EMPTY, BRICK, STEEL, WATER, FOREST, EAGLE
    grid = [[E]*GRID_SIZE for _ in range(GRID_SIZE)]

    # Steel outer border
    for x in range(GRID_SIZE):
        grid[0][x] = S; grid[GRID_SIZE-1][x] = S
    for y in range(GRID_SIZE):
        grid[y][0] = S; grid[y][GRID_SIZE-1] = S

    # Eagle + 1-ring brick protection
    ex, ey = EAGLE_POS
    grid[ey][ex] = G
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            nx, ny = ex+dx, ey+dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and grid[ny][nx] == E:
                grid[ny][nx] = B

    # Steel pillars (4 symmetrical groups)
    for px, py in [(4,4),(4,20),(20,4),(20,20),(8,10),(16,10),(8,15),(16,15)]:
        for dy in range(2):
            for dx in range(2):
                nx, ny = px+dx, py+dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                    grid[ny][nx] = S

    # Brick walls (breakable cover)
    for bx, by, bw, bh in [(6,7,4,1),(15,7,4,1),(6,18,4,1),(15,18,4,1),(10,12,5,1)]:
        for dy in range(bh):
            for dx in range(bw):
                nx, ny = bx+dx, by+dy
                if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and grid[ny][nx] == E:
                    grid[ny][nx] = B

    # Water patch (centre)
    for dy in range(2):
        for dx in range(3):
            grid[12+dy][11+dx] = W

    # Forest patches
    for fx, fy in [(3,12),(22,12),(12,5),(12,20)]:
        if grid[fy][fx] == E: grid[fy][fx] = F

    # Clear spawns & player start
    for sx, sy in SPAWN_ENEMY:
        grid[sy][sx] = E
    px, py = SPAWN_PLAYER
    grid[py][px] = E

    return grid


# ══════════════════════════════════════════════════════════════════════
#  Main Game
# ══════════════════════════════════════════════════════════════════════
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Battle City — AZM")
        self.screen   = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock    = pygame.time.Clock()
        self.renderer = Renderer(self.screen)
        self.player   = PlayerTank()
        self._state    = MENU
        self._menu_sel = 0
        self._pending_level   = 0
        self._loading_caption = ""
        self._loading_frames  = 0
        self._loading_total   = max(1, int(FPS * LOADING_SECS))

    # ──────────────────────────────────────────────────────────────────
    #  Level loading
    # ──────────────────────────────────────────────────────────────────

    def _load_level(self, idx, show_transition=True):
        self._idx = idx

        # Common reset
        self.player.respawn()
        self._enemies:    list = []
        self._bullets:    list = []
        self._explosions: list = []   # [x, y, timer, max_timer]
        self._eagle_dead       = False
        self._kills            = 0
        self._spawn_ptr        = 0
        self._spawn_timer      = 0
        self._spawn_delay      = int(FPS * 1.5)
        self._boss             = None
        self._fast_gated       = False
        self._fast_gate_kills  = 0

        if idx == 0:
            self._setup_level1()
        elif idx == 1:
            self._setup_level2()
        elif idx == 2:
            self._setup_boss()
        else:
            self._state = YOU_WIN
            return

        reset_minimax_stats()
        if show_transition:
            self._state   = TRANSITION
            self._trans_t = TRANSITION_SECS * FPS
        else:
            self._state = PLAYING

    def _start_loading_to_level(self, idx):
        self._pending_level = idx
        caps = {
            0: "Loading Level 1 — Brick Maze",
            1: "Loading Level 2 — Steel Fortress",
            2: "Loading Boss Level — Tank Commander",
        }
        self._loading_caption = caps.get(idx, "Loading…")
        self._loading_frames  = 0
        self._loading_total    = max(1, int(FPS * LOADING_SECS))
        self._state            = LOADING

    # ── Level 1 ───────────────────────────────────────────────────────
    def _setup_level1(self):
        self._level_num  = 1
        self._level_name = "Brick Maze"
        self._is_boss    = False

        # CSP: dense brick maze
        gen        = CSPMapGenerator(level=1)
        self._grid = gen.generate()

        # Pool per spec: 7 Basic + 5 Fast + 8 Basic = 20
        # "Fast tanks spawn after 10 kills" = gate fast tanks until kills >= 10
        # Implementation: maintain a flat spawn_queue; fast tanks are added to
        # held_fast buffer and inserted into queue when gate opens.
        all_tanks = ["basic"]*7 + ["fast"]*5 + ["basic"]*8
        self._spawn_queue    = [t for t in all_tanks if t != "fast"]  # basics first
        self._held_fast      = [t for t in all_tanks if t == "fast"]  # held
        self._fast_gated     = True
        self._fast_gate_kills= 10
        # Legacy compat
        self._pool           = all_tanks
        self._pool_idx       = 0

    # ── Level 2 ───────────────────────────────────────────────────────
    def _setup_level2(self):
        self._level_num  = 2
        self._level_name = "Steel Fortress"
        self._is_boss    = False

        # CSP: brick + steel mix
        gen        = CSPMapGenerator(level=2)
        self._grid = gen.generate()

        # Pool: 4 Fast + 3 Armor + 2 Power + 11 Basic = 20
        self._pool        = ["fast"]*4 + ["armor"]*3 + ["power"]*2 + ["basic"]*11
        self._spawn_queue = list(self._pool)
        self._held_fast   = []
        self._pool_idx    = 0

    # ── Boss Level ────────────────────────────────────────────────────
    def _setup_boss(self):
        self._level_num  = 3
        self._level_name = "Tank Commander"
        self._is_boss    = True
        self._pool        = []
        self._spawn_queue = []
        self._held_fast   = []
        self._pool_idx    = 0

        # Hard-coded closed arena (spec requirement)
        self._grid = _build_boss_arena()

        # Boss spawns at top-centre
        self._boss = BossTank(12, 2)

    # ──────────────────────────────────────────────────────────────────
    #  Main loop
    # ──────────────────────────────────────────────────────────────────

    def run(self):
        while True:
            self.clock.tick(FPS)
            self._events()
            if   self._state == PLAYING:
                self._tick()
            elif self._state == TRANSITION:
                self._trans_t -= 1
                if self._trans_t <= 0:
                    self._state = PLAYING
            elif self._state == LOADING:
                self._loading_frames += 1
                if self._loading_frames >= self._loading_total:
                    self._load_level(self._pending_level, show_transition=False)
            self._render()
            pygame.display.flip()

    # ──────────────────────────────────────────────────────────────────
    #  Events
    # ──────────────────────────────────────────────────────────────────

    def _events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN:
                k = ev.key
                if k == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()

                if self._state == MENU:
                    if k in (pygame.K_UP, pygame.K_w):
                        self._menu_sel = (self._menu_sel - 1) % 3
                    elif k in (pygame.K_DOWN, pygame.K_s):
                        self._menu_sel = (self._menu_sel + 1) % 3
                    elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        self._start_loading_to_level(self._menu_sel)
                    elif k == pygame.K_1:
                        self._menu_sel = 0
                        self._start_loading_to_level(0)
                    elif k == pygame.K_2:
                        self._menu_sel = 1
                        self._start_loading_to_level(1)
                    elif k == pygame.K_3:
                        self._menu_sel = 2
                        self._start_loading_to_level(2)
                    continue

                if self._state == LOADING:
                    continue

                if k == pygame.K_p:
                    if   self._state == PLAYING: self._state = PAUSED
                    elif self._state == PAUSED:  self._state = PLAYING
                if k == pygame.K_r and self._state in (GAME_OVER, YOU_WIN):
                    self.player = PlayerTank()
                    self._state = MENU
                    self._menu_sel = 0
                # N = skip to next level (for testing)
                if k == pygame.K_n and self._state in (PLAYING, PAUSED):
                    next_idx = self._idx + 1
                    if next_idx > 2:
                        self._state = YOU_WIN
                    else:
                        self._load_level(next_idx)

    # ──────────────────────────────────────────────────────────────────
    #  Full game tick
    # ──────────────────────────────────────────────────────────────────

    def _tick(self):
        grid      = self._grid
        all_tanks = self._all_tanks()

        # Prune bullets that died last tick (they were rendered for one frame already)
        self._bullets = [b for b in self._bullets if b.alive]

        # ── 1. INPUT ─────────────────────────────────────────────────
        keys = pygame.key.get_pressed()
        pb   = self.player.handle_input(keys, grid, all_tanks)
        if pb: self._bullets.append(pb)

        # ── 2. AGENT DECISIONS ───────────────────────────────────────
        new_bullets = []
        for e in [e for e in self._enemies if e.alive]:
            b = e.decide(grid, self.player, all_tanks)
            if b: new_bullets.append(b)
        if self._boss and self._boss.alive:
            b = self._boss.decide(grid, self.player, all_tanks)
            if b: new_bullets.append(b)

        # ── 3. MOVE (inside decide() via try_move) ───────────────────
        # ── 4. SHOOT ─────────────────────────────────────────────────
        self._bullets.extend(new_bullets)

        # ── 5. BULLET UPDATE ─────────────────────────────────────────
        # Snapshot current brick positions so we can detect destructions
        # and notify A* tanks to replan (spec: replan on map-change event).
        brick_before = {
            (x, y)
            for y in range(GRID_SIZE) for x in range(GRID_SIZE)
            if grid[y][x] == BRICK
        }

        for b in self._bullets:
            if b.alive:
                b.update(grid, all_tanks)

        # Find bricks that were just destroyed this tick
        destroyed_bricks = brick_before - {
            (x, y)
            for y in range(GRID_SIZE) for x in range(GRID_SIZE)
            if grid[y][x] == BRICK
        }
        if destroyed_bricks:
            for e in self._enemies:
                if e.alive and hasattr(e, 'notify_brick_destroyed'):
                    for bx, by in destroyed_bricks:
                        e.notify_brick_destroyed(bx, by)

        # ── 6. COLLISION — bullet vs bullet cancellation ─────────────
        Bullet.cancel_pairs(self._bullets)

        # ── 7. STATE UPDATE ──────────────────────────────────────────
        # Eagle destroyed? Check ALL bullets (including ones that just died this tick)
        for b in self._bullets:
            if b.eagle_hit:
                self._eagle_dead = True

        # Newly killed enemies → explosions + kill count
        newly_dead = [e for e in self._enemies if not e.alive]
        for d in newly_dead:
            self._explosions.append([d.x, d.y, 14, 14])
            self._kills += 1
        self._enemies = [e for e in self._enemies if e.alive]

        # Boss killed?
        if self._boss and not self._boss.alive:
            self._explosions.append([self._boss.x, self._boss.y, 20, 20])
            self._kills += 1
            self._boss = None

        # Player death
        if not self.player.alive:
            self._explosions.append([self.player.x, self.player.y, 14, 14])
            if not self.player.lose_life():
                self._state = GAME_OVER; return

        # Flash timers
        for t in all_tanks:
            if t.flash_timer > 0: t.flash_timer -= 1

        # Explosion timers
        for exp in self._explosions: exp[2] -= 1
        self._explosions = [e for e in self._explosions if e[2] > 0]

        # Remove dead bullets AFTER render (renderer draws them at render_x/render_y
        # so bullets that died this tick are still visible for one frame)
        self._bullets = [b for b in self._bullets if b.alive]

        # ── 8. SPAWN CHECK ───────────────────────────────────────────
        if not self._is_boss:
            self._tick_spawn()

        # ── 9. RENDER (called from run()) ────────────────────────────

        # ── 10. WIN / LOSE CHECK ─────────────────────────────────────
        if self._eagle_dead:
            self._state = GAME_OVER; return

        if self._check_win():
            next_idx = self._idx + 1
            if next_idx > 2:
                self._state = YOU_WIN
            else:
                self._load_level(next_idx)

    # ──────────────────────────────────────────────────────────────────
    #  Spawn System (per spec)
    # ──────────────────────────────────────────────────────────────────

    def _tick_spawn(self):
        """
        Clean spawn system using _spawn_queue (ready) + _held_fast (gated).
        Level 1: fast tanks sit in _held_fast until kills >= 10, then get
                 prepended back into _spawn_queue. All other levels use _spawn_queue directly.
        """
        active = [e for e in self._enemies if e.alive]
        if len(active) >= MAX_ACTIVE_ENEMIES: return

        # When kill gate opens, release held fast tanks into the queue
        if self._fast_gated and self._held_fast:
            # Release when kills threshold met OR all basics are exhausted
            basics_exhausted = len(self._spawn_queue) == 0 and len([e for e in self._enemies if e.alive]) == 0
            if self._kills >= self._fast_gate_kills or basics_exhausted:
                self._spawn_queue = self._held_fast + self._spawn_queue
                self._held_fast   = []

        if not self._spawn_queue: return

        # Count spawn delay
        self._spawn_timer += 1
        if self._spawn_timer < self._spawn_delay: return

        pos = self._pick_spawn()
        if pos is None:
            self._spawn_timer = self._spawn_delay - FPS // 2
            return

        tank_type         = self._spawn_queue.pop(0)
        self._spawn_timer = 0

        cls  = TANK_FACTORIES.get(tank_type, BasicTank)
        tank = cls(*pos)
        self._enemies.append(tank)

    def _pick_spawn(self):
        """Round-robin spawn with fairness constraint (≥10 Manhattan dist from player)."""
        for _ in range(len(SPAWN_ENEMY)):
            sx, sy = SPAWN_ENEMY[self._spawn_ptr]
            self._spawn_ptr = (self._spawn_ptr + 1) % len(SPAWN_ENEMY)
            # Fairness constraint
            if abs(sx-self.player.x) + abs(sy-self.player.y) < SPAWN_FAIRNESS_DIST:
                continue
            # Not occupied by another enemy
            if any(e.alive and e.x==sx and e.y==sy for e in self._enemies):
                continue
            return (sx, sy)
        return None

    # ──────────────────────────────────────────────────────────────────
    #  Win / state helpers
    # ──────────────────────────────────────────────────────────────────

    def _check_win(self):
        active      = [e for e in self._enemies if e.alive]
        spawn_empty = len(self._spawn_queue) == 0
        held_empty  = len(getattr(self, '_held_fast', [])) == 0
        boss_done   = (self._boss is None or not self._boss.alive)
        return len(active) == 0 and spawn_empty and held_empty and boss_done

    def _enemies_remaining(self):
        active = sum(1 for e in self._enemies if e.alive)
        if self._is_boss:
            return 1 if (self._boss and self._boss.alive) else 0
        queued = len(self._spawn_queue) + len(getattr(self, '_held_fast', []))
        return active + queued

    def _all_tanks(self):
        tanks = [self.player] + [e for e in self._enemies if e.alive]
        if self._boss and self._boss.alive: tanks.append(self._boss)
        return tanks

    # ──────────────────────────────────────────────────────────────────
    #  Render
    # ──────────────────────────────────────────────────────────────────

    def _render(self):
        if self._state == MENU:
            self.renderer.draw_main_menu(self._menu_sel)
            return
        if self._state == LOADING:
            p = self._loading_frames / self._loading_total
            self.renderer.draw_loading(p, self._loading_caption)
            return
        if self._state == TRANSITION:
            cd = max(1, self._trans_t // FPS + 1)
            self.renderer.draw_transition(self._level_num, self._level_name, cd)
            return

        self.renderer.draw_frame(
            grid              = self._grid,
            player            = self.player,
            enemies           = self._enemies,
            bullets           = self._bullets,
            explosions        = self._explosions,
            level             = self._level_num,
            level_name        = self._level_name,
            enemies_remaining = self._enemies_remaining(),
            boss              = self._boss,
            kills             = self._kills,
        )

        if self._state == PAUSED:
            self.renderer.draw_modal_box("PAUSED", "Press  P  to resume")
        elif self._state == GAME_OVER:
            self.renderer.draw_modal_box("GAME OVER", "Press  R  for menu")
        elif self._state == YOU_WIN:
            self.renderer.draw_modal_box("YOU WIN!", "Press  R  for menu")


# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    game = Game()
    game.run()
