import heapq
from collections import deque
from constants import GRID_SIZE, EMPTY, BRICK, STEEL, WATER, FOREST, EAGLE, ASTAR_COST


# ══════════════════════════════════════════════════════════════════════
#  BFS  — shortest hop path, ignores cost
#  Used by: Basic Tank  (Simple Reflex Agent)
# ══════════════════════════════════════════════════════════════════════
def bfs(grid_matrix, start, goal):
    """
    Standard queue-based BFS.
    Treats Empty & Forest as passable. Brick counted as passable (no cost).
    Returns list of (x,y) steps from start→goal, or [].
    """
    sx, sy = start
    gx, gy = goal
    if (sx, sy) == (gx, gy):
        return []

    visited = {(sx, sy): None}
    queue   = deque([(sx, sy)])

    while queue:
        x, y = queue.popleft()
        if x == gx and y == gy:
            path, cur = [], (x, y)
            while cur != (sx, sy):
                path.append(cur)
                cur = visited[cur]
            return list(reversed(path))

        for dx, dy in [(0,-1),(0,1),(-1,0),(1,0)]:
            nx, ny = x+dx, y+dy
            if (nx,ny) in visited: continue
            if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE): continue
            t = grid_matrix[ny][nx]
            # BFS: passable if not steel/water (treats brick as walkable for path planning)
            if t not in (STEEL, WATER) or (nx == gx and ny == gy):
                visited[(nx,ny)] = (x,y)
                queue.append((nx,ny))
    return []


# ══════════════════════════════════════════════════════════════════════
#  Greedy Best-First — single-step, heuristic only
#  Used by: Fast Tank  (Goal-Based Agent)
# ══════════════════════════════════════════════════════════════════════
def greedy_next_step(grid_matrix, start, goal):
    """
    Picks the passable neighbour with lowest Manhattan distance to goal.
    Returns (nx, ny) or None. Does NOT compute full path.
    Local-minima failure is intentional (shows why greedy ≠ optimal).
    """
    sx, sy = start
    gx, gy = goal
    best, best_h = None, float('inf')

    for dx, dy in [(0,-1),(0,1),(-1,0),(1,0)]:
        nx, ny = sx+dx, sy+dy
        if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE): continue
        t = grid_matrix[ny][nx]
        if t in (STEEL, WATER): continue          # hard blocked
        h = abs(nx-gx) + abs(ny-gy)
        if h < best_h:
            best_h, best = h, (nx, ny)
    return best


# ══════════════════════════════════════════════════════════════════════
#  A*  — cost-optimal path
#  Used by: Armor Tank  (Model-Based Reflex Agent)
# ══════════════════════════════════════════════════════════════════════
def astar(grid_matrix, start, goal):
    """
    A* with tile costs: empty/forest=1, brick=3, steel/water=∞.
    Returns list of (x,y) steps, or [].
    Key insight: cost 3 to shoot through 1 brick < cost 6+ to detour.
    """
    sx, sy = start
    gx, gy = goal
    if (sx, sy) == (gx, gy):
        return []

    def h(x, y): return abs(x-gx) + abs(y-gy)

    open_set  = [(h(sx,sy), 0, sx, sy)]
    came_from = {(sx,sy): None}
    g_score   = {(sx,sy): 0}

    while open_set:
        f, g, x, y = heapq.heappop(open_set)
        if x == gx and y == gy:
            path, cur = [], (x,y)
            while cur != (sx,sy):
                path.append(cur)
                cur = came_from[cur]
            return list(reversed(path))

        for dx, dy in [(0,-1),(0,1),(-1,0),(1,0)]:
            nx, ny = x+dx, y+dy
            if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE): continue
            t    = grid_matrix[ny][nx]
            cost = ASTAR_COST.get(t, float('inf'))
            if cost == float('inf') and not (nx==gx and ny==gy): continue
            ng = g + (1 if (nx==gx and ny==gy) else cost)
            if ng < g_score.get((nx,ny), float('inf')):
                g_score[(nx,ny)] = ng
                came_from[(nx,ny)] = (x,y)
                heapq.heappush(open_set, (ng+h(nx,ny), ng, nx, ny))
    return []


# ══════════════════════════════════════════════════════════════════════
#  Minimax + Alpha-Beta Pruning  — Boss Tank
# ══════════════════════════════════════════════════════════════════════
_minimax_stats = {"with_pruning": 0, "without_pruning": 0}

def get_minimax_stats():
    """
    Returns node counts for the report.
    'with_pruning'    — actual nodes evaluated (alpha-beta active).
    'without_pruning' — theoretical O(b^d) estimate, where b=5 (branch
                        factor: 4 moves + shoot) and d = current depth.
                        This matches the spec requirement to measure and
                        report the speedup ratio.  Actual unpruned count
                        is also accumulated via _count_unpruned_max/min
                        if you want an empirical figure; the theoretical
                        estimate is used for the HUD display.
    """
    return dict(_minimax_stats)

def reset_minimax_stats():
    _minimax_stats["with_pruning"]    = 0
    _minimax_stats["without_pruning"] = 0


# ── Unpruned shadow traversal (for accurate without_pruning count) ────
def _count_unpruned_max(boss, player, grid, depth):
    """Full minimax traversal WITHOUT alpha-beta — counts every node."""
    _minimax_stats["without_pruning"] += 1
    if depth == 0:
        return _evaluate(boss, player, grid)
    best = float('-inf')
    for act in _actions_for(boss, grid):
        nb   = _apply(boss, act, grid)
        best = max(best, _count_unpruned_min(nb, player, grid, depth - 1))
    return best


def _count_unpruned_min(boss, player, grid, depth):
    """Full minimax traversal WITHOUT alpha-beta — counts every node."""
    _minimax_stats["without_pruning"] += 1
    if depth == 0:
        return _evaluate(boss, player, grid)
    best = float('inf')
    for act in _actions_for(player, grid):
        np_ = _apply(player, act, grid)
        best = min(best, _count_unpruned_max(boss, np_, grid, depth - 1))
    return best


def minimax_decision(boss_state, player_state, grid_matrix, depth):
    """
    Returns best action for Boss Tank.
    boss_state / player_state: dicts {x, y, hp}
    Actions: UP/DOWN/LEFT/RIGHT/SHOOT

    Side-effect: increments both _minimax_stats counters so the HUD
    and report can display pruned vs unpruned node counts and speedup.
    """
    # Run unpruned shadow traversal first to count without_pruning nodes
    _count_unpruned_max(boss_state, player_state, grid_matrix, depth)

    actions   = _actions_for(boss_state, grid_matrix)
    best_val  = float('-inf')
    best_act  = actions[0]
    alpha     = float('-inf')
    beta      = float('inf')

    for act in actions:
        nb = _apply(boss_state, act, grid_matrix)
        v  = _min_val(nb, player_state, grid_matrix, depth-1, alpha, beta)
        if v > best_val:
            best_val, best_act = v, act
        alpha = max(alpha, best_val)

    return best_act


def _max_val(boss, player, grid, depth, alpha, beta):
    _minimax_stats["with_pruning"] += 1
    if depth == 0:
        return _evaluate(boss, player, grid)
    for act in _actions_for(boss, grid):
        nb = _apply(boss, act, grid)
        alpha = max(alpha, _min_val(nb, player, grid, depth-1, alpha, beta))
        if alpha >= beta:
            return alpha
    return alpha


def _min_val(boss, player, grid, depth, alpha, beta):
    _minimax_stats["with_pruning"] += 1
    if depth == 0:
        return _evaluate(boss, player, grid)
    for act in _actions_for(player, grid):
        np_ = _apply(player, act, grid)
        beta = min(beta, _max_val(boss, np_, grid, depth-1, alpha, beta))
        if beta <= alpha:
            return beta
    return beta


def _actions_for(state, grid):
    x, y = state['x'], state['y']
    acts = ['shoot']
    for dx, dy in [(0,-1),(0,1),(-1,0),(1,0)]:
        nx, ny = x+dx, y+dy
        if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
            t = grid[ny][nx]
            if t not in (STEEL, WATER):
                acts.append((dx, dy))
    return acts


def _apply(state, action, grid):
    if action == 'shoot':
        return dict(state)
    dx, dy = action
    nx, ny = state['x']+dx, state['y']+dy
    if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
        t = grid[ny][nx]
        if t not in (STEEL, WATER):
            return {**state, 'x': nx, 'y': ny}
    return dict(state)


def _evaluate(boss, player, grid):
    """
    Heuristic per spec:
    +60 player within 3 tiles
    +50 player in line-of-sight
    +30 boss adjacent to steel
    +20 per missing player HP
    -40 per missing boss HP
    -20 player in forest
    """
    score = 0
    bx, by = boss['x'], boss['y']
    px, py = player['x'], player['y']
    dist   = abs(bx-px) + abs(by-py)

    if dist <= 3:  score += 60
    if _los(bx, by, px, py, grid): score += 50

    for dx, dy in [(0,-1),(0,1),(-1,0),(1,0)]:
        nx, ny = bx+dx, by+dy
        if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and grid[ny][nx] == STEEL:
            score += 30
            break

    score += max(0, (3 - player.get('hp', 1))) * 20
    score -= max(0, (10 - boss.get('hp', 10))) * 40

    if 0 <= px < GRID_SIZE and 0 <= py < GRID_SIZE:
        if grid[py][px] == FOREST:
            score -= 20

    score += max(0, 15 - dist) * 3
    return score


def _los(bx, by, px, py, grid):
    if bx == px:
        step = 1 if py > by else -1
        for y in range(by+step, py, step):
            if grid[y][bx] in (BRICK, STEEL, WATER): return False
        return True
    if by == py:
        step = 1 if px > bx else -1
        for x in range(bx+step, px, step):
            if grid[by][x] in (BRICK, STEEL, WATER): return False
        return True
    return False
