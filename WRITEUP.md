# Color Block Crush — Write-up

## 1. State representation

Blocks are indexed `0..n-1` (sorted by their ID character, for determinism).
A **board state is a tuple of `n` integers**: entry `i` is the cell index
(`y*w + x`) of block `i`'s anchor, or `-1` if that block has already exited.
Tuples are hashable and cheap to compare, so they drop straight into the
`visited`/`best-g` dictionaries and the priority-queue.

Each block precomputes, once at load time:

- **`delta_bits`** — the bit offsets of its cells relative to the anchor, so a
  block's occupancy bitmask at anchor cell `a` is `OR(1 << (a + d))`. Occupancy
  of the whole board is a single Python integer (bitboard); wall cells are
  folded into a constant `wall_mask`.
- **`exit_anchors`** — the set of anchor cells from which the block is legally
  positioned to leave through a matching gate. An exit test is then a single
  set membership, not a geometry recomputation.
- **`dist_map`** — a walls-only shortest *slide* distance from every anchor to
  the nearest matching gate (reverse-BFS over the slide graph). This is an
  admissible lower bound (other blocks can only add obstacles) and is used as
  the A\* heuristic.

**Ice** is stored as an unlock threshold per block; the number of exited blocks
is just the count of `-1` entries in the state, so "is this block still frozen"
is `ice >= 0 and exited_count < ice`. **Directional** blocks restrict the set of
slide directions considered.

**Symmetry reduction.** Blocks with identical (color, shape, ice, axis) are
interchangeable. A `canonical()` key sorts the anchors *within* each equivalence
class, so permutations of identical blocks (e.g. the eight 1×1 blue blocks in
test 4, or the many yellow 1×1s in test 5) collapse to one search node. This is
a large win on the duplicate-heavy levels.

## 2. Move generation

From a state we build the occupancy bitboard once, then for each block that is
present and not frozen:

- take the block's own mask out of the occupancy (`others = occ & ~mask_i`);
- for each allowed direction, slide cell-by-cell, stopping before a bounds
  violation or before the swept mask intersects `others`;
- emit the **maximal** stop position as the move (this matches the tests; a note
  on partial stops is below).

After each move we run **`resolve_exits`**: any block sitting on a matching gate
leaves, and because one departure can unfreeze ice blocks or open space for
another, this cascades to a fixed point (iterated in sorted order so results are
deterministic). Move generation and exit resolution share the same bitboard
primitives, which is what makes the engine fast enough (~15k node expansions/s
in pure Python).

Reported moves use the block's **new top-left `(x, y)`**, exactly as the output
format requires.

## 3. The two solvers

Both search the same state graph; they differ in *what guides them* — a genuine
difference in kind, not just a weight.

### Solver 1 — `complete`

Two mechanisms, chosen by level shape:

1. **Independent-region decomposition (no ice).** Two blocks that can never
   occupy a common cell (over walls only, ignoring other movable blocks) can
   never interact, so the level splits into independent sub-puzzles. Each is
   solved **optimally with A\*** and the move lists concatenated. This is why
   test 2 and test 3 come back short (10 and 24 moves) and fast. Decomposition
   is deliberately **disabled when ice is present**, because ice thresholds
   count *global* exits and would be miscounted across independent groups.

2. **Exit-maximising best-first (ice / hard levels).** The priority is
   `f = g + W · (blocks still on the board)`. This is the key idea — see §4.

If A\* can't finish a region optimally within its time slice, that region falls
back to the exit-maximising search, so `complete` still returns a valid solution.

### Solver 2 — `fast` (beam search)

A different *kind* of search from Solver 1. Instead of a global priority queue,
beam search advances **one ply at a time** and keeps only the best `k` states of
each ply (the "beam"); memory and per-ply work are bounded by `k`, so it races
down the tree and returns a valid — not necessarily shortest — solution fast.

- **Scoring.** States are ranked lexicographically by `(blocks-remaining,
  summed-distance-to-gate)` — fewer blocks on the board always wins, so the beam
  is pulled toward exits, with geometry as the tie-break.
- **Widening on failure.** The classic beam failure is discarding a move that
  *temporarily* worsens the score (parking an almost-done block to free space).
  We mitigate with an ascending width ladder `(256, 1024, 4096)`: if a width
  can't get through, we retry wider (a wide enough beam keeps those "worse"
  states alive), each retry with a fresh visited-set so it isn't blocked by what
  the narrower pass pruned. A wider beam gives both a higher success rate *and* a
  shorter path, so the first width wide enough to succeed is already decent.
- **Shortening pass.** Beam paths carry dead motion, so on success we run a
  time-bounded pass that drops any move the sequence still solves without, and
  truncates once the goal is first reached.
- **Unsolvability.** A bounded beam can't prove a level unsolvable; if every
  width empties its beam we confirm with the exhaustive weighted-A\* engine
  before reporting `UNSOLVABLE`.

On the four levels without deep ordering constraints it is fast and short. On
test 4 it still finds a valid solution, but a long one — beam's weakness is
exactly the ordering dependency `complete` was built for (see §6).

### Bonus — `astar`

Plain optimal A\* over raw states, kept as a reference and as the inner engine
for decomposition.

## 4. Why test 4 needed a different idea

test 4 (ice + four directional blocks) breaks a distance heuristic completely.
Inspecting the board shows why: the two blue exit gates are **physically blocked
by the frozen ice blocks** (C sits on the left gate, D on the right), and C/D
only unlock after two blocks leave — but the only blocks that *can* leave first
are the red/green ones through the top and bottom gates.

Instrumenting a breadth-first sweep made the structure precise:

| blocks exited | earliest depth |
|---|---|
| 1 | **22 moves** |
| 2 | 30 |
| 3 | 32 |
| 4 | 33 |

The **first** exit takes ~22 setup moves during which no block leaves and every
block stays roughly the same distance from its gate — a long *flat plateau* on
which a distance heuristic gives no gradient at all, so distance-guided search
just wanders. After that first exit, the rest cascade within a handful of moves.

The exit-maximising search is built for exactly this shape. While no block has
exited, `remaining` is constant, so `f = g + W·remaining` orders purely by depth
— a uniform-cost sweep that crosses the plateau to the *shallowest* state that
gets a block out. The moment an exit happens, `remaining` drops and `f` falls by
`W`, so that branch is pursued immediately and the search dives through the
cascade. Ice needs no special casing: frozen blocks simply become movable as the
exit count passes their threshold, which is precisely what the objective pushes
toward. Result: **test 4 solved, 56 moves, ~41s**, re-simulated and verified to
respect every ice constraint (C and D never move before two blocks have exited).

## 5. Results & comparison

| level | complete | | fast (beam) | | notes |
|---|---|---|---|---|---|
| | moves | time | moves | time | |
| test1 | 2  | <1s  | 2   | <1s  | decomposes into 2 trivial regions |
| test2 | 10 | <1s  | 10  | <1s  | optimal |
| test3 | 24 | ~1s  | 25  | ~1s  | walls; complete optimal, beam near-optimal |
| test4 | 56 | ~41s | ~560| ~44s | ice+directional; beam wanders, complete is clean |
| test5 | 43 | ~3s  | 66  | ~2s  | very tight (2 free cells); ice |

`complete` is the one to trust for correctness and short solutions. `fast` (beam)
is quick and short on the four non-ordering levels; on test 4 it still returns a
valid solution but a long one — the price of a bounded-width search on a level
whose solution needs a long, precise, temporarily-unrewarding maneuver. Both are
validated by `run_tests.py`, which re-simulates every emitted move. (Beam's exact
test-4 length varies run-to-run with how much of the shortening budget it uses.)

## 6. Known limitations / next steps

- **Partial slides.** Both solvers generate only the *maximal* slide in each
  direction. The spec's "slide as far as you want" can be read as allowing any
  intermediate stop; none of the five levels need one, but a held-out level
  could. Adding intermediate stops is a one-line change in move generation at
  the cost of a larger branching factor.
- **test 4 timing.** 41s is within budget but not generous; the cost is entirely
  the ~185k-state plateau crossing in pure Python. A stronger dead-end pruner
  (proving a state can no longer free a required gate) or a C/bitset rewrite
  would cut it substantially.
- **Optimality under ice.** The exit-maximising search returns a valid, short
  solution but not a provably shortest one; making it optimal would require an
  admissible heuristic that accounts for forced exit ordering.
