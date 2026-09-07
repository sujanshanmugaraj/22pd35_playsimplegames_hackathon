#!/usr/bin/env python3
"""
solve.py -- Color Block Crush solver.

Usage:
    python solve.py <level.txt>
    python solve.py <level.txt> --solver complete
    python solve.py <level.txt> --solver fast
    python solve.py <level.txt> --solver complete --verbose
"""

import sys
import re
import time
import heapq
import argparse
from collections import defaultdict, deque

DEFAULT_TIME_LIMIT = 58.0  # margin under the 60s budget

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIRS_H = ((1, 0), (-1, 0))
DIRS_V = ((0, 1), (0, -1))


# --------------------------------------------------------------------------
# Level / block model (built once, immutable during search)
# --------------------------------------------------------------------------

class Block:
    __slots__ = ("id", "color", "offsets", "anchor0", "ice", "axis",
                 "dxmin", "dxmax", "dymin", "dymax",
                 "delta_bits", "exit_anchors", "dist_map", "min_dist", "dirs")

    def __init__(self, bid, color, offsets, anchor0, ice, axis):
        self.id = bid
        self.color = color
        self.offsets = tuple(sorted(offsets))
        self.anchor0 = anchor0
        self.ice = -1 if (ice is None or ice <= 0) else ice
        self.axis = axis
        xs = [dx for dx, dy in self.offsets]
        ys = [dy for dx, dy in self.offsets]
        self.dxmin, self.dxmax = min(xs), max(xs)
        self.dymin, self.dymax = min(ys), max(ys)
        if axis == 'h':
            self.dirs = DIRS_H
        elif axis == 'v':
            self.dirs = DIRS_V
        else:
            self.dirs = DIRS


class Gate:
    __slots__ = ("id", "color", "side", "lo", "hi")

    def __init__(self, gid, color, side, lo, hi):
        self.id, self.color, self.side, self.lo, self.hi = gid, color, side, lo, hi


class Level:
    def __init__(self, w, h, walls, blocks_dict, gates):
        self.w = w
        self.h = h
        self.walls = walls
        self.gates = gates
        self.wall_mask = 0
        for (x, y) in walls:
            self.wall_mask |= 1 << (y * w + x)

        self.ids = sorted(blocks_dict.keys())
        self.blocks = [blocks_dict[b] for b in self.ids]
        self.n = len(self.blocks)
        self.index = {b: i for i, b in enumerate(self.ids)}

        self.has_target = [any(g.color == blk.color for g in gates)
                           for blk in self.blocks]

        for blk in self.blocks:
            self._precompute(blk)

        self.equiv = [(blk.color, blk.offsets, blk.ice, blk.axis or "")
                      for blk in self.blocks]
        counts = defaultdict(int)
        for e in self.equiv:
            counts[e] += 1
        self.has_identical = any(c > 1 for c in counts.values())
        equiv_group = {}
        for i, e in enumerate(self.equiv):
            equiv_group.setdefault(e, []).append(i)
        self.canon_groups = [members for _, members in sorted(equiv_group.items())]

        self.target_idx = [i for i in range(self.n) if self.has_target[i]]

    def _mask_at(self, blk, ax, ay):
        w = self.w
        m = 0
        for dx, dy in blk.offsets:
            m |= 1 << ((ay + dy) * w + (ax + dx))
        return m

    def _fits(self, blk, ax, ay):
        w, h = self.w, self.h
        if ax + blk.dxmin < 0 or ax + blk.dxmax >= w:
            return False
        if ay + blk.dymin < 0 or ay + blk.dymax >= h:
            return False
        return not (self._mask_at(blk, ax, ay) & self.wall_mask)

    def _can_exit_at(self, blk, ax, ay):
        xs = [ax + dx for dx, dy in blk.offsets]
        ys = [ay + dy for dx, dy in blk.offsets]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        for g in self.gates:
            if g.color != blk.color:
                continue
            if g.side == "top" and ymin == 0 and g.lo <= xmin and xmax <= g.hi:
                return True
            if g.side == "bottom" and ymax == self.h - 1 and g.lo <= xmin and xmax <= g.hi:
                return True
            if g.side == "left" and xmin == 0 and g.lo <= ymin and ymax <= g.hi:
                return True
            if g.side == "right" and xmax == self.w - 1 and g.lo <= ymin and ymax <= g.hi:
                return True
        return False

    def _precompute(self, blk):
        w, h = self.w, self.h
        blk.delta_bits = [dy * w + dx for dx, dy in blk.offsets]
        exit_anchors = set()
        valid = []
        for ay in range(h):
            for ax in range(w):
                if not self._fits(blk, ax, ay):
                    continue
                cell = ay * w + ax
                valid.append((ax, ay, cell))
                if self._can_exit_at(blk, ax, ay):
                    exit_anchors.add(cell)
        blk.exit_anchors = frozenset(exit_anchors)

        validset = {(ax, ay) for ax, ay, _ in valid}
        fwd = defaultdict(list)
        for ax, ay, _ in valid:
            for ddx, ddy in blk.dirs:
                cx, cy = ax, ay
                dest = None
                while True:
                    nx, ny = cx + ddx, cy + ddy
                    if (nx, ny) not in validset:
                        break
                    cx, cy = nx, ny
                    dest = (cx, cy)
                if dest is not None:
                    fwd[(ax, ay)].append(dest)
        rev = defaultdict(list)
        for p, dests in fwd.items():
            for q in dests:
                rev[q].append(p)
        dist = {}
        dq = deque()
        for cell in exit_anchors:
            ax, ay = cell % w, cell // w
            dist[(ax, ay)] = 0
            dq.append((ax, ay))
        while dq:
            p = dq.popleft()
            for q in rev.get(p, ()):
                if q not in dist:
                    dist[q] = dist[p] + 1
                    dq.append(q)
        dm = {}
        for (ax, ay), d in dist.items():
            dm[ay * w + ax] = d
        blk.dist_map = dm
        blk.min_dist = min(dist.values()) if dist else 10 ** 6


# --------------------------------------------------------------------------
# State helpers
# --------------------------------------------------------------------------

def _mask_of_fast(blk, anchor_cell):
    m = 0
    for d in blk.delta_bits:
        m |= 1 << (anchor_cell + d)
    return m


def resolve_exits(level, anchors):
    blocks = level.blocks
    changed = True
    while changed:
        changed = False
        nex = sum(1 for a in anchors if a < 0)
        for i in range(level.n):
            a = anchors[i]
            if a < 0:
                continue
            blk = blocks[i]
            if blk.ice >= 0 and nex < blk.ice:
                continue
            if a in blk.exit_anchors:
                anchors[i] = -1
                changed = True
                nex += 1
    return anchors


def initial_state(level):
    anchors = []
    for blk in level.blocks:
        ax, ay = blk.anchor0
        anchors.append(ay * level.w + ax)
    resolve_exits(level, anchors)
    return tuple(anchors)


def is_goal(level, state):
    for i in level.target_idx:
        if state[i] >= 0:
            return False
    return True


def neighbors(level, state):
    w, h = level.w, level.h
    blocks = level.blocks
    nex = 0
    masks = [0] * level.n
    occ = level.wall_mask
    for i in range(level.n):
        a = state[i]
        if a < 0:
            nex += 1
        else:
            m = _mask_of_fast(blocks[i], a)
            masks[i] = m
            occ |= m

    for i in range(level.n):
        a = state[i]
        if a < 0:
            continue
        blk = blocks[i]
        if blk.ice >= 0 and nex < blk.ice:
            continue
        others = occ & ~masks[i]
        ax, ay = a % w, a // w
        dxmin, dxmax, dymin, dymax = blk.dxmin, blk.dxmax, blk.dymin, blk.dymax
        deltas = blk.delta_bits
        for ddx, ddy in blk.dirs:
            cx, cy = ax, ay
            dest = None
            while True:
                nx, ny = cx + ddx, cy + ddy
                if nx + dxmin < 0 or nx + dxmax >= w or ny + dymin < 0 or ny + dymax >= h:
                    break
                base = ny * w + nx
                m = 0
                for d in deltas:
                    m |= 1 << (base + d)
                if m & others:
                    break
                cx, cy = nx, ny
                dest = base
            if dest is not None:
                lst = list(state)
                lst[i] = dest
                resolve_exits(level, lst)
                yield i, dest, tuple(lst)


def canonical(level, state):
    if not level.has_identical:
        return state
    return tuple(tuple(sorted(state[i] for i in g)) for g in level.canon_groups)


def heuristic(level, state):
    total = 0
    blocks = level.blocks
    for i in level.target_idx:
        a = state[i]
        if a >= 0:
            d = blocks[i].dist_map.get(a, blocks[i].min_dist)
            total += d if (d and 0 < d < 10 ** 5) else 1
    return total


def _remaining_targets(level, state):
    return sum(1 for i in level.target_idx if state[i] >= 0)


def quick_unsolvable_check(level, state, log):
    for i in level.target_idx:
        if state[i] >= 0 and level.blocks[i].min_dist >= 10 ** 6:
            log(f"Static check: block {level.ids[i]} can never reach a gate -> UNSOLVABLE")
            return True
    return False


# --------------------------------------------------------------------------
# Decomposition
# --------------------------------------------------------------------------

def _reachable_cells(level, blk):
    w, h = level.w, level.h
    ax0, ay0 = blk.anchor0
    seen = {(ax0, ay0)}
    q = deque([(ax0, ay0)])
    occ = set()
    while q:
        ax, ay = q.popleft()
        for dx, dy in blk.offsets:
            occ.add((ax + dx, ay + dy))
        for ddx, ddy in DIRS:
            nx, ny = ax + ddx, ay + ddy
            if (nx, ny) in seen:
                continue
            if level._fits(blk, nx, ny):
                seen.add((nx, ny))
                q.append((nx, ny))
    return occ


def decompose(level):
    n = level.n
    reach = [_reachable_cells(level, level.blocks[i]) for i in range(n)]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if reach[i] & reach[j]:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


def sub_level(level, idxs):
    bd = {}
    for i in idxs:
        blk = level.blocks[i]
        bd[level.ids[i]] = Block(level.ids[i], blk.color, blk.offsets,
                                 blk.anchor0, None if blk.ice < 0 else blk.ice,
                                 blk.axis)
    return Level(level.w, level.h, level.walls, bd, level.gates)


# --------------------------------------------------------------------------
# Solvers
# --------------------------------------------------------------------------

def _astar(level, time_limit, start_time, log, label=""):
    start = initial_state(level)
    if is_goal(level, start):
        return "SOLVED", []
    if quick_unsolvable_check(level, start, log):
        return "UNSOLVABLE", None

    counter = 0
    best_g = {canonical(level, start): 0}
    open_heap = [(heuristic(level, start), 0, counter, start, [])]
    nodes = 0
    while open_heap:
        if (nodes & 1023) == 0 and time.time() - start_time > time_limit:
            log(f"A*{label}: timeout after {nodes} nodes")
            return "TIMEOUT", None
        f, g, _, state, path = heapq.heappop(open_heap)
        ck = canonical(level, state)
        if g > best_g.get(ck, 1 << 30):
            continue
        nodes += 1
        for i, na, ns in neighbors(level, state):
            nck = canonical(level, ns)
            ng = g + 1
            if ng >= best_g.get(nck, 1 << 30):
                continue
            best_g[nck] = ng
            np_ = path + [(i, na)]
            if is_goal(level, ns):
                log(f"A*{label}: SOLVED {len(np_)} moves, {nodes} nodes")
                return "SOLVED", np_
            counter += 1
            heapq.heappush(open_heap, (ng + heuristic(level, ns), ng, counter, ns, np_))
    log(f"A*{label}: exhausted {nodes} nodes")
    return "UNSOLVABLE", None


def solve_wastar(level, time_limit=DEFAULT_TIME_LIMIT, weight=2.5, log=lambda *a: None):
    start_time = time.time()
    start = initial_state(level)
    if is_goal(level, start):
        return "SOLVED", []
    if quick_unsolvable_check(level, start, log):
        return "UNSOLVABLE", None

    counter = 0
    open_heap = [(weight * heuristic(level, start), 0, counter, start, [])]
    best = {canonical(level, start): 0}
    nodes = 0
    while open_heap:
        if (nodes & 1023) == 0 and time.time() - start_time > time_limit:
            log(f"wA*: timeout after {nodes} nodes")
            return "TIMEOUT", None
        f, g, _, state, path = heapq.heappop(open_heap)
        nodes += 1
        ck = canonical(level, state)
        if best.get(ck, 1 << 30) < g:
            continue
        for i, na, ns in neighbors(level, state):
            nck = canonical(level, ns)
            ng = g + 1
            if ng >= best.get(nck, 1 << 30):
                continue
            np_ = path + [(i, na)]
            if is_goal(level, ns):
                log(f"wA*: SOLVED {len(np_)} moves, {nodes} nodes")
                return "SOLVED", np_
            best[nck] = ng
            counter += 1
            heapq.heappush(open_heap,
                           (ng + weight * heuristic(level, ns), ng, counter, ns, np_))
    log(f"wA*: exhausted {nodes} nodes")
    return "UNSOLVABLE", None


def _score(level, state):
    rem = 0
    dist = 0
    blocks = level.blocks
    for i in level.target_idx:
        a = state[i]
        if a >= 0:
            rem += 1
            d = blocks[i].dist_map.get(a, blocks[i].min_dist)
            dist += d if (d and d > 0) else 1
    return rem, dist


def _block_dests(level, anchors, i):
    w, h = level.w, level.h
    blk = level.blocks[i]
    occ = level.wall_mask
    for j in range(level.n):
        a = anchors[j]
        if a >= 0 and j != i:
            occ |= _mask_of_fast(level.blocks[j], a)
    a = anchors[i]
    ax, ay = a % w, a // w
    dxmin, dxmax, dymin, dymax = blk.dxmin, blk.dxmax, blk.dymin, blk.dymax
    dests = set()
    for ddx, ddy in blk.dirs:
        cx, cy = ax, ay
        dest = None
        while True:
            nx, ny = cx + ddx, cy + ddy
            if nx + dxmin < 0 or nx + dxmax >= w or ny + dymin < 0 or ny + dymax >= h:
                break
            base = ny * w + nx
            m = 0
            for d in blk.delta_bits:
                m |= 1 << (base + d)
            if m & occ:
                break
            cx, cy = nx, ny
            dest = base
        if dest is not None:
            dests.add(dest)
    return dests


def _shorten(level, path, deadline):
    def replay(seq):
        st = list(initial_state(level))
        if is_goal(level, tuple(st)):
            return True, 0
        for idx, (i, na) in enumerate(seq):
            if st[i] < 0:
                return False, -1
            blk = level.blocks[i]
            nex = sum(1 for a in st if a < 0)
            if blk.ice >= 0 and nex < blk.ice:
                return False, -1
            if na not in _block_dests(level, st, i):
                return False, -1
            st[i] = na
            resolve_exits(level, st)
            if is_goal(level, tuple(st)):
                return True, idx + 1
        return is_goal(level, tuple(st)), len(seq)

    ok, solved_len = replay(path)
    if ok and solved_len <= len(path):
        path = path[:solved_len]
    improved = True
    while improved and time.time() < deadline:
        improved = False
        idx = 0
        while idx < len(path):
            if time.time() >= deadline:
                break
            trial = path[:idx] + path[idx + 1:]
            ok, solved_len = replay(trial)
            if ok:
                path = trial[:solved_len]
                improved = True
            else:
                idx += 1
    return path


def _beam_once(level, start, k, time_limit, start_time, log):
    visited = {canonical(level, start)}
    parent = {start: None}
    frontier = [start]
    ply = 0
    while frontier:
        if time.time() - start_time > time_limit:
            return "TIMEOUT", None
        succ = []
        for state in frontier:
            for i, na, ns in neighbors(level, state):
                ck = canonical(level, ns)
                if ck in visited:
                    continue
                visited.add(ck)
                parent[ns] = (state, i, na)
                if is_goal(level, ns):
                    path = []
                    cur = ns
                    while parent[cur] is not None:
                        ps, pi, pa = parent[cur]
                        path.append((pi, pa))
                        cur = ps
                    path.reverse()
                    log(f"Beam(k={k}): SOLVED {len(path)} moves at ply {ply + 1}")
                    return "SOLVED", path
                succ.append(ns)
        if not succ:
            return "EXHAUSTED", None
        if len(succ) > k:
            succ.sort(key=lambda s: _score(level, s))
            succ = succ[:k]
        frontier = succ
        ply += 1
    return "EXHAUSTED", None


def solve_beam(level, time_limit=DEFAULT_TIME_LIMIT, widths=(256, 1024, 4096),
               log=lambda *a: None):
    start_time = time.time()
    start = initial_state(level)
    if is_goal(level, start):
        return "SOLVED", []
    if quick_unsolvable_check(level, start, log):
        return "UNSOLVABLE", None

    exhausted_all = True
    for k in widths:
        remaining = time_limit - (time.time() - start_time)
        if remaining <= 0:
            break
        status, path = _beam_once(level, start, k, remaining, start_time, log)
        if status == "SOLVED":
            n0 = len(path)
            deadline = start_time + min(time_limit, (time.time() - start_time) + 4.0)
            path = _shorten(level, path, deadline)
            log(f"Beam(k={k}): shortened {n0} -> {len(path)} moves")
            return "SOLVED", path
        if status == "TIMEOUT":
            exhausted_all = False
            break
        log(f"Beam(k={k}): exhausted without solution, widening")
    if exhausted_all:
        remaining = time_limit - (time.time() - start_time)
        if remaining > 0.5:
            return solve_wastar(level, time_limit=remaining, weight=3.0, log=log)
    return "TIMEOUT", None


def solve_exitmax(level, time_limit=DEFAULT_TIME_LIMIT, weight=60, log=lambda *a: None):
    start_time = time.time()
    start = initial_state(level)
    if is_goal(level, start):
        return "SOLVED", []
    if quick_unsolvable_check(level, start, log):
        return "UNSOLVABLE", None

    W = weight
    counter = 0
    r0 = _remaining_targets(level, start)
    open_heap = [(W * r0, 0, counter, start)]
    best_g = {canonical(level, start): 0}
    parent = {start: None}
    nodes = 0
    best_rem = r0

    while open_heap:
        if (nodes & 2047) == 0 and time.time() - start_time > time_limit:
            log(f"ExitMax: timeout after {nodes} nodes (best remaining {best_rem})")
            return "TIMEOUT", None
        f, g, _, state = heapq.heappop(open_heap)
        rem = _remaining_targets(level, state)
        if rem < best_rem:
            best_rem = rem
            log(f"ExitMax: {r0 - rem}/{r0} exited @ {nodes} nodes, "
                f"{time.time() - start_time:.1f}s")
        if rem == 0:
            path = []
            cur = state
            while parent[cur] is not None:
                ps, i, na = parent[cur]
                path.append((i, na))
                cur = ps
            path.reverse()
            log(f"ExitMax: SOLVED {len(path)} moves, {nodes} nodes")
            return "SOLVED", path
        ck = canonical(level, state)
        if best_g.get(ck, 1 << 30) < g:
            continue
        for i, na, ns in neighbors(level, state):
            nck = canonical(level, ns)
            ng = g + 1
            if ng >= best_g.get(nck, 1 << 30):
                continue
            best_g[nck] = ng
            if ns not in parent:
                parent[ns] = (state, i, na)
            counter += 1
            heapq.heappush(open_heap,
                           (ng + W * _remaining_targets(level, ns), ng, counter, ns))
    log(f"ExitMax: exhausted {nodes} nodes")
    return "UNSOLVABLE", None


# --------------------------------------------------------------------------
# Drivers (Complete & Fast)
# --------------------------------------------------------------------------

def solve_complete(level, time_limit=DEFAULT_TIME_LIMIT, log=lambda *a: None):
    start_time = time.time()
    has_ice = any(b.ice >= 0 for b in level.blocks)

    if not has_ice:
        groups = decompose(level)
        log(f"Complete: {len(groups)} independent group(s) {[len(g) for g in groups]}")
        all_moves = []
        ok = True
        for g in groups:
            remaining = time_limit - (time.time() - start_time)
            if remaining <= 0:
                ok = False
                break
            sub = sub_level(level, g)
            idmap = {sub.index[level.ids[i]]: i for i in g}
            astar_budget = min(remaining * 0.6, 25.0)
            status, moves = _astar(sub, astar_budget, time.time(), log,
                                   label=f" grp{[level.ids[i] for i in g]}")
            if status == "TIMEOUT":
                remaining = time_limit - (time.time() - start_time)
                status, moves = solve_exitmax(sub, time_limit=remaining, log=log)
            if status == "UNSOLVABLE":
                return "UNSOLVABLE", None
            if status != "SOLVED":
                ok = False
                break
            all_moves.extend((level.ids[idmap[si]], na) for si, na in moves)
        if ok:
            return "SOLVED", all_moves

    remaining = time_limit - (time.time() - start_time)
    status, moves = solve_exitmax(level, time_limit=remaining, log=log)
    if status == "SOLVED":
        return "SOLVED", [(level.ids[i], na) for i, na in moves]
    return status, moves



def solve_fast_single(level, time_limit=DEFAULT_TIME_LIMIT, log=lambda *a: None):
    start_time = time.time()
    has_ice = any(b.ice >= 0 for b in level.blocks)

    # 3.0s allows medium ice levels (Test 5) to solve directly in wA*
    # without triggering expensive beam fallback passes
    quick_budget = min(3.0 if has_ice else 6.0, time_limit * 0.25)
    status, moves = solve_wastar(level, time_limit=quick_budget, weight=2.5, log=log)
    if status in ("SOLVED", "UNSOLVABLE"):
        return status, moves

    remaining = time_limit - (time.time() - start_time)
    if remaining <= 0:
        return "TIMEOUT", None

    widths = (512, 2048) if has_ice else (256, 1024, 4096)
    return solve_beam(level, time_limit=remaining, widths=widths, log=log)

def solve_fast(level, time_limit=DEFAULT_TIME_LIMIT, log=lambda *a: None):
    start_time = time.time()
    has_ice = any(b.ice >= 0 for b in level.blocks)

    if not has_ice:
        groups = decompose(level)
        if len(groups) > 1:
            log(f"Fast: decomposed into {len(groups)} independent group(s)")
            all_moves = []
            for g in groups:
                remaining = time_limit - (time.time() - start_time)
                if remaining <= 0:
                    return "TIMEOUT", None
                sub = sub_level(level, g)
                idmap = {sub.index[level.ids[i]]: i for i in g}
                status, moves = solve_fast_single(sub, time_limit=remaining, log=log)
                if status != "SOLVED":
                    return status, None
                all_moves.extend((level.ids[idmap[si]], na) for si, na in moves)
            return "SOLVED", all_moves

    status, moves = solve_fast_single(level, time_limit=time_limit, log=log)
    if status == "SOLVED":
        return "SOLVED", [(level.ids[i], na) for i, na in moves]
    return status, moves


# --------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------

def _emit(level, status, path):
    print(f"STATUS: {status}")
    if status == "SOLVED":
        print(f"MOVES: {len(path)}")
        for bid, cell in path:
            x, y = cell % level.w, cell // level.w
            print(f"{bid} {x} {y}")
    else:
        print("MOVES: 0")


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(r'i\d+|RA_[A-Z]+|[#.\-|<>^v]|[A-Za-z0-9]')


def _next_nonempty(lines, i):
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    return i


def _tokenize_row(line, expected_cols):
    raw_tokens = line.strip().split()
    tokens = []
    for tok in raw_tokens:
        parts = _TOKEN_RE.findall(tok)
        if parts and "".join(parts) == tok:
            tokens.extend(parts)
        else:
            tokens.append(tok)
    if len(tokens) > expected_cols:
        tokens = tokens[:expected_cols]
    elif len(tokens) < expected_cols:
        tokens.extend(["."] * (expected_cols - len(tokens)))
    return tokens


def parse_level(text):
    lines = text.splitlines()
    i = 0
    w = h = None
    i = _next_nonempty(lines, i)
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("w="):
            w = int(s.split("=")[1].strip())
            i += 1
        elif s.startswith("h="):
            h = int(s.split("=")[1].strip())
            i += 1
        elif s == "COLOR:":
            i += 1
            break
        else:
            i += 1
        i = _next_nonempty(lines, i)
    if w is None or h is None:
        raise ValueError("Could not find w=/h= header")

    expected_cols = w + 2

    def read_grid(lines, i, rows):
        grid = []
        for _ in range(rows):
            i = _next_nonempty(lines, i)
            grid.append(_tokenize_row(lines[i], expected_cols))
            i += 1
        return grid, i

    color_grid, i = read_grid(lines, i, h + 2)
    while lines[i].strip() != "ID:":
        i += 1
    i += 1
    id_grid, i = read_grid(lines, i, h + 2)
    while lines[i].strip() != "MODIFIERS:":
        i += 1
    i += 1
    mod_grid, i = read_grid(lines, i, h + 2)
    return build_level(w, h, color_grid, id_grid, mod_grid)


def build_level(w, h, color_grid, id_grid, mod_grid):
    walls = set()
    block_cells = defaultdict(list)
    block_colors = {}
    for y in range(h):
        for x in range(w):
            c = color_grid[y + 1][x + 1]
            bid = id_grid[y + 1][x + 1]
            if c == "#":
                walls.add((x, y))
            elif bid != ".":
                block_cells[bid].append((x, y))
                block_colors[bid] = c

    blocks = {}
    for bid, cells in block_cells.items():
        minx = min(x for x, y in cells)
        miny = min(y for x, y in cells)
        offsets = frozenset((x - minx, y - miny) for x, y in cells)
        anchor = (minx, miny)
        top_row_y = min(y for x, y in cells)
        tag_x = min(x for x, y in cells if y == top_row_y)
        tag = "."
        if top_row_y + 1 < len(mod_grid) and tag_x + 1 < len(mod_grid[top_row_y + 1]):
            tag = mod_grid[top_row_y + 1][tag_x + 1]
        ice = None
        axis = None
        if tag.startswith("i") and len(tag) > 1 and tag[1:].isdigit():
            ice = int(tag[1:])
        elif tag == "-":
            axis = "h"
        elif tag == "|":
            axis = "v"
        blocks[bid] = Block(bid, block_colors[bid], offsets, anchor, ice, axis)

    gate_cells = defaultdict(list)
    for x in range(w):
        c = color_grid[0][x + 1]
        if c != ".":
            gate_cells[id_grid[0][x + 1]].append(("top", x, c))
        c = color_grid[h + 1][x + 1]
        if c != ".":
            gate_cells[id_grid[h + 1][x + 1]].append(("bottom", x, c))
    for y in range(h):
        c = color_grid[y + 1][0]
        if c != ".":
            gate_cells[id_grid[y + 1][0]].append(("left", y, c))
        c = color_grid[y + 1][w + 1]
        if c != ".":
            gate_cells[id_grid[y + 1][w + 1]].append(("right", y, c))
    gates = []
    for gid, cells in gate_cells.items():
        side = cells[0][0]
        color = cells[0][2]
        idxs = [c[1] for c in cells]
        gates.append(Gate(gid, color, side, min(idxs), max(idxs)))

    return Level(w, h, frozenset(walls), blocks, gates)


# --------------------------------------------------------------------------
# In-process validator
# --------------------------------------------------------------------------

def _simulate(level, path):
    """Re-simulate a solved path and return (valid, error_msg).
    path is a list of (block_id_str, cell_int) pairs."""
    st = list(initial_state(level))
    for step, (bid, cell) in enumerate(path):
        if bid not in level.index:
            return False, f"step {step}: unknown block {bid}"
        i = level.index[bid]
        if st[i] < 0:
            return False, f"step {step}: block {bid} already exited"
        blk = level.blocks[i]
        nex = sum(1 for a in st if a < 0)
        if blk.ice >= 0 and nex < blk.ice:
            return False, f"step {step}: block {bid} is FROZEN"
        # legal destinations for this block in the current state (pure
        # geometry -- cheaper than calling neighbors(), which would compute
        # moves for every other block too just to check one)
        legal_dests = _block_dests(level, st, i)
        if cell not in legal_dests:
            return False, f"step {step}: {bid}->cell {cell} is illegal"
        st[i] = cell
        resolve_exits(level, st)
    ok = is_goal(level, tuple(st))
    return ok, ("" if ok else "path did not reach goal")


# --------------------------------------------------------------------------
# Test runner
# --------------------------------------------------------------------------

SOLVERS = ["complete", "fast"]


def _run_one(level_path, solver_name, time_limit, verbose):
    """Run one (level, solver) combination in-process. Returns a result dict."""
    log_lines = []

    def log(*a):
        if verbose:
            log_lines.append(" ".join(str(x) for x in a))

    text = open(level_path).read()
    level = parse_level(text)

    t0 = time.time()
    try:
        if solver_name == "complete":
            status, path = solve_complete(level, time_limit=time_limit, log=log)
        else:
            status, path = solve_fast(level, time_limit=time_limit, log=log)
    except Exception as e:
        elapsed = time.time() - t0
        return dict(status="ERROR", moves=0, valid=False, valid_msg=str(e),
                    elapsed=elapsed, log=log_lines)
    elapsed = time.time() - t0

    n_moves = len(path) if path else 0
    valid = False
    valid_msg = "-"

    if status == "SOLVED" and path:
        valid, valid_msg = _simulate(level, path)
        valid_msg = "OK" if valid else valid_msg
    elif status == "UNSOLVABLE":
        valid = True   # declared unsolvable is a valid outcome
        valid_msg = "N/A"

    return dict(status=status, moves=n_moves, valid=valid,
                valid_msg=valid_msg, elapsed=elapsed, log=log_lines)


def run_all_tests(test_dir="tests", time_limit=DEFAULT_TIME_LIMIT,
                  solvers=None, verbose=False):
    import glob, os
    if solvers is None:
        solvers = SOLVERS

    files = sorted(glob.glob(os.path.join(test_dir, "*.txt")))
    if not files:
        print(f"No test files found in '{test_dir}/'")
        return

    W_LVL  = 14   # column width for level name
    W_SOL  = 10   # column width for solver name
    W_ST   = 12   # status
    W_MV   =  6   # moves
    W_VL   =  8   # valid
    W_TM   =  9   # time

    hdr = (f"{'Level':<{W_LVL}} {'Solver':<{W_SOL}}"
           f" {'Status':>{W_ST}} {'Moves':>{W_MV}}"
           f" {'Valid':>{W_VL}} {'Time':>{W_TM}}")
    sep = "-" * len(hdr)

    print()
    print("=" * len(hdr))
    print(" COLOR BLOCK CRUSH -- Test Suite Results")
    print("=" * len(hdr))
    print(hdr)
    print(sep)

    # accumulate per-solver totals for the summary
    totals = {s: dict(runs=0, solved=0, passed=0, total_time=0.0, total_moves=0)
              for s in solvers}
    overall_ok = True

    for fpath in files:
        name = os.path.basename(fpath)
        first = True
        for solver in solvers:
            res = _run_one(fpath, solver, time_limit, verbose)

            icon   = "[PASS]" if (res["status"] in ("SOLVED","UNSOLVABLE") and res["valid"]) else "[FAIL]"
            v_disp = res["valid_msg"] if res["valid_msg"] else ("OK" if res["valid"] else "NO")
            lbl    = name if first else ""
            row = (f"{lbl:<{W_LVL}} {solver:<{W_SOL}}"
                   f" {icon+' '+res['status']:>{W_ST+7}}"
                   f" {res['moves']:>{W_MV}}"
                   f" {v_disp:>{W_VL}}"
                   f" {res['elapsed']:>{W_TM-1}.2f}s")
            print(row)

            if verbose:
                for line in res["log"]:
                    print(f"    {line}")

            # accumulate
            t = totals[solver]
            t["runs"]        += 1
            t["total_time"]  += res["elapsed"]
            t["total_moves"] += res["moves"]
            if res["status"] == "SOLVED":
                t["solved"] += 1
            if res["status"] in ("SOLVED","UNSOLVABLE") and res["valid"]:
                t["passed"] += 1
            else:
                overall_ok = False

            first = False
        print(sep)

    # per-solver summary
    print()
    print("=" * len(hdr))
    print(" SUMMARY")
    print("=" * len(hdr))
    shdr = (f"{'Solver':<{W_SOL+2}} {'Tests':>6} {'Solved':>7}"
            f" {'Passed':>7} {'TotalMoves':>11} {'TotalTime':>10} {'AvgTime':>8}")
    print(shdr)
    print("-" * len(shdr))
    for solver in solvers:
        t = totals[solver]
        avg = t["total_time"] / max(t["runs"], 1)
        print(f"{solver:<{W_SOL+2}}"
              f" {t['runs']:>6}"
              f" {t['solved']:>7}"
              f" {t['passed']:>7}"
              f" {t['total_moves']:>11}"
              f" {t['total_time']:>9.2f}s"
              f" {avg:>7.2f}s")
    print("-" * len(shdr))
    print()
    if overall_ok:
        print("  *** ALL TESTS PASSED ***")
    else:
        print("  *** SOME TESTS FAILED OR TIMED OUT ***")
    print()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Color Block Crush solver")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("level_file", nargs="?", default=None,
                       help="Path to a single level file to solve")
    group.add_argument("--test-all", action="store_true",
                       help="Run all tests/*.txt files through all solvers and print a summary")

    parser.add_argument("--solver", "--solve", dest="solver",
                        choices=["complete", "fast"], default="complete",
                        help="Solver to use in single-level mode (default: complete)")
    parser.add_argument("--solvers", dest="solvers", nargs="+",
                        choices=["complete", "fast"],
                        help="Solvers to run in --test-all mode (default: complete fast)")
    parser.add_argument("--test-dir", default="tests",
                        help="Directory containing test *.txt files (default: tests)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--time-limit", type=float, default=DEFAULT_TIME_LIMIT)
    args = parser.parse_args()

    if args.test_all:
        solvers = args.solvers if args.solvers else SOLVERS
        run_all_tests(test_dir=args.test_dir, time_limit=args.time_limit,
                      solvers=solvers, verbose=args.verbose)
        return

    def log(*a):
        if args.verbose:
            print(*a, file=sys.stderr)

    with open(args.level_file, "r") as f:
        text = f.read()

    level = parse_level(text)
    log(f"Parsed: {level.w}x{level.h}, {level.n} blocks, "
        f"{len(level.gates)} gates, {len(level.walls)} walls")

    if args.solver == "complete":
        status, path = solve_complete(level, time_limit=args.time_limit, log=log)
    else:
        status, path = solve_fast(level, time_limit=args.time_limit, log=log)
    _emit(level, status, path)


if __name__ == "__main__":
    main()