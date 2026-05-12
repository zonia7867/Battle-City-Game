from constants import GRID_SIZE, BRICK, STEEL, WATER, FOREST, EAGLE, BULLET_STEPS_PER_TICK


class Bullet:
    __slots__ = ('x', 'y', 'dir', 'owner_type', 'owner', 'alive', 'eagle_hit', 'render_x', 'render_y')

    def __init__(self, x, y, direction, owner_type='enemy', owner=None):
        # Spawn bullet ONE tile ahead of tank — immediately visible and
        # correctly positioned to hit walls/tanks directly in front.
        dx, dy = direction
        self.x          = x + dx
        self.y          = y + dy
        self.render_x   = self.x
        self.render_y   = self.y
        self.dir        = direction
        self.owner_type = owner_type
        self.owner      = owner
        self.alive      = True
        self.eagle_hit  = False

    def update(self, grid, tanks):
        """
        Each tick: check current tile, then advance (BULLET_STEPS_PER_TICK-1)
        more tiles. Total = BULLET_STEPS_PER_TICK tiles of movement per tick.
        render_x/render_y always hold the last position before death so the
        renderer can draw the bullet even when it dies this tick.
        """
        if not self.alive:
            return
        dx, dy = self.dir

        for step in range(BULLET_STEPS_PER_TICK):
            if not self.alive:
                break

            # Step 0: check tile bullet is already on (spawned here last frame).
            # Step 1+: move one tile forward first, then check.
            if step > 0:
                nx, ny = self.x + dx, self.y + dy
                if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
                    self.alive = False
                    break
                self.x, self.y = nx, ny

            # Safety bounds check (step 0 could be off-grid if tank at edge)
            if not (0 <= self.x < GRID_SIZE and 0 <= self.y < GRID_SIZE):
                self.alive = False
                break

            # Keep render position updated to last valid tile
            self.render_x, self.render_y = self.x, self.y

            tile = grid[self.y][self.x]

            if tile == EAGLE:
                self.eagle_hit = True
                self.alive = False
                break

            if tile == BRICK:
                grid[self.y][self.x] = 0
                self.alive = False
                break

            if tile == STEEL:
                self.alive = False
                break

            if tile == WATER:
                self.alive = False
                break

            # Forest: bullet passes through — no collision, continue loop

            # Tank collision at current tile
            for t in tanks:
                if t is self.owner or not t.alive:
                    continue
                if t.x == self.x and t.y == self.y:
                    t.take_hit()
                    self.alive = False
                    break

    @staticmethod
    def cancel_pairs(bullets):
        """Destroy both bullets when two occupy the same tile."""
        alive = [b for b in bullets if b.alive]
        for i in range(len(alive)):
            for j in range(i + 1, len(alive)):
                a, b = alive[i], alive[j]
                if a.alive and b.alive and a.x == b.x and a.y == b.y:
                    a.alive = b.alive = False
