
# ─── Grid & Display ───────────────────────────────────────────────────
GRID_SIZE  = 26
TILE_SIZE  = 24
PANEL_W    = 180
SCREEN_W   = GRID_SIZE * TILE_SIZE + PANEL_W
SCREEN_H   = GRID_SIZE * TILE_SIZE
FPS        = 30

# ─── Terrain codes ────────────────────────────────────────────────────
EMPTY  = 0
BRICK  = 1
STEEL  = 2
WATER  = 3
FOREST = 4
EAGLE  = 5

# ─── Directions ───────────────────────────────────────────────────────
UP    = ( 0, -1)
DOWN  = ( 0,  1)
LEFT  = (-1,  0)
RIGHT = ( 1,  0)
DIRS  = [UP, DOWN, LEFT, RIGHT]

# ─── Fixed positions ──────────────────────────────────────────────────
EAGLE_POS    = (12, 24)
SPAWN_PLAYER = (4,  24)
SPAWN_ENEMY  = [(0, 0), (12, 0), (24, 0)]

# ─── Spawn rules ──────────────────────────────────────────────────────
MAX_ACTIVE_ENEMIES   = 3
ENEMY_POOL_PER_LEVEL = 20
SPAWN_FAIRNESS_DIST  = 10
PLAYER_START_LIVES   = 10   # used by PlayerTank.__init__

# ─── Bullet ───────────────────────────────────────────────────────────
BULLET_STEPS_PER_TICK = 2

# ─── A* costs ─────────────────────────────────────────────────────────
ASTAR_COST = {EMPTY:1, FOREST:1, BRICK:3, STEEL:float('inf'), WATER:float('inf'), EAGLE:1}

# ─── NES-palette colours ──────────────────────────────────────────────
C_BLACK   = (  0,   0,   0)
C_BG      = ( 10,  10,  10)
# HUD sidebar — black / purple
C_PANEL      = (  6,   3,  16)
C_DIVIDER    = ( 85,  50, 125)
C_PANEL_TEXT = (210, 185, 245)
C_PANEL_DIM  = (130, 100, 170)

# terrain
C_EMPTY     = ( 18,  18,  18)
C_BRICK     = (176,  72,  16)
C_BRICK_SH  = (120,  45,   8)
C_STEEL     = (130, 155, 175)
C_STEEL_HI  = (185, 210, 230)
C_WATER1    = ( 25,  75, 190)
C_WATER2    = ( 55, 115, 220)
C_FOREST1   = ( 22,  90,  22)
C_FOREST2   = ( 45, 140,  45)
C_EAGLE_BG  = ( 10,  10,  10)
C_EAGLE_COL = (220, 190,  35)

# UI
C_WHITE   = (255, 255, 255)
C_YELLOW  = (255, 215,   0)
C_RED     = (220,  45,  45)
C_GREEN   = ( 65, 195,  65)
C_CYAN    = ( 55, 210, 210)
C_ORANGE  = (220, 130,  25)
C_PURPLE  = (155,  75, 215)
C_PURPLE_HI  = (210, 140, 255)
C_PURPLE_DK  = ( 60,  20,  95)
C_GRAY    = (110, 110, 110)
C_DGRAY   = ( 40,  40,  40)
C_LTGRAY  = (175, 175, 175)

TANK_COLORS = {
    "player": C_YELLOW,
    "basic" : C_GRAY,
    "fast"  : C_CYAN,
    "armor" : C_GREEN,
    "power" : C_PURPLE,
    "boss"  : C_RED,
}
