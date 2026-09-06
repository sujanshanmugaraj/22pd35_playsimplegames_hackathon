#!/usr/bin/env python3
"""validate.py <level.txt> [solver] -- run a solver and re-simulate its output
to prove every move is legal and the level is truly solved (ice + directional
rules included). Non-zero exit on any violation."""
import sys, subprocess, solve


def simulate(level, moves):
    st = list(solve.initial_state(level))
    w = level.w
    for step, (bid, x, y) in enumerate(moves):
        if bid not in level.index:
            raise AssertionError(f"move {step}: unknown block {bid}")
        i = level.index[bid]
        if st[i] < 0:
            raise AssertionError(f"move {step}: block {bid} already exited")
        blk = level.blocks[i]
        nex = sum(1 for a in st if a < 0)
        if blk.ice >= 0 and nex < blk.ice:
            raise AssertionError(f"move {step}: block {bid} FROZEN "
                                 f"(ice={blk.ice}, {nex} exited)")
        legal = {na for _, na, _ in _moves_for(level, tuple(st), i)}
        cell = y * w + x
        if cell not in legal:
            legalxy = sorted((c % w, c // w) for c in legal)
            raise AssertionError(f"move {step}: {bid}->({x},{y}) illegal. legal={legalxy}")
        st[i] = cell
        solve.resolve_exits(level, st)
    return tuple(st)


def _moves_for(level, state, only_i):
    for i, na, ns in solve.neighbors(level, state):
        if i == only_i:
            yield i, na, ns


def main():
    path = sys.argv[1]
    solver = sys.argv[2] if len(sys.argv) > 2 else "complete"
    out = subprocess.run([sys.executable, "solve.py", path, "--solver", solver],
                         capture_output=True, text=True)
    lines = out.stdout.strip().splitlines()
    if not lines:
        print("NO OUTPUT", out.stderr[-500:]); sys.exit(1)
    status = lines[0].split(":")[1].strip()
    print(f"[{path} / {solver}] {status}")
    if status != "SOLVED":
        return
    n = int(lines[1].split(":")[1])
    moves = []
    for ln in lines[2:2 + n]:
        b, x, y = ln.split()
        moves.append((b, int(x), int(y)))
    level = solve.parse_level(open(path).read())
    end = simulate(level, moves)
    assert solve.is_goal(level, end), "ran but NOT solved!"
    exited = sorted(level.ids[i] for i in range(level.n) if end[i] < 0)
    print(f"  VALID: {n} moves, all legal, solved. Exited: {exited}")


if __name__ == "__main__":
    main()
