# Color Block Crush — Technical Write-Up

**Name:** Sujan S  
**Roll No:** 22PD35  
**Course:** MSc Data Science  

---

## 1. State Representation

### Board State

A board state is a **tuple of `n` integers**, one per block, indexed `0..n-1` (blocks sorted by their ID character for determinism):

```python
state = (anchor_0, anchor_1, ..., anchor_{n-1})
```

Each entry is:
- `anchor_i = y * w + x` — the flat cell index of block `i`'s top-left (anchor) position
- `-1` — block has already exited the board

**Why a flat tuple of integers?**
- A 12×12 board has 144 cells → fits in a single byte per block.
- Tuples are hashable in O(n) and compare equal in O(n) — they go directly into `dict`/`set` structures used for visited sets and best-g tables.
- No object allocation per state — the search creates millions of states; tuples are the fastest Python structure for this.

### Precomputed Block Data

Each `Block` object stores geometry precomputed once at level-load time:

| Field | Type | What it stores |
|---|---|---|
| `offsets` | tuple of `(dx, dy)` | Shape of the block relative to anchor |
| `delta_bits` | list of int | `dy*w + dx` for each cell; used in bitboard computation |
| `exit_anchors` | frozenset | Anchor cells where this block can legally auto-exit |
| `dist_map` | dict | `anchor_cell → slide_distance_to_nearest_gate` (BFS over walls-only slide graph) |
| `min_dist` | int | Minimum over all `dist_map` values; used as fallback |
| `dirs` | tuple | `DIRS`, `DIRS_H`, or `DIRS_V` — enforces directional constraint |

### Bitboard Occupancy

The whole board's occupancy is a single Python integer:

```python
# Block i occupies these bits at anchor cell a:
mask_i = OR(1 << (a + d) for d in blk.delta_bits)

# Total occupancy including walls:
occ = wall_mask | mask_0 | mask_1 | ... | mask_{n-1}
```

Wall cells are folded into a constant `wall_mask` at level-load time. Collision detection between two blocks becomes a single bitwise `AND` — O(1) in Python's arbitrary-precision integers.

### Ice Constraint

```python
blk.ice = -1         # no ice (never frozen)
blk.ice = N          # frozen until N other blocks have exited
```

The current exited count is just:
```python
nex = sum(1 for a in state if a < 0)
```

A block is frozen if `blk.ice >= 0 and nex < blk.ice`. No extra state is needed — the constraint is derived directly from the state tuple.

### Symmetry Reduction (Canonicalisation)

Blocks with identical `(color, shape, ice, axis)` are interchangeable — swapping two such blocks produces an equivalent board state. The `canonical()` function collapses these:

```python
def canonical(level, state):
    if not level.has_identical:
        return state
    # Sort anchor values within each equivalence class
    return tuple(tuple(sorted(state[i] for i in g)) for g in level.canon_groups)
```

**Impact:** Test 4 has 8 identical 1×1 blue blocks. Without canonicalisation, those 8! = 40,320 permutations would each produce a distinct state in the search. With it, they all collapse to one. Test 5 has even more yellow 1×1 blocks — canonicalisation is a large win there.

---

## 2. Move Generation

### `neighbors(level, state)` — the hot path

Called millions of times per solve. Steps:

1. **Build occupancy once per state:**
   ```python
   occ = wall_mask
   for i in range(n):
       if state[i] >= 0:
           occ |= _mask_of_fast(blocks[i], state[i])
   ```

2. **For each active, non-frozen block `i`:**
   - Compute `others = occ & ~masks[i]` (everything except this block)
   - For each allowed direction in `blk.dirs`:
     - Walk step-by-step in that direction
     - At each new position, compute the block's mask and check `mask & others`
     - Stop when blocked; the last unblocked position is the destination
   - If a destination exists: copy state, set new anchor, call `resolve_exits`, yield

3. **`resolve_exits` (cascade auto-exit):**
   ```python
   while changed:
       nex = count of -1 entries
       for each active block:
           if not frozen and anchor in exit_anchors:
               mark as exited (-1)
               changed = True
   ```
   One move can cause a chain of exits — each new exit may unfreeze an ice block, which may immediately exit itself, and so on.

### Directional Blocks

Directional blocks need zero special-case code. At construction time:
```python
if axis == 'h':   blk.dirs = DIRS_H   # ((1,0), (-1,0))
elif axis == 'v': blk.dirs = DIRS_V   # ((0,1), (0,-1))
else:             blk.dirs = DIRS     # all 4 directions
```
The move generator naturally iterates only the allowed directions.

### Output Format

Each move is reported as the block's new anchor `(x, y)`:
```
<block_id> <x> <y>
```
Where `x = anchor_cell % w`, `y = anchor_cell // w`. This is the block's **new top-left position** after the slide, exactly as the spec requires.

---

## 3. Heuristic

### Admissible Distance-to-Gate

For A\* and weighted A\* (wA\*), the heuristic is:

```python
h(state) = sum of dist_map[anchor_i] for each remaining target block i
```

`dist_map` is a **walls-only slide distance** — precomputed via BFS backward from exit anchors through the slide graph (ignoring other movable blocks). This is **admissible**: real slide distance can only be ≥ walls-only slide distance, because other blocks add obstacles but never remove them.

**Why not Euclidean/Manhattan?** Blocks slide to maximal positions, not single steps. The number of slides needed is not the number of cells moved. The walls-only slide graph captures the actual structure of the movement.

### When the Heuristic Fails

The distance heuristic completely fails on **test 4** (see §5). The two ice blocks (`C`, `D`) sit directly in front of the exit gates, blocking them. No block can exit until `C` and `D` unfreeze. But `C` and `D` only unfreeze after 2 blocks exit first. The blocks that exit first must travel to the top/bottom gates — a ~22 move journey with no reduction in any block's `dist_map` value.

Result: the heuristic plateau is ~22 moves wide. A\* and wA\* time out because every state on the plateau has the same `h` value and `g` grows without any pruning power.

---

## 4. Decomposition

### Theory

If blocks `A` and `B` can never occupy the same cell (considering walls but ignoring other movable blocks), they can never block each other. Their sub-puzzles are **fully independent** — solving them separately and concatenating the moves gives a valid global solution.

### Algorithm (`decompose`)

```python
# 1. BFS the full reachable region for each block (walls only, no other blocks)
reach[i] = all cells block i could ever reach

# 2. Union-Find: merge any two blocks whose regions share a cell
for i, j in all pairs:
    if reach[i] & reach[j]:
        union(i, j)

# 3. Return connected components
```

### `sub_level`

Creates a new `Level` object containing only the blocks in one group, but with the same walls and gates. The sub-level is solved independently, and moves are mapped back to global block IDs.

### Why Ice Disables Decomposition

Ice thresholds count **global** exits. If block `C` in group 1 has `ice=2`, it requires 2 total exits — which might come from group 2. You cannot solve the groups independently because one group's exits affect another group's unfreeze state. Decomposition is skipped entirely when any block has `ice >= 0`.

### Impact on Test Results

| Level | Groups | Effect |
|---|---|---|
| test1 | 2 | Each group has only 1 block → trivial |
| test2 | 3 | Groups of 2–4 blocks → A\* optimal per group |
| test3 | 2–3 | Similar decomposition benefit |
| test4 | 1 (ice) | Decomposition disabled → full ExitMax search |
| test5 | 1 (ice) | Decomposition disabled → full ExitMax search |

---

## 5. Solver 1 — Complete (Dependency-Aware)

### Design Philosophy

**Correctness first.** Find the correct answer within the time budget. Use the most powerful algorithm available for each sub-problem.

### Algorithm Flow

```
solve_complete(level):
    if no ice blocks:
        groups = decompose(level)
        for each group:
            try _astar(sub_level) with 60% of remaining budget
            if TIMEOUT:
                try solve_exitmax(sub_level) with remaining budget
            if UNSOLVABLE:
                return UNSOLVABLE
        return concatenated moves
    else:
        return solve_exitmax(full_level)
```

### Inner Engine 1: Plain A\* (`_astar`)

Standard A\* with:
- **Priority:** `f = g + h(state)` where `h` = sum of dist_map values
- **Visited set:** keyed on `canonical(state)` — deduplicates symmetry-equivalent states
- **Time check:** every 1024 nodes (avoids `time.time()` overhead on the hot path)
- **Optimality:** guaranteed (heuristic is admissible)

Used for small independent groups where it finishes quickly and returns the shortest solution.

### Inner Engine 2: Exit-Maximising Search (`solve_exitmax`)

The breakthrough idea for test 4. Priority function:

```python
f = g + W * remaining_targets(state)    # W = 60
```

Where `remaining_targets` = number of target blocks still on the board.

**Why this works on test 4:**

| Phase | What happens |
|---|---|
| Setup (0–22 moves) | No block exits → `remaining` is constant → `f = g + constant` → search sweeps the plateau like uniform-cost search, methodically exploring until it finds the first exit |
| First exit (move ~22) | `remaining` drops by 1 → `f` drops by `W=60` → that branch jumps 60 positions up the heap → search immediately dives to exploit it |
| Cascade (moves 23–33) | Exits cascade quickly → each triggers another heap dive |
| Ice unfreeze (after 2 exits) | `C` and `D` unfreeze automatically as `nex` passes their threshold |

The ice ordering is handled **implicitly** — frozen blocks are simply unmovable in `neighbors()`, so the search naturally finds states where the prerequisites are met before the frozen blocks are moved.

**Result:** test 4 solved in 56 moves, ~41 seconds.

---

## 6. Solver 2 — Fast (Beam Search)

### Design Philosophy

**Speed over optimality.** Find a valid solution as quickly as possible. Use a bounded-width search that caps memory and per-step work.

### Algorithm Flow

```
solve_fast(level):
    if no ice and multiple groups:
        decompose and solve each group with solve_fast_single

solve_fast_single(level):
    1. try solve_wastar(weight=2.5, budget=min(3s, 25% of limit))
       → quick win on simple levels
    2. if TIMEOUT: try solve_beam(widths=(256, 1024, 4096))
```

### Weighted A\* (`solve_wastar`)

Identical to A\* but priority is `f = g + weight * h` with `weight = 2.5`. The inflated heuristic makes the search greedier — it rushes toward exits faster but may find a longer path. Used as the first cheap pass before committing to beam search.

### Beam Search (`solve_beam` + `_beam_once`)

**Core idea:** advance one ply at a time, keep only the `k` best states.

```
frontier = {initial_state}
visited = {canonical(initial_state)}

for each ply:
    successors = all neighbors of all states in frontier
    score each: (blocks_remaining, sum_of_distances_to_gate)
    keep only the k best-scoring successors → new frontier
    if goal found → return path
    if frontier empty → EXHAUSTED (try wider k)
```

**Scoring:** `(blocks_remaining, sum_distances)` — fewer blocks always wins; distance breaks ties. This pulls the beam toward exits.

**Widening on failure:** if beam width `k` fails (exhausts without a solution), retry with larger `k`. Each retry uses a fresh `visited` set so it isn't blocked by what the narrower pass pruned. Ascending ladder: `(256, 1024, 4096)` for non-ice; `(512, 2048)` for ice levels.

**Shortening pass (`_shorten`):** beam paths carry dead motion (redundant slides). After finding a solution, greedily try dropping each move — if the remaining sequence still reaches the goal, discard the move. Time-bounded to 4 extra seconds.

### Why Beam Search is Genuinely Different from ExitMax

| Property | ExitMax (Solver 1) | Beam Search (Solver 2) |
|---|---|---|
| Search type | Global priority queue | Level-synchronous, bounded-width |
| Memory | Grows with all explored states | Fixed: k states per ply |
| Completeness | Yes (within time) | No — can miss solutions |
| Optimality | Near-optimal | Not optimal |
| Handles ordering | Yes (plateau crossing) | No (ordering moves look "bad" and get pruned) |
| Speed | Slower (thorough) | Faster (shallow sweep) |
| Path length | Short | Often longer before shortening |

They are **different in kind** — not the same algorithm at different weights.

---

## 7. Why Test 4 is Hard

Test 4's structure, revealed by instrumentation:

```
Board: 6×6 | 14 blocks | 2 ice (C, D) | 4 directional (0,1,2,3, horizontal)

Ice block C (Red 2×2, bottom-left):  ice=2, sits at left exit gate
Ice block D (Green 2×2, top-right):  ice=2, sits at right exit gate

→ Nothing can exit until C and D unfreeze
→ C and D unfreeze after 2 exits
→ Only Red/Green blocks can exit (top/bottom gates)
→ Getting Red/Green to the top/bottom gates takes ~22 moves
→ During those 22 moves: no exit, no distance reduction, heuristic is flat
```

BFS depth to each exit milestone:

| Exits | Depth (moves) |
|---|---|
| 0 (start) | 0 |
| **1st exit** | **22** |
| 2nd exit | 30 |
| 3rd exit | 32 |
| 4th (goal) | 33 |

This ~22 move plateau is why plain A\* and wA\* time out: they expand ~185k states during the plateau, all with identical heuristic values, before any useful pruning occurs.

ExitMax's `W=60` weight turns the plateau into a uniform-cost sweep. Once the first exit happens, the score drops by 60 and the cascade begins immediately.

---

## 8. Results & Comparison

### Complete Solver

| Level | Grid | Blocks | Special | Status | Moves | Time |
|---|---|---|---|---|---|---|
| test1 | 4×5 | 2 | — | SOLVED | 2 | < 1s |
| test2 | 6×6 | 10 | — | SOLVED | 10 | < 1s |
| test3 | 6×6 | 11 | walls | SOLVED | 24 | ~1s |
| test4 | 6×6 | 14 | ice + directional | SOLVED | 56 | ~41s |
| test5 | 3×7 | 14 | ice | SOLVED | 43 | ~3s |

### Fast Solver (Beam Search)

| Level | Status | Moves | Time | Notes |
|---|---|---|---|---|
| test1 | SOLVED | 2 | < 1s | wA\* wins immediately |
| test2 | SOLVED | 10 | < 1s | wA\* wins immediately |
| test3 | SOLVED | 25 | ~1s | beam width 256, 1 extra move |
| test4 | SOLVED | ~560 | ~44s | beam can't navigate the plateau efficiently |
| test5 | SOLVED | 66 | ~3s | beam correct but 23 moves longer than complete |

### Analysis

- `complete` is strictly better on move quality for every test.
- `fast` is competitive on speed for tests 1–3 and 5.
- On test 4, `fast` still returns a valid solution (all moves verified legal) but the path is ~10× longer — this is expected: beam search discards ordering-dependent "setup" moves as they look unrewarding locally.
- Both solvers return **within 60 seconds** on all provided test levels.

---

## 9. Tools & Supporting Scripts

### `solve_with_time.py` — Extended Solver with Built-in Batch Runner

Same engine as `solve.py`, but adds `--test-all` mode:

```bash
python solve_with_time.py --test-all
```

Runs all `tests/*.txt` files through both solvers in-process, validates each solution, and prints a full report:

```
Level          Solver          Result  Moves      Time
test1.txt      complete  [PASS] SOLVED      2    0.04s
               fast      [PASS] SOLVED      2    0.03s
...
SUMMARY
Solver      Tests  Solved  Passed  TotalMoves  TotalTime  AvgTime
complete        5       5       5         135    46.17s    9.23s
fast            5       5       5         663    39.50s    9.70s
  *** ALL TESTS PASSED ***
```

### `validate.py` — Independent Move Verifier

Re-simulates the solver's output from scratch (without trusting the solver's own logic). Checks per move:
1. Block exists and hasn't exited already.
2. Block is not frozen (ice check).
3. Destination is a legal slide in the current state.
4. Final state is a goal (all target blocks exited).

```bash
python validate.py tests/test4.txt complete   # one level
python validate.py --all                       # all tests, both solvers
```

### `animation.py` — Terminal Visualiser

Runs both solvers via subprocess, then replays both solutions side-by-side in the terminal using ANSI colors:

```bash
python animation.py tests/test3.txt       # animate one level
python animation.py tests/test3.txt 0.05  # custom speed
python animation.py --all                  # all tests in sequence
```

Shows colored blocks, walls (gray), frozen blocks (cyan), and gate arrows updating in real-time.

---

## 10. Known Limitations & Potential Improvements

### Partial Slides

Both solvers generate only the **maximal** slide (block slides as far as possible). The spec says "slide as far as you want" — intermediate stops are technically allowed. None of the five provided tests require them, but a held-out level could. Adding them is a one-line change in move generation at the cost of a larger branching factor (up to `w` or `h` new moves per block per direction).

### Test 4 Timing

41 seconds is within budget but not generous. The cost is the ~185k-state plateau crossing in pure Python (~15k nodes/s). Improvements:

- **Dead-end pruner:** detect states where a required gate is permanently blocked.
- **C extension / bitset library:** the bitboard operations would benefit enormously from C-speed integers.
- **Better weight tuning:** `W=60` was chosen empirically; adaptive weight might help.

### Optimality Under Ice

`solve_exitmax` returns a valid, short solution but not provably shortest. Making it optimal would require an admissible heuristic that accounts for forced exit ordering — significantly harder than the walls-only slide distance.

### Beam Search Improvement for Ordering Levels

The beam search could be improved for test 4 by adding a **lookahead** that detects ice blocks blocking gates and temporarily boosts the priority of moves that contribute to unlocking them. This would require problem-specific knowledge that the current generic scorer doesn't have.
