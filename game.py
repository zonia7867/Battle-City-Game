import pygame
import sys
import random
from collections import deque

# Constants
TILE_SIZE = 24
GRID_WIDTH = 26
GRID_HEIGHT = 26
GAME_WIDTH = GRID_WIDTH * TILE_SIZE
GAME_HEIGHT = GRID_HEIGHT * TILE_SIZE
SIDEBAR_WIDTH = 200
WINDOW_WIDTH = GAME_WIDTH + SIDEBAR_WIDTH
WINDOW_HEIGHT = GAME_HEIGHT
FPS = 10

# Tile types
EMPTY = 0
BRICK = 1
STEEL = 2
WATER = 3
FOREST = 4
EAGLE = 5

# Colors
COLORS = {
    EMPTY: (0, 0, 0),
    BRICK: (150, 75, 0),
    STEEL: (150, 150, 150),
    WATER: (0, 80, 255),
    FOREST: (20, 120, 20),
    EAGLE: (200, 200, 0),
}
PLAYER_COLOR = (0, 220, 0)
PLAYER_DIR_COLOR = (255, 255, 255)
ENEMY_COLOR = (220, 0, 0)
BULLET_COLOR = (255, 255, 255)
HUD_BG = (30, 30, 30)
HUD_TEXT = (240, 240, 240)

# Directions
DIR_UP = (0, -1)
DIR_DOWN = (0, 1)
DIR_LEFT = (-1, 0)
DIR_RIGHT = (1, 0)
DIRS = {
    'UP': DIR_UP,
    'DOWN': DIR_DOWN,
    'LEFT': DIR_LEFT,
    'RIGHT': DIR_RIGHT,
}

class MapGenerator:
    def __init__(self):
        self.width = GRID_WIDTH
        self.height = GRID_HEIGHT
        self.max_wall_tiles = int(GRID_WIDTH * GRID_HEIGHT * 0.40)
        self.player_start = (4, 24)
        self.eagle = (12, 24)
        self.spawns = [(0, 0), (12, 0), (24, 0)]
        self.border_positions = {
            *( (x, 0) for x in range(self.width) ),
            *( (x, self.height - 1) for x in range(self.width) ),
            *( (0, y) for y in range(self.height) ),
            *( (self.width - 1, y) for y in range(self.height) ),
        }

    def generate(self, level: int):
        self.level = level
        self.weights = self.get_level_weights(level)
        self.rng = random.Random()

        for attempt in range(50):
            self.map = [[None for _ in range(self.width)] for _ in range(self.height)]
            self.wall_count = 0
            self.assign_border_and_fixed()
            self.eagle_ring = [p for p in self.get_neighbors(self.eagle) if self.in_bounds(p)]
            self.positions = self.build_position_order()
            if self.backtrack(0):
                return self.finalize_map()
        raise RuntimeError('Map generation failed after multiple attempts')

    def get_level_weights(self, level: int):
        if level == 1:
            return {
                EMPTY: 55,
                BRICK: 32,
                STEEL: 5,
                WATER: 3,
                FOREST: 5,
            }
        if level == 2:
            return {
                EMPTY: 50,
                BRICK: 20,
                STEEL: 15,
                WATER: 10,
                FOREST: 5,
            }
        return {
            EMPTY: 55,
            BRICK: 25,
            STEEL: 10,
            WATER: 5,
            FOREST: 5,
        }

    def assign_border_and_fixed(self):
        for x in range(self.width):
            self.map[0][x] = STEEL
            self.map[self.height - 1][x] = STEEL
        for y in range(self.height):
            self.map[y][0] = STEEL
            self.map[y][self.width - 1] = STEEL

        for spawn in self.spawns:
            sx, sy = spawn
            self.map[sy][sx] = EMPTY

        px, py = self.player_start
        self.map[py][px] = EMPTY
        ex, ey = self.eagle
        self.map[ey][ex] = EAGLE

    def build_position_order(self):
        positions = []
        for y in range(1, self.height - 1):
            for x in range(1, self.width - 1):
                if self.map[y][x] is None:
                    positions.append((x, y))
        positions.sort(key=lambda p: (0 if p in self.eagle_ring else 1, self.rng.random()))
        return positions

    def backtrack(self, index: int):
        if index >= len(self.positions):
            return self.final_bfs_check()

        x, y = self.positions[index]
        domain = self.get_domain_for_position((x, y))
        for tile in domain:
            self.map[y][x] = tile
            if tile in (BRICK, STEEL, WATER):
                self.wall_count += 1

            if self.wall_count <= self.max_wall_tiles and self.check_forward():
                if self.backtrack(index + 1):
                    return True

            if tile in (BRICK, STEEL, WATER):
                self.wall_count -= 1
            self.map[y][x] = None

        return False

    def get_domain_for_position(self, pos):
        if pos in self.eagle_ring:
            return self.rng.sample([BRICK, STEEL], 2)

        tiles = [EMPTY, FOREST, BRICK, STEEL, WATER]
        weights = [self.weights[t] for t in tiles]
        sampled = self.rng.choices(tiles, weights=weights, k=len(tiles) * 2)
        ordered = []
        for tile in sampled:
            if tile not in ordered:
                ordered.append(tile)
        return ordered

    def in_bounds(self, pos):
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def get_neighbors(self, pos):
        x, y = pos
        return [
            (x - 1, y - 1), (x, y - 1), (x + 1, y - 1),
            (x - 1, y),                 (x + 1, y),
            (x - 1, y + 1), (x, y + 1), (x + 1, y + 1),
        ]

    def tile_value(self, pos, treat_unassigned_as_empty=True):
        x, y = pos
        tile = self.map[y][x]
        if tile is None and treat_unassigned_as_empty:
            return EMPTY
        return EMPTY if tile is None else tile

    def check_forward(self):
        if not self.can_reach_eagle():
            return False
        if not self.player_reachable():
            return False
        if not self.water_safety():
            return False
        return True

    def can_reach_eagle(self):
        for spawn in self.spawns:
            if not self.bfs(spawn, self.eagle, {EMPTY, FOREST}, treat_unassigned_as_empty=True):
                return False
        return True

    def player_reachable(self):
        for spawn in self.spawns:
            if not self.bfs(spawn, self.player_start, {EMPTY, FOREST}, treat_unassigned_as_empty=True):
                return False
        return True

    def water_safety(self):
        for spawn in self.spawns:
            if not self.bfs(spawn, self.eagle, {EMPTY, FOREST, WATER}, treat_unassigned_as_empty=True):
                continue
            if not self.bfs(spawn, self.eagle, {EMPTY, FOREST}, treat_unassigned_as_empty=True):
                return False
        return True

    def final_bfs_check(self):
        for spawn in self.spawns:
            if not self.bfs(spawn, self.eagle, {EMPTY, FOREST}, treat_unassigned_as_empty=False):
                return False
        return True

    def bfs(self, start, goal, passable_values, treat_unassigned_as_empty=True):
        queue = deque([start])
        seen = {start}
        while queue:
            x, y = queue.popleft()
            if (x, y) == goal:
                return True
            for dx, dy in (DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                if (nx, ny) in seen:
                    continue
                tile = self.tile_value((nx, ny), treat_unassigned_as_empty)
                if tile not in passable_values:
                    continue
                seen.add((nx, ny))
                queue.append((nx, ny))
        return False

    def finalize_map(self):
        return [
            [EMPTY if cell is None else cell for cell in row]
            for row in self.map
        ]

class Tank:
    def __init__(self, x, y, direction='UP', color=PLAYER_COLOR, hp=1, is_player=False):
        self.x = x
        self.y = y
        self.direction = direction
        self.color = color
        self.hp = hp
        self.is_player = is_player
        self.alive = True

    def rect(self):
        return pygame.Rect(self.x * TILE_SIZE, self.y * TILE_SIZE, TILE_SIZE, TILE_SIZE)

    def direction_rect(self):
        dx, dy = DIRS[self.direction]
        cx = self.x * TILE_SIZE + TILE_SIZE // 2
        cy = self.y * TILE_SIZE + TILE_SIZE // 2
        if dx != 0:
            return pygame.Rect(cx + dx * 6, cy - 4, 8, 8)
        return pygame.Rect(cx - 4, cy + dy * 6, 8, 8)

    def move(self, direction, game_map, tanks):
        dx, dy = DIRS[direction]
        target_x = self.x + dx
        target_y = self.y + dy
        if target_x < 0 or target_x >= GRID_WIDTH or target_y < 0 or target_y >= GRID_HEIGHT:
            return
        target_tile = game_map[target_y][target_x]
        if target_tile in (BRICK, STEEL, WATER):
            return
        if any(t.alive and t.x == target_x and t.y == target_y for t in tanks if t is not self):
            return
        self.x = target_x
        self.y = target_y
        self.direction = direction

    def take_damage(self):
        self.hp -= 1
        if self.hp <= 0:
            self.alive = False

class Bullet:
    def __init__(self, x, y, direction, owner):
        self.x = x
        self.y = y
        self.direction = direction
        self.owner = owner
        self.alive = True

    def rect(self):
        return pygame.Rect(self.x * TILE_SIZE + TILE_SIZE // 4,
                           self.y * TILE_SIZE + TILE_SIZE // 4,
                           TILE_SIZE // 2,
                           TILE_SIZE // 2)

    def advance_step(self, game_map, tanks, bullets):
        if not self.alive:
            return
        dx, dy = DIRS[self.direction]
        next_x = self.x + dx
        next_y = self.y + dy
        if next_x < 0 or next_x >= GRID_WIDTH or next_y < 0 or next_y >= GRID_HEIGHT:
            self.alive = False
            return

        self.x = next_x
        self.y = next_y

        # Bullet collision with bullets
        for other in bullets:
            if other is not self and other.alive and other.x == self.x and other.y == self.y:
                self.alive = False
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
        if tile == EAGLE:
            self.alive = False
            return

        if tile == WATER:
            self.alive = False
            return

        for tank in tanks:
            if tank.alive and tank.x == self.x and tank.y == self.y:
                tank.take_damage()
                self.alive = False
                return

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption('Battle City Clone')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Arial', 20)
        self.big_font = pygame.font.SysFont('Arial', 40)
        self.map_generator = MapGenerator()
        self.reset()

    def reset(self):
        self.game_map = self.map_generator.generate(1)
        self.player = Tank(4, 24, direction='UP', is_player=True)
        self.player.lives = 10
        self.player.respawn_timer = 0
        self.player.can_shoot = True
        self.bullets = []
        self.enemies = [
            Tank(0, 0, direction='DOWN', color=ENEMY_COLOR, hp=1),
            Tank(12, 0, direction='DOWN', color=ENEMY_COLOR, hp=1),
            Tank(24, 0, direction='DOWN', color=ENEMY_COLOR, hp=1),
        ]
        self.tanks = [self.player] + self.enemies
        self.game_over = False
        self.win = False
        self.lose_reason = ''
        self.enemy_start_count = len(self.enemies)

    def reload_map(self):
        self.game_map = self.map_generator.generate(1)
        self.bullets = []
        self.game_over = False
        self.win = False
        self.lose_reason = ''
        self.player.respawn_timer = 0
        self.player.can_shoot = True
        self.player.alive = True
        self.player.hp = 1
        self.player.x, self.player.y = 4, 24
        self.player.direction = 'UP'
        for enemy, spawn in zip(self.enemies, self.map_generator.spawns):
            enemy.x, enemy.y = spawn
            enemy.alive = True
            enemy.hp = 1
            enemy.direction = 'DOWN'

    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            self.handle_events()
            if not self.game_over:
                self.update()
            self.render()

    def handle_events(self):
        self.pressed = pygame.key.get_pressed()
        self.shoot_pressed = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.shoot_pressed = True
                if event.key == pygame.K_r:
                    self.reload_map()

    def update(self):
        self.handle_player_input()
        self.move_tanks()
        self.fire_bullets()
        self.advance_bullets()
        self.collision_check()
        self.update_state()
        self.check_win_lose()

    def handle_player_input(self):
        if not self.player.alive:
            return
        if self.pressed[pygame.K_UP]:
            self.player.move('UP', self.game_map, self.tanks)
        elif self.pressed[pygame.K_DOWN]:
            self.player.move('DOWN', self.game_map, self.tanks)
        elif self.pressed[pygame.K_LEFT]:
            self.player.move('LEFT', self.game_map, self.tanks)
        elif self.pressed[pygame.K_RIGHT]:
            self.player.move('RIGHT', self.game_map, self.tanks)

    def move_tanks(self):
        # Static enemies do not move in this version
        pass

    def fire_bullets(self):
        if self.shoot_pressed and self.player.alive and self.player.can_shoot:
            if not any(b.alive and b.owner is self.player for b in self.bullets):
                dx, dy = DIRS[self.player.direction]
                bullet_x = self.player.x + dx
                bullet_y = self.player.y + dy
                if 0 <= bullet_x < GRID_WIDTH and 0 <= bullet_y < GRID_HEIGHT:
                    bullet = Bullet(bullet_x, bullet_y, self.player.direction, self.player)
                    self.bullets.append(bullet)
                    self.player.can_shoot = False
        if not self.shoot_pressed:
            self.player.can_shoot = True

    def advance_bullets(self):
        for bullet in self.bullets:
            if bullet.alive:
                # bullets move two steps per tick
                bullet.advance_step(self.game_map, self.tanks, self.bullets)
            if bullet.alive:
                bullet.advance_step(self.game_map, self.tanks, self.bullets)

    def collision_check(self):
        for bullet in self.bullets:
            if not bullet.alive:
                continue
            tile = self.game_map[bullet.y][bullet.x]
            if tile == EAGLE:
                self.game_over = True
                self.lose_reason = 'Eagle destroyed!'
                return
            if tile == BRICK:
                self.game_map[bullet.y][bullet.x] = EMPTY
                bullet.alive = False
            elif tile == STEEL:
                bullet.alive = False
            elif tile == WATER:
                bullet.alive = False
        for bullet in self.bullets:
            if not bullet.alive:
                continue
            for tank in self.tanks:
                if tank.alive and tank.x == bullet.x and tank.y == bullet.y:
                    if bullet.owner is tank:
                        continue
                    tank.take_damage()
                    bullet.alive = False
                    break
        bullet_positions = {}
        for bullet in self.bullets:
            if not bullet.alive:
                continue
            key = (bullet.x, bullet.y)
            if key in bullet_positions:
                bullet.alive = False
                bullet_positions[key].alive = False
            else:
                bullet_positions[key] = bullet

    def update_state(self):
        if self.player.alive:
            return
        if self.player.lives > 0:
            if self.player.respawn_timer == 0:
                self.player.respawn_timer = pygame.time.get_ticks() + 2000
            elif pygame.time.get_ticks() >= self.player.respawn_timer:
                self.player.respawn_timer = 0
                self.player.alive = True
                self.player.hp = 1
                self.player.x = 4
                self.player.y = 24
                self.player.direction = 'UP'
        else:
            self.game_over = True
            self.lose_reason = 'No lives remaining.'

    def check_win_lose(self):
        alive_enemies = [e for e in self.enemies if e.alive]
        if len(alive_enemies) == 0:
            self.game_over = True
            self.win = True

    def render(self):
        self.screen.fill((0, 0, 0))
        self.draw_map()
        self.draw_tanks()
        self.draw_bullets()
        self.draw_hud()
        if self.game_over:
            self.draw_end_screen()
        pygame.display.flip()

    def draw_map(self):
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                tile = self.game_map[y][x]
                color = COLORS.get(tile, COLORS[EMPTY])
                rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(self.screen, color, rect)
                pygame.draw.rect(self.screen, (40, 40, 40), rect, 1)

    def draw_tanks(self):
        for tank in self.tanks:
            if not tank.alive:
                continue
            pygame.draw.rect(self.screen, tank.color, tank.rect())
            pygame.draw.rect(self.screen, PLAYER_DIR_COLOR, tank.direction_rect())

    def draw_bullets(self):
        for bullet in self.bullets:
            if bullet.alive:
                pygame.draw.rect(self.screen, BULLET_COLOR, bullet.rect())

    def draw_hud(self):
        hud_rect = pygame.Rect(GAME_WIDTH, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, HUD_BG, hud_rect)
        lines = [
            'Battle City Clone',
            '',
            f'Lives: {self.player.lives}',
            f'Enemies: {len([e for e in self.enemies if e.alive])}/{self.enemy_start_count}',
            '',
            'Controls:',
            'Arrow keys to move',
            'Space to shoot',
            'R to regenerate map',
        ]
        y = 20
        for line in lines:
            surface = self.font.render(line, True, HUD_TEXT)
            self.screen.blit(surface, (GAME_WIDTH + 10, y))
            y += 26

    def draw_end_screen(self):
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        if self.win:
            message = 'YOU WIN!'
        else:
            message = 'GAME OVER'
        msg_surface = self.big_font.render(message, True, (255, 255, 255))
        sub_surface = self.font.render(self.lose_reason or 'Press R to restart.', True, (255, 255, 255))
        rect = msg_surface.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT // 2 - 20))
        self.screen.blit(msg_surface, rect)
        rect2 = sub_surface.get_rect(center=(GAME_WIDTH // 2, GAME_HEIGHT // 2 + 30))
        self.screen.blit(sub_surface, rect2)

if __name__ == '__main__':
    game = Game()
    game.run()
