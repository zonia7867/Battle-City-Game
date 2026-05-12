import math, pygame
from constants import *


class Renderer:
    def __init__(self, screen):
        self.screen      = screen
        self._wave       = 0
        self._init_fonts()
        self._build_tile_surfaces()

    def _init_fonts(self):
        pygame.font.init()
        try:
            self.f_hud   = pygame.font.SysFont("Courier New", 12, bold=True)
            self.f_title = pygame.font.SysFont("Courier New", 16, bold=True)
            self.f_big   = pygame.font.SysFont("Courier New", 34, bold=True)
            self.f_med   = pygame.font.SysFont("Courier New", 20, bold=True)
            self.f_menu  = pygame.font.SysFont("Arial Black", 46, bold=True)
            self.f_menu_opt = pygame.font.SysFont("Consolas", 22, bold=True)
            self.f_menu_small = pygame.font.SysFont("Consolas", 16, bold=True)
        except Exception:
            self.f_hud   = pygame.font.SysFont(None, 14)
            self.f_title = pygame.font.SysFont(None, 18)
            self.f_big   = pygame.font.SysFont(None, 38)
            self.f_med   = pygame.font.SysFont(None, 22)
            self.f_menu  = pygame.font.SysFont(None, 52, bold=True)
            self.f_menu_opt = pygame.font.SysFont(None, 22, bold=True)
            self.f_menu_small = pygame.font.SysFont(None, 16, bold=True)

    def _build_tile_surfaces(self):
        """Pre-render static tile surfaces for speed."""
        T = TILE_SIZE
        self._tiles = {}

        # EMPTY
        s = pygame.Surface((T,T)); s.fill(C_EMPTY)
        self._tiles[EMPTY] = s

        # BRICK
        s = pygame.Surface((T,T)); s.fill(C_BRICK)
        # Horizontal mortar
        pygame.draw.line(s, C_BRICK_SH, (0,T//2),(T,T//2), 1)
        # Vertical mortar (offset per half-row)
        pygame.draw.line(s, C_BRICK_SH, (T//2,0),(T//2,T//2), 1)
        pygame.draw.line(s, C_BRICK_SH, (T//4, T//2),(T//4,T), 1)
        pygame.draw.line(s, C_BRICK_SH, (T*3//4,T//2),(T*3//4,T), 1)
        self._tiles[BRICK] = s

        # STEEL
        s = pygame.Surface((T,T)); s.fill(C_STEEL)
        pygame.draw.rect(s, C_STEEL_HI, (1,1,T-2,T-2), 1)
        pygame.draw.line(s, C_STEEL_HI, (2,2),(T-2,2), 1)
        pygame.draw.line(s, C_STEEL_HI, (2,2),(2,T-2), 1)
        pygame.draw.rect(s, C_DGRAY,    (T//3,T//3,T//3,T//3))
        self._tiles[STEEL] = s

        # FOREST
        s = pygame.Surface((T,T)); s.fill(C_FOREST1)
        for fx,fy,r in [(4,4,4),(13,5,3),(8,13,4),(17,13,3),(4,16,3)]:
            pygame.draw.circle(s, C_FOREST2, (fx,fy), r)
        self._tiles[FOREST] = s

    def draw_frame(self, grid, player, enemies, bullets, explosions,
                   level, level_name, enemies_remaining, boss=None, kills=0):
        self._wave = (self._wave+1) % 40
        self.screen.fill(C_BG)
        self._draw_grid(grid)
        self._draw_explosions(explosions)
        # Draw forest OVERLAY (tanks hidden inside forest)
        self._draw_tanks(player, enemies, boss)
        self._draw_forest_overlay(grid)
        self._draw_bullets(bullets)
        self._draw_panel(player, level, level_name, enemies_remaining, boss, kills)

    def _draw_grid(self, grid):
        T = TILE_SIZE
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                px, py = x*T, y*T
                tile   = grid[y][x]

                if tile in self._tiles:
                    self.screen.blit(self._tiles[tile], (px,py))
                elif tile == WATER:
                    self._draw_water(px, py, T)
                elif tile == EAGLE:
                    self._draw_eagle(px, py, T)
                else:
                    pygame.draw.rect(self.screen, C_EMPTY, (px,py,T,T))

    def _draw_water(self, px, py, T):
        pygame.draw.rect(self.screen, C_WATER1, (px,py,T,T))
        phase = self._wave
        for wx in range(0, T, 8):
            ox = (wx + phase) % 8
            arc_x = px + wx - ox
            pygame.draw.arc(self.screen, C_WATER2,
                            (arc_x, py+T//3, 7, 5), 0, math.pi, 2)

    def _draw_eagle(self, px, py, T):
        pygame.draw.rect(self.screen, C_EAGLE_BG, (px,py,T,T))
        # Eagle / phoenix symbol (two chevrons = wings)
        cx = px + T//2; cy = py + T//2
        # Body
        pygame.draw.rect(self.screen, C_EAGLE_COL, (cx-3, cy-4, 6, 10))
        # Wings
        pts_l = [(cx-3,cy-2),(cx-10,cy+4),(cx-3,cy+4)]
        pts_r = [(cx+3,cy-2),(cx+10,cy+4),(cx+3,cy+4)]
        pygame.draw.polygon(self.screen, C_EAGLE_COL, pts_l)
        pygame.draw.polygon(self.screen, C_EAGLE_COL, pts_r)
        # Crown/head
        pygame.draw.circle(self.screen, C_EAGLE_COL, (cx, cy-5), 4)
        pygame.draw.rect(self.screen, C_EAGLE_BG, (cx-1,cy-7,2,2))

    def _draw_forest_overlay(self, grid):
        """Redraw forest tiles on top so tanks appear hidden."""
        T = TILE_SIZE
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                if grid[y][x] == FOREST:
                    self.screen.blit(self._tiles[FOREST], (x*T, y*T))

    def _draw_tanks(self, player, enemies, boss=None):
        all_t = [e for e in enemies if e.alive]
        if boss and boss.alive: all_t.append(boss)
        if player.alive: all_t.append(player)
        for t in all_t:
            self._draw_tank(t)

    def _draw_tank(self, tank):
        T  = TILE_SIZE
        px = tank.x * T
        py = tank.y * T
        col = TANK_COLORS.get(tank.type, C_GRAY)
        if tank.flash_timer > 0:
            col = C_WHITE

        # Treads
        pygame.draw.rect(self.screen, C_DGRAY, (px+1,     py+4, 4, T-8))
        pygame.draw.rect(self.screen, C_DGRAY, (px+T-5,   py+4, 4, T-8))
        # Tread notches
        for i in range(0, T-8, 4):
            pygame.draw.line(self.screen, C_BLACK, (px+1,py+4+i),(px+4,py+4+i),1)
            pygame.draw.line(self.screen, C_BLACK, (px+T-5,py+4+i),(px+T-1,py+4+i),1)

        # Hull
        m = 4
        pygame.draw.rect(self.screen, col, (px+m, py+m, T-m*2, T-m*2))
        # Hull shading
        pygame.draw.line(self.screen, C_WHITE, (px+m,py+m),(px+T-m,py+m),1)
        pygame.draw.line(self.screen, C_WHITE, (px+m,py+m),(px+m,py+T-m),1)

        # Barrel
        cx, cy = px+T//2, py+T//2
        dx, dy = tank.dir
        bx2, by2 = cx+dx*(T//2-1), cy+dy*(T//2-1)
        pygame.draw.line(self.screen, C_DGRAY, (cx,cy),(bx2,by2), 4)
        pygame.draw.line(self.screen, col,     (cx,cy),(bx2,by2), 2)

        # Turret dot
        pygame.draw.circle(self.screen, C_DGRAY, (cx,cy), 4)
        pygame.draw.circle(self.screen, col,     (cx,cy), 3)

        # Boss ring
        if tank.type == 'boss':
            pygame.draw.rect(self.screen, C_YELLOW, (px+1,py+1,T-2,T-2), 2)
            pygame.draw.rect(self.screen, C_RED,    (px+3,py+3,T-6,T-6), 1)

        # HP bar for multi-hit tanks
        if tank.max_hp > 1 and tank.alive:
            bw = T-4
            filled = max(0, int(bw * tank.hp / tank.max_hp))
            pygame.draw.rect(self.screen, C_RED,   (px+2, py+T+1, bw,     3))
            pygame.draw.rect(self.screen, C_GREEN, (px+2, py+T+1, filled, 3))

    def _draw_bullets(self, bullets):
        T = TILE_SIZE
        for b in bullets:
            # Use render_x/render_y (last valid position) so bullets that
            # died this tick are still visible for this frame.
            rx = getattr(b, 'render_x', b.x)
            ry = getattr(b, 'render_y', b.y)
            cx = rx*T + T//2
            cy = ry*T + T//2
            col = C_YELLOW if b.owner_type == 'player' else C_RED
            dx, dy = b.dir
            # Larger, more visible bullet with directional elongation
            pygame.draw.ellipse(self.screen, col,
                                (cx-4+dx*3, cy-4+dy*3, 8, 8))
            pygame.draw.circle(self.screen, C_WHITE, (cx, cy), 2)

    def _draw_explosions(self, explosions):
        T = TILE_SIZE
        for exp in explosions:
            x, y, timer, max_t = exp
            cx = x*T + T//2
            cy = y*T + T//2
            prog  = (max_t - timer) / max_t
            r_out = int(prog * T * 1.2)
            r_in  = int(prog * T * 0.6)
            r_cor = int(prog * T * 0.3)
            if r_out > 0:
                pygame.draw.circle(self.screen, C_RED,    (cx,cy), r_out)
            if r_in > 0:
                pygame.draw.circle(self.screen, C_ORANGE, (cx,cy), r_in)
            if r_cor > 0:
                pygame.draw.circle(self.screen, C_YELLOW, (cx,cy), r_cor)

    # ── HUD Panel ─────────────────────────────────────────────────────

    def _draw_panel(self, player, level, level_name, enemies_remaining,
                    boss=None, kills=0):
        from search import get_minimax_stats
        px0 = GRID_SIZE * TILE_SIZE
        pw  = PANEL_W
        s   = self.screen
        pygame.draw.rect(s, C_PANEL, (px0, 0, pw, SCREEN_H))
        pygame.draw.line(s, C_PURPLE, (px0, 0), (px0, SCREEN_H), 2)

        y = 8
        x = px0 + 8

        def ln(text, col=C_PANEL_TEXT, f=None):
            nonlocal y
            f   = f or self.f_hud
            img = f.render(text, True, col)
            s.blit(img, (x, y))
            y  += img.get_height() + 3

        def div():
            nonlocal y
            y += 4
            pygame.draw.line(s, C_DIVIDER, (px0 + 4, y), (px0 + pw - 4, y), 1)
            y += 5

        ln("BATTLE CITY", C_PURPLE_HI, self.f_title)
        ln("by Zonia,", C_PANEL_DIM, self.f_hud)
        ln("Maidah and Anza", C_PANEL_DIM, self.f_hud)
        div()

        ln(f"LEVEL {level}", C_PURPLE_HI, self.f_title)
        ln(level_name, C_PANEL_TEXT)
        div()

        lives_mark = ("★ " * player.lives).strip()
        ln(f"Lives: {lives_mark}", C_PURPLE_HI)
        ln(f"Enemies: {enemies_remaining}", C_PANEL_TEXT)
        ln(f"Kills:   {kills}", C_PANEL_DIM)
        div()

        # Controls
        ln("CONTROLS", C_PURPLE_HI, self.f_title)
        for ctrl in (
            "WASD/Arrows: Move",
            "SPACE/J: Fire",
            "P: Pause",
            "N: Next Level",
            "ESC: Quit",
        ):
            ln(ctrl, C_PANEL_DIM)
        div()

        # Tank legend
        ln("TANK => ALGORITHM", C_PURPLE_HI, self.f_title)
        legend = [
            ("player", "Player  =>  You!"),
            ("basic", "Basic   =>  BFS"),
            ("fast", "Fast    =>  Greedy"),
            ("armor", "Armor   =>  A*"),
            ("power", "Power   =>  A*"),
            ("boss", "Boss    =>  Minimax"),
        ]
        for ttype, label in legend:
            col = TANK_COLORS.get(ttype, C_GRAY)
            pygame.draw.rect(s, col, (x, y + 2, 10, 10))
            img = self.f_hud.render(f"  {label}", True, C_PANEL_TEXT)
            s.blit(img, (x + 10, y))
            y += img.get_height() + 3

        # Boss panel
        if boss and boss.alive:
            div()
            ln(f"── BOSS  Ph.{boss.phase} ──", C_PURPLE_HI, self.f_title)
            ln(f"HP: {boss.hp}/{boss.max_hp}", C_PANEL_TEXT)
            bw = pw - 18
            filled = max(0, int(bw * boss.hp / boss.max_hp))
            pygame.draw.rect(s, C_PURPLE_DK, (x, y, bw, 8))
            pygame.draw.rect(s, C_PURPLE_HI, (x, y, filled, 8))
            pygame.draw.rect(s, C_PURPLE, (x, y, bw, 8), 1)
            y += 11
            ln(f"Depth: {boss._depth}", C_PANEL_DIM)
            stats = get_minimax_stats()
            pruned = stats["with_pruning"]
            unpruned = stats["without_pruning"]
            ln(f"Nodes (pruned):   {pruned}", C_PURPLE_HI)
            ln(f"Nodes (no prune): {unpruned}", C_PANEL_DIM)
            if pruned > 0 and unpruned > 0:
                ratio = unpruned / pruned
                ln(f"Speedup: x{ratio:.1f}", C_PANEL_TEXT)

    # ── Overlays ──────────────────────────────────────────────────────

    def draw_modal_box(self, title, sub=""):
        """Full-screen dim plus centered black/purple panel (pause / game over / win)."""
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((12, 6, 22, 210))
        self.screen.blit(ov, (0, 0))

        title_img = self.f_big.render(title, True, C_PURPLE_HI)
        subimg = self.f_med.render(sub, True, C_PANEL_TEXT) if sub else None
        pad_x, pad_y = 36, 26
        gap = 16
        box_w = title_img.get_width() + pad_x * 2
        box_h = title_img.get_height() + pad_y * 2
        if subimg:
            box_w = max(box_w, subimg.get_width() + pad_x * 2)
            box_h += subimg.get_height() + gap

        bx = (SCREEN_W - box_w) // 2
        by = (SCREEN_H - box_h) // 2

        pygame.draw.rect(self.screen, C_PANEL, (bx, by, box_w, box_h), border_radius=12)
        pygame.draw.rect(self.screen, C_PURPLE, (bx, by, box_w, box_h), 3, border_radius=12)

        tx = (SCREEN_W - title_img.get_width()) // 2
        ty = by + pad_y
        self.screen.blit(title_img, (tx, ty))
        if subimg:
            sx = (SCREEN_W - subimg.get_width()) // 2
            self.screen.blit(subimg, (sx, ty + title_img.get_height() + gap))

    def draw_overlay(self, text, sub="", col=C_YELLOW):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0,0,0,170))
        self.screen.blit(ov,(0,0))
        img = self.f_big.render(text, True, col)
        rx  = (SCREEN_W - img.get_width())  // 2
        ry  = (SCREEN_H - img.get_height()) // 2 - 24
        self.screen.blit(img,(rx,ry))
        if sub:
            sim = self.f_med.render(sub, True, C_WHITE)
            sx  = (SCREEN_W - sim.get_width())  // 2
            self.screen.blit(sim,(sx, ry + img.get_height() + 14))

    def draw_transition(self, level, name, countdown):
        self.screen.fill(C_BLACK)
        self.draw_overlay(f"LEVEL  {level}", f"{name}   —   {countdown}s", C_CYAN)

    def _blit_outline_text(self, text, font, pos, fill_col, outline_col, offsets=None):
        """Stacked outline for a chunky arcade look."""
        if offsets is None:
            offsets = ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, -2), (-2, 2), (2, 2))
        x, y = pos
        for dx, dy in offsets:
            s = font.render(text, True, outline_col)
            self.screen.blit(s, (x + dx, y + dy))
        self.screen.blit(font.render(text, True, fill_col), (x, y))

    def _title_width_spaced(self, text, font, tracking, space_w):
        """Total width for spaced-out title layout (matches _blit_spaced_outline_title)."""
        n = len(text)
        w = 0
        for i, ch in enumerate(text):
            if ch == " ":
                w += space_w
            else:
                w += font.render(ch, True, C_WHITE).get_width()
            if i < n - 1:
                w += tracking
        return w

    def _blit_spaced_outline_title(self, text, center_x, y, fill_col, outline_col, tracking=10, space_w=36):
        """Per-glyph outline with extra tracking for a clear, readable title."""
        font = self.f_menu
        offsets = ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1))
        total = self._title_width_spaced(text, font, tracking, space_w)
        cx = center_x - total // 2
        n = len(text)
        for i, ch in enumerate(text):
            if ch == " ":
                cx += space_w
                if i < n - 1:
                    cx += tracking
                continue
            g_fill = font.render(ch, True, fill_col)
            g_out = font.render(ch, True, outline_col)
            for dx, dy in offsets:
                self.screen.blit(g_out, (cx + dx, y + dy))
            self.screen.blit(g_fill, (cx, y))
            cx += g_fill.get_width()
            if i < n - 1:
                cx += tracking

    def draw_main_menu(self, selection_index):
        """Black + purple title screen with level choices."""
        self.screen.fill(C_BLACK)

        title = "BATTLE CITY"
        ty = 52
        self._blit_spaced_outline_title(
            title, SCREEN_W // 2, ty, C_PURPLE_HI, C_PURPLE_DK, tracking=10, space_w=36
        )

        credit = 'Tank You Next'
        cr = self.f_menu_small.render(credit, True, C_PURPLE)
        self.screen.blit(cr, ((SCREEN_W - cr.get_width()) // 2, ty + 62))

        options = [
            ("LEVEL 1", "Brick Maze", pygame.K_1),
            ("LEVEL 2", "Steel Fortress", pygame.K_2),
            ("BOSS LEVEL", "Tank Commander", pygame.K_3),
        ]
        block_y = SCREEN_H // 2 - 20
        for i, (head, sub, _) in enumerate(options):
            sel = i == selection_index
            row_y = block_y + i * 52
            row_w, row_h = 420, 46
            rx = (SCREEN_W - row_w) // 2
            if sel:
                pygame.draw.rect(self.screen, C_PURPLE_DK, (rx, row_y, row_w, row_h), border_radius=6)
                pygame.draw.rect(self.screen, C_PURPLE, (rx, row_y, row_w, row_h), 2, border_radius=6)
            else:
                pygame.draw.rect(self.screen, (25, 15, 40), (rx, row_y, row_w, row_h), 1, border_radius=6)

            prefix = "► " if sel else "  "
            hcol = C_PURPLE_HI if sel else C_PURPLE
            line = prefix + head
            img = self.f_menu_opt.render(line, True, hcol)
            self.screen.blit(img, (rx + 14, row_y + 4))
            sub_img = self.f_menu_small.render(sub, True, C_LTGRAY if sel else C_GRAY)
            self.screen.blit(sub_img, (rx + 36, row_y + 26))

    def draw_loading(self, progress, caption):
        """Minimal loading screen with a small progress bar (0..1)."""
        self.screen.fill(C_BLACK)
        cap = self.f_med.render(caption, True, C_PURPLE_HI)
        self.screen.blit(cap, ((SCREEN_W - cap.get_width()) // 2, SCREEN_H // 2 - 40))

        bar_w, bar_h = 280, 14
        bx = (SCREEN_W - bar_w) // 2
        by = SCREEN_H // 2
        pygame.draw.rect(self.screen, C_PURPLE_DK, (bx, by, bar_w, bar_h), border_radius=4)
        pygame.draw.rect(self.screen, C_PURPLE, (bx, by, bar_w, bar_h), 1, border_radius=4)
        fill = max(0, min(bar_w - 2, int((bar_w - 2) * progress)))
        if fill > 0:
            pygame.draw.rect(
                self.screen, C_PURPLE_HI, (bx + 1, by + 1, fill, bar_h - 2), border_radius=3
            )

        pct = self.f_menu_small.render(f"{int(progress * 100)}%", True, C_PURPLE)
        self.screen.blit(pct, ((SCREEN_W - pct.get_width()) // 2, by + bar_h + 10))
        lab = self.f_menu_small.render("LOADING…", True, C_GRAY)
        self.screen.blit(lab, ((SCREEN_W - lab.get_width()) // 2, by - 22))
