# Color Block Crush — Solver

> **Hackathon Take-Home Submission**  
> Sliding-block puzzle solver supporting the full rule set: walls, auto-exit cascades, **ice** (`i=N`) and **directional** (`-` / `|`) blocks.  
> Two genuinely different solvers, both returning within 60 seconds on all provided test levels.

---
## Name : Sujan S
## Roll No : 22PD35
## Course : MSc Data Science
---

## 1. What is this puzzle?

Color Block Crush is a sliding-block puzzle on a rectangular grid:

- **Blocks** are colored polyomino shapes (like Tetris pieces, but they never rotate).
- **Gates** are colored openings on the border of the board.
- **A move** picks one block and slides it as far as possible in one direction (left, right, up, down) until it hits a wall, another block, or the board edge.
- **Auto-exit**: after any move, any block now sitting fully aligned with a matching-color gate automatically exits the board. This can cascade (one exit triggers another).
- **Goal**: every block that has a matching gate must exit.

Special rules in harder levels:
- **Ice (`i=N`)**: the block is frozen until at least N other blocks have exited. Then it behaves normally.
- **Directional (`-` or `|`)**: the block can only slide horizontally (`-`) or vertically (`|`).

---

## 2. Setup & Installation

```bash
# No third-party dependencies. Pure Python 3.8+ standard library.
pip install -r requirements.txt   # this is a no-op

# Verify Python version
python --version   # needs >= 3.8
```

---

## 3. Running the Solver

```bash
# Solve a level (default: 'complete' solver)
python solve.py tests/test1.txt

# Choose which solver to use
python solve.py tests/test4.txt --solver complete
python solve.py tests/test4.txt --solver fast

# Print solver debug logs to stderr (stdout stays clean for the grader)
python solve.py tests/test4.txt --solver complete --verbose

# Override the time budget (default: 58s, leaving margin under the 60s limit)
python solve.py tests/test4.txt --time-limit 30

# Run ALL tests in one shot with a full summary table (built into solve.py)
python solve.py --test-all
python solve.py --test-all --solvers complete fast --test-dir tests

# Validate a solution move-by-move (re-simulates to prove legality)
python validate.py tests/test4.txt complete
python validate.py --all                      # validate all tests, both solvers
```

---

## 4. Output Format

Exactly as required by the assignment — only these lines on stdout:

```
STATUS: SOLVED | UNSOLVABLE | TIMEOUT
MOVES: <N>
<block_id> <x> <y>
... (one line per move, only when STATUS is SOLVED)
```

- **`block_id`** — the ID character from the ID layer of the level file.
- **`x y`** — the new top-left anchor position of the block after the slide (0-indexed, origin at top-left).

**Example:**
```
STATUS: SOLVED
MOVES: 2
0 1 2
1 2 0
```

---

## 5. File Structure & Architecture

```
solve.py            ← Main solver + CLI  (submitted grader entry point)
solve_with_time.py  ← Extended version: built-in batch test runner + timing report
validate.py         ← Independent move-by-move legality verifier
animation.py        ← Terminal visualiser: animated dual side-by-side playback
requirements.txt    ← Standard library only — pip install is a no-op
README.md           ← This file
WRITEUP.md          ← Technical write-up (state repr, solver comparison)
tests/
  test1.txt         ← Starter: 4×5, no modifiers
  test2.txt         ← Medium: 6×6, more blocks
  test3.txt         ← Walls: 6×6 with # cells
  test4.txt         ← Ice + Directional: the hardest
  test5.txt         ← Ice only: frozen block unlocks after 1 exit
  test6..10.txt     ← Extra test levels
```

### Architecture Overview
<img width="1024" height="559" alt="image" src="https://github.com/user-attachments/assets/15a1590a-7705-4bc4-8918-16b57277b190" />


  validate.py ──calls──▶ solve.py subprocess ──▶ re-simulates output
  animation.py ─calls──▶ solve.py subprocess ──▶ renders board in terminal
  solve_with_time.py ───▶ same engine as solve.py + batch test runner
```

---

## 5a. `solve_with_time.py` — Batch Test Runner with Timing

`solve_with_time.py` is an **extended version of the solver** that includes a built-in test suite runner and detailed timing report. It has the same solver engine as `solve.py` but adds two modes:

### Single-file mode (identical to solve.py)

```bash
# Solve one level
python solve_with_time.py tests/test1.txt

# Choose solver
python solve_with_time.py tests/test4.txt --solver fast

# With debug logs
python solve_with_time.py tests/test4.txt --solver complete --verbose

# Custom time limit
python solve_with_time.py tests/test4.txt --time-limit 30
```

### Batch test-all mode (built-in)

```bash
# Run ALL tests in tests/ through both solvers and print a full report
python solve_with_time.py --test-all

# Run only one solver
python solve_with_time.py --test-all --solvers complete

# Custom test folder
python solve_with_time.py --test-all --test-dir tests

# With verbose solver logs per test
python solve_with_time.py --test-all --verbose
```

### Sample output


```

> Each row shows `[PASS]` / `[FAIL]`, the status, move count, and wall-clock time. The summary table shows total and average time per solver. Solutions are validated in-process after solving.

---

## 5b. `animation.py` — Real-time Terminal Visualiser

`animation.py` provides a **live animated dual-panel display** in your terminal showing both the `complete` and `fast` solvers replaying their solutions step-by-step, side by side.

### What it shows

```
=== COLOR BLOCK CRUSH -- REALTIME DUAL COMPARISON ===
File: tests/test3.txt | Grid: 6x6 | Speed: 0.15s/move


┌──── COMPLETE ─────┐        ┌──── FAST ─────────┐
Step: 3/24  | Exited: 1/11   Step: 3/25  | Exited: 1/11
Action: Move 'A' -> (2,0)    Action: Move 'A' -> (2,0)
┌────────────────┐            ┌────────────────┐
│▼▼──────────────│            │▼▼──────────────│
│ ██  R1 R1      │            │ ██  R1 R1      │
│    G2 G2       │            │    G2 G2       │
│       ██       │            │       ██       │
└────────────────┘            └────────────────┘

```

- **Colored blocks** are rendered with ANSI colors matching their color letter.
- **Walls** (`#`) appear as gray `██` cells.
- **Frozen (ice) blocks** are shown in cyan.
- **Gate arrows** (`▼`, `▲`, `►`, `◄`) appear on the board border in matching colors.
- Both panels update simultaneously, one move per `speed` seconds.

### How to run

```bash
# Animate one level (default speed: 0.15s per move)
python animation.py tests/test1.txt

# Animate a specific level
python animation.py tests/test4.txt

# Custom speed (seconds per move)
python animation.py tests/test3.txt 0.3      # slower
python animation.py tests/test3.txt 0.05     # faster

# Animate ALL tests in sequence
python animation.py --all
python animation.py --all 0.1
```

### How it works internally

1. Calls `solve.py` (via subprocess) for both `complete` and `fast` solvers.
2. Parses both solution outputs into move lists.
3. Replays both solutions step-by-step in a loop:
   - Applies each move to an in-memory board state.
   - Calls `resolve_exits()` to cascade auto-exits.
   - Renders both boards side-by-side using ANSI escape codes.
   - Clears the terminal and redraws each frame.
4. When one solver finishes before the other, its panel shows `DONE (Goal Reached)` while the other continues.

> **Note:** Animation requires a terminal that supports ANSI color codes (standard on Linux/macOS; on Windows use Windows Terminal or PowerShell — not the old cmd.exe).

---

## 6. Level Format (ASCII)

Each level file has three stacked grids:

```
w=6
h=6
COLOR:         ← Letter = block color; # = wall; . = empty; border = gate color
...
ID:            ← Same grid, but letters = block IDs; border = gate IDs (a,b,c,...)
...
MODIFIERS:     ← Border: ^ v < > (gate direction). Interior: i2, -, |, or .
...
```

**Grid dimensions**: every grid is `(h+2) × (w+2)` — one border row/column on each side for gates.

**Token reference:**

| Location | Token | Meaning |
|---|---|---|
| Interior COLOR | `R G B Y P O W` | Block color |
| Interior COLOR | `#` | Wall cell |
| Interior COLOR | `.` | Empty cell |
| Interior ID | `0-9, A-Z` | Block ID |
| Interior ID | `.` | Empty |
| Interior MODIFIERS | `i2` | Ice — frozen until 2 blocks exit |
| Interior MODIFIERS | `-` | Horizontal-only movement |
| Interior MODIFIERS | `\|` | Vertical-only movement |
| Interior MODIFIERS | `.` | No modifier |
| Border MODIFIERS | `^` `v` `<` `>` | Gate direction (top/bottom/left/right) |

---

## 7. Code Breakdown — solve.py

`solve.py` is a single self-contained file (~900 lines). Every section is separated by a comment banner. Here is a complete walkthrough.

---

### 7.1 Data Model: Block, Gate, Level

#### `Block` (lines 30–51)

```python
class Block:
    __slots__ = ("id", "color", "offsets", "anchor0", "ice", "axis",
                 "dxmin", "dxmax", "dymin", "dymax",
                 "delta_bits", "exit_anchors", "dist_map", "min_dist", "dirs")
```

Stores everything about one block:

| Field | Type | Meaning |
|---|---|---|
| `id` | str | Block ID character from the ID grid |
| `color` | str | Color letter |
| `offsets` | tuple of (dx, dy) | Shape — relative positions of all cells from anchor |
| `anchor0` | (ax, ay) | Starting top-left position |
| `ice` | int | `-1` if no ice; otherwise N = number of exits needed before unfreeze |
| `axis` | str or None | `'h'` (horizontal only), `'v'` (vertical only), or `None` (free) |
| `dxmin/dxmax/dymin/dymax` | int | Bounding box extents (precomputed for fast bounds checks) |
| `delta_bits` | list of int | `dy*w + dx` for each cell; used in bitboard occupancy |
| `exit_anchors` | frozenset | Set of anchor cell indices where this block can auto-exit |
| `dist_map` | dict | Maps anchor cell → slide-distance to nearest exit (BFS precomputed) |
| `min_dist` | int | Minimum distance from any position to any exit |
| `dirs` | tuple | Which directions are allowed: `DIRS`, `DIRS_H`, or `DIRS_V` |

**Why `__slots__`?** Eliminates the per-instance `__dict__`, reducing memory by ~40% when thousands of search nodes reference block data.

#### `Gate` (lines 54–58)

Simple data class: `id`, `color`, `side` (`"top"/"bottom"/"left"/"right"`), `lo`, `hi` (the range of cells the gate spans along its edge).

#### `Level` (lines 61–176)

The immutable board description built once before search begins.

**Constructor steps:**
1. Build `wall_mask` — an integer bitboard where bit `y*w+x` is set if `(x,y)` is a wall. Collision checks become a single `&` operation.
2. Sort blocks deterministically by ID for stable indexing.
3. Detect identical blocks (same color+shape+ice+axis) for canonicalisation symmetry breaking.
4. Call `_precompute(blk)` for each block.

**`_precompute(blk)` — the key setup step (lines 127–176):**

For each block, it runs once at level-load time and computes:

1. **`delta_bits`** — bit offsets for occupancy mask construction.
2. **Valid anchor positions** — every `(ax, ay)` where the block fits on the board (bounds + no wall overlap). Uses `_fits()` which checks bounds and does a bitboard `&` with `wall_mask`.
3. **`exit_anchors`** — subset of valid positions where the block can exit through a matching gate. Uses `_can_exit_at()`: checks the block's edge cells align with a same-color gate.
4. **Walls-only slide graph** — builds `fwd[(ax,ay)] → [destinations]` by simulating slides through the valid-position set (ignoring other blocks). This represents the block's movement structure ignoring dynamic occupancy.
5. **BFS reverse from exit anchors** — traverses the slide graph backwards from every exit anchor to assign each position a "slide distance to exit." Stored in `dist_map`. This is the **admissible heuristic** used by A* and wA*.

---

### 7.2 State Representation

```python
state = tuple(anchor_cell_0, anchor_cell_1, ..., anchor_cell_n-1)
```

A board state is a **tuple of integers**, one per block, in sorted-ID order:
- `anchor_cell = ay * w + ax` (flat cell index of the block's top-left corner)
- `-1` means the block has exited the board

**Why flat integers?** A 12×12 board has 144 cells, so a cell index fits in a byte. Tuples of integers hash and compare extremely fast in Python, which is critical since the search stores millions of states in dicts/sets.

**Key state functions:**

| Function | What it does |
|---|---|
| `initial_state(level)` | Converts `anchor0` fields to cell indices, then calls `resolve_exits` |
| `is_goal(level, state)` | Returns True if all `target_idx` blocks have `state[i] < 0` |
| `resolve_exits(level, anchors)` | Cascading exit loop: checks each block's anchor against its `exit_anchors`; marks as `-1` and repeats until stable |

---

### 7.3 Move Generation (`neighbors`)

```python
def neighbors(level, state):
    # yields (block_index, new_anchor_cell, new_state_tuple)
```

This is the hottest function — called millions of times per solve.

**Steps:**

1. Build `occ` (occupancy bitboard) = `wall_mask | mask_of_each_active_block`. Uses `_mask_of_fast(blk, anchor_cell)` which ORs the precomputed `delta_bits` bits.
2. For each active, non-frozen block:
   - Compute `others = occ & ~masks[i]` (occupancy excluding this block).
   - For each allowed direction (from `blk.dirs`):
     - Walk step-by-step in that direction.
     - At each step, build the block's mask at the new position and check against `others`.
     - Stop when blocked; the last valid position is the slide destination.
   - If a destination exists: copy state, set new anchor, call `resolve_exits`, yield result.

**Ice enforcement**: before trying to move block `i`, check `blk.ice >= 0 and nex < blk.ice`. If frozen, skip it.

**Directional enforcement**: already embedded in `blk.dirs` — horizontal-only blocks have `DIRS_H = ((1,0),(-1,0))`, vertical-only have `DIRS_V = ((0,1),(0,-1))`.

---

### 7.4 Heuristic & Canonicalisation

#### Heuristic (lines 280–288)

```python
def heuristic(level, state):
    # Sum of slide-distance-to-gate for each remaining target block
```

For each target block still on the board, looks up `blk.dist_map[anchor_cell]` — the precomputed BFS distance through the walls-only slide graph from the current position to the nearest exit. This is **admissible** (never overestimates): the actual distance can only be longer due to other blocks blocking slides.

#### Canonicalisation (lines 274–277)

```python
def canonical(level, state):
    if not level.has_identical:
        return state
    return tuple(tuple(sorted(state[i] for i in g)) for g in level.canon_groups)
```

If two blocks have identical color + shape + ice + axis, swapping them produces an equivalent state. `canonical()` collapses these into a sorted tuple so the search doesn't explore mirror images. This can halve the state space on levels with many same-colored 1×1 blocks (like test 5).

---

### 7.5 Decomposition

```python
def decompose(level) -> list[list[int]]
def sub_level(level, idxs) -> Level
```

**Idea**: if no ice is present, blocks whose reachable cell sets never overlap are completely independent. They can never block or affect each other, so their sub-puzzles can be solved separately.

**Algorithm (`decompose`)**:
1. For each block, BFS its full reachable region (ignoring other blocks) via `_reachable_cells`.
2. Union-Find: merge any two blocks whose reachable regions share a cell.
3. Return the connected components.

**`sub_level`**: creates a new `Level` containing only the blocks in one group (same walls and gates). The sub-level is then solved independently, and the moves are mapped back to global block indices.

**Impact**: test 2 has 3 independent groups, so the solver works on groups of 2–4 blocks instead of 10. Test 3 also decomposes cleanly.

> ⚠️ **Ice disables decomposition.** When a block is frozen, its unlock threshold is a global counter (total exits across all blocks). You cannot reason about groups independently — one group's exits affect another group's freeze state.

---

### 7.6 Solver 1 — Complete

**Entry point**: `solve_complete(level, time_limit, log)`

**Philosophy**: Prioritise correctness. Solve optimally where possible, fall back to a more powerful search when needed.

**Algorithm:**

```
if no ice blocks:
    groups = decompose(level)
    for each group:
        try A* with up to 60% of remaining budget
        if A* times out → fall back to ExitMax search
    return concatenated moves

else (ice present, decomposition unsafe):
    run ExitMax search on the full level
```

#### Inner engine: `_astar` (plain A*)

Standard A* with:
- **Priority**: `f = g + h` where `g` = moves so far, `h` = heuristic (slide-distance sum)
- **Dedup**: closed set keyed on `canonical(state)`
- **Time check**: every 1024 nodes to avoid `time.time()` overhead
- **Goal check**: on expansion, not generation

Used for small independent groups where it can find an optimal solution quickly.

#### Inner engine: `solve_exitmax` (Exit-Maximising Best-First)

The key insight for hard levels like test 4:

> The distance-to-gate heuristic is **blind to the real problem structure**. On test 4, the first block to exit needs ~22 setup moves during which no block moves geometrically closer to any gate — a long flat heuristic plateau. A* gets stuck.

**ExitMax** uses a different priority: `f = g + W * remaining_targets` where `W = 60`.

- While no block has exited, `remaining_targets` is constant → the search sweeps the plateau like uniform-cost search, methodically exploring until it finds the first exit.
- The moment a block exits, `remaining` drops by 1 → `f` drops by `W=60`, so that branch jumps to the front of the heap. The search immediately dives into the cascade.
- Ice ordering is handled implicitly: frozen blocks are simply unmovable until the exit count crosses their threshold, which is exactly what "maximise exits" drives toward.

```python
# Priority formula
f = g + W * _remaining_targets(level, state)   # W = 60
```

---

### 7.7 Solver 2 — Fast

**Entry point**: `solve_fast(level, time_limit, log)`

**Philosophy**: Speed over optimality. Use a bounded-width search that sacrifices completeness for drastically lower memory and time cost.

**Algorithm:**

```
if no ice and multiple independent groups:
    decompose and solve each group with solve_fast_single

else:
    solve_fast_single(level)
```

#### `solve_fast_single`

```
1. Try weighted A* (wA*, weight=2.5) for up to min(3s, 25% of budget)
   → Often solves simple levels instantly
   → If SOLVED or UNSOLVABLE, return immediately

2. Fall back to Beam Search with widths:
   → (512, 2048) for ice levels
   → (256, 1024, 4096) for non-ice levels
```

#### Beam Search: `solve_beam` + `_beam_once`

Beam search is a **bounded-width breadth-first search**:

1. Maintain a `frontier` of states (one per "ply"/depth level).
2. Generate all successors of all frontier states.
3. Score each successor: `(blocks_remaining, sum_of_distances)` — fewer blocks always wins, distance as tiebreak.
4. Keep only the best `k` successors as the next frontier.
5. If a goal is found, return the path.
6. If the frontier empties with no goal, try a wider beam.

**Why beam search is different from ExitMax:**

| Property | ExitMax (complete) | Beam Search (fast) |
|---|---|---|
| Search type | Global priority queue (best-first) | Level-synchronous, bounded-width |
| Memory | Grows with all explored states | Fixed to `k` states per ply |
| Completeness | Yes (within time limit) | No — can miss solutions |
| Optimality | Near-optimal | Not optimal |
| Speed | Slower (thorough) | Faster (shallow sweep) |
| Path quality | Short | Often longer (redundant moves) |

**Shortening pass** (`_shorten`): after beam search finds a solution, a post-processing pass greedily tries dropping each move. If the remaining sequence still reaches the goal, the move is discarded. Beam paths often contain redundant sliding — this recovers most of it cheaply.

#### Weighted A* (`solve_wastar`)

Identical to A* but with priority `f = g + weight * h` (weight=2.5). The inflated heuristic makes the search greedier — it finds a solution faster but it may not be optimal. Used as the first-pass "cheap" check before committing to beam search.

---

### 7.8 Parser

```python
def parse_level(text) -> Level
def build_level(w, h, color_grid, id_grid, mod_grid) -> Level
```

**`_tokenize_row`**: handles compound tokens like `i2` (ice modifier) embedded between `.` characters in the MODIFIERS grid. Uses a regex `r'i\d+|RA_[A-Z]+|[#.\-|<>^v]|[A-Za-z0-9]'` to split each line correctly even when tokens touch each other.

**Grid parsing order:**
1. Read `w=` and `h=` from header.
2. Read `(h+2) × (w+2)` COLOR grid (includes one border row/col on each side for gates).
3. Read ID grid in same shape.
4. Read MODIFIERS grid in same shape.

**Block construction** (`build_level`):
- Group cells by block ID → compute offsets relative to top-left anchor.
- Read the modifier tag from the MODIFIERS grid at the block's topmost-leftmost cell.
- Parse `i<N>` for ice, `-` for horizontal, `|` for vertical.

**Gate construction**:
- Scan the border of the COLOR/ID grids.
- Group border cells by gate ID → determine `side`, `lo`, `hi`, and `color`.

---

## 8. Solver Approaches in Detail

### Solver 1 — Complete: Why it solves test 4

Test 4 is the hardest level. It has:
- 14 blocks including 2 ice blocks (`C` and `D`, each requiring 2 prior exits)
- 4 directional blocks (horizontal-only)
- The ice blocks physically sit at the exit gates, blocking everything else

A plain distance heuristic completely fails here. Here is why:

1. The two ice blocks `C` (Red, bottom-right) and `D` (Green, top-left) sit directly in front of the exit gates.
2. Until `C` and `D` unfreeze (need 2 exits each), NO other block can exit — the gates are physically blocked.
3. The setup moves needed to arrange the first two exits produce **no change in any block's distance to any gate**.
4. Result: the heuristic plateau lasts ~22 moves. Standard A* and wA* time out.

**ExitMax solves this** because:
- `W=60` per remaining block overwhelms the `g` cost → the search prioritises states where fewer blocks remain on the board, regardless of distance.
- The flat plateau is crossed by uniform-cost sweep (all states have the same `f` while no block exits).
- The instant block `R` or `G` exits for the first time, the remaining-count drops → that branch's priority jumps by 60 → the search immediately exploits the cascade.

### Solver 2 — Fast: Why beam search is different

Beam search advances **one ply at a time** and discards all but the `k` most-promising states at each depth. This is fundamentally different from ExitMax:

- ExitMax explores the entire plateau thoroughly using a global priority queue.
- Beam search stays shallow, sacrificing any states that look locally bad — even if they were on the only path to a solution.

This is why beam search fails on test 4 (the setup moves look "bad" → they get pruned) but succeeds quickly on tests 1–3 and 5 where the path is locally consistent with the distance heuristic.

---

## 9. Handling Special Rules: Ice & Directional

### Ice

Ice is handled in three places:

1. **`Block.__init__`**: `self.ice = -1 if ice is None or ice <= 0 else ice`  
   A block with no ice gets `ice = -1` so the check `blk.ice >= 0` is always false for non-ice blocks.

2. **`neighbors()`**: Before generating moves for block `i`:
   ```python
   nex = sum(1 for a in state if a < 0)   # count exited blocks
   if blk.ice >= 0 and nex < blk.ice:
       continue   # block is frozen, skip it
   ```

3. **`resolve_exits()`**: The cascade loop also checks ice before auto-exiting a block:
   ```python
   if blk.ice >= 0 and nex < blk.ice:
       continue   # block is at an exit gate but still frozen
   ```

### Directional

Directional constraints are enforced by simply setting `blk.dirs` at construction time:

```python
if axis == 'h':   self.dirs = DIRS_H   # = ((1,0), (-1,0))
elif axis == 'v': self.dirs = DIRS_V   # = ((0,1), (0,-1))
else:             self.dirs = DIRS     # all four directions
```

`neighbors()` iterates `for ddx, ddy in blk.dirs` — so directional blocks naturally never generate moves in forbidden directions. No special-case code needed anywhere else.

---
## 10. Test Results

### Optimal Move Sequence Output
<img width="296" height="886" alt="image" src="https://github.com/user-attachments/assets/0386a5d7-4b07-44cf-a1d8-ed0dd3f47e88" />

> **Specification & Output Compliance:** Raw terminal output generated by `--solver complete` solving `test4.txt`. The solver emits the exact competition standard: a `STATUS: SOLVED` header, the optimal move count (`MOVES: 56`), and the step-by-step block translation coordinates without intermediate formatting noise.

---

### Automated Test Suite Benchmarks
<img width="597" height="344" alt="Screenshot 2026-09-06 232456" src="https://github.com/user-attachments/assets/f4130d8c-729c-4ae1-8a94-68eb77b45fec" />

> **Dual-Engine Performance Comparison:** Full benchmark run across the standard test suite (`test1.txt` – `test5.txt`). While `complete` guarantees minimum path lengths (56 moves on Test 4), `fast` leverages bounded anytime beam search to slash execution time on deep combinatorial plateaus from **41.60s down to 16.57s** while passing all validation checks.

---

### Real-Time Dual-Solver Visualizer
<img width="476" height="278" alt="image" src="https://github.com/user-attachments/assets/59f5b9c4-eef1-4dd3-b8b4-62c267df6010" />

> **Synchronous Execution Animation:** Live terminal rendering running `complete` (left) and `fast` (right) side-by-side on `test3.txt`. The display visualizes dynamic board states, directional borders, thawed ice status, and live move steps, demonstrating path divergence and search behavior in real time.

> Both solvers return within 60 seconds on all 5 test levels. 
---

## 11. Validation & Verification

Every solution is independently verified by `validate.py`, which re-simulates the output move-by-move without trusting the solver:

```bash
# Validate one level
python validate.py tests/test4.txt complete

# Validate all tests, both solvers — prints a summary table
python validate.py --all

# Validate using a different solver script
python validate.py --all --script solve_with_time.py
```

**What `validate.py` checks per move:**
1. Block exists in the level.
2. Block has not already exited.
3. Block is not frozen (ice constraint).
4. Destination is a legal slide (checked via `solve.neighbors`).
5. Final board state is a goal (all target blocks exited).

Exit code is `0` if all tests pass, `1` if any test fails.
