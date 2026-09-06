#!/usr/bin/env python3
import sys
import time
import os
import re
import subprocess

# ANSI color escape codes
COLORS = {
    'R': '\033[91m',    # Bright Red
    'G': '\033[92m',    # Bright Green
    'B': '\033[94m',    # Bright Blue
    'Y': '\033[93m',    # Bright Yellow
    'P': '\033[95m',    # Bright Magenta / Pink
    'O': '\033[33m',    # Dark Yellow / Orange
    'W': '\033[97m',    # White
    'RESET': '\033[0m', # Default Terminal Color
    'WALL': '\033[90m', # Gray / Dark
    'ICE': '\033[96m',  # Cyan / Ice blue
    'BOLD': '\033[1m',
}

ANSI_REGEX = re.compile(r'\033\[[0-9;]*m')

def visible_len(s):
    """Calculates visible terminal width excluding ANSI color codes."""
    return len(ANSI_REGEX.sub('', s))

def pad_visible(s, width):
    """Pads string to exact terminal width regardless of ANSI codes."""
    vlen = visible_len(s)
    if vlen < width:
        return s + ' ' * (width - vlen)
    return s

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def build_board_lines(level, state, step, total_steps, last_action, solver_name, header_color):
    w, h = level.w, level.h
    grid = [['  ' for _ in range(w)] for _ in range(h)]

    # 1. Draw walls
    for (x, y) in level.walls:
        grid[y][x] = f"{COLORS['WALL']}██{COLORS['RESET']}"

    # 2. Count exited blocks
    nex = sum(1 for a in state if a < 0)

    # 3. Draw active blocks
    for i in range(level.n):
        a = state[i]
        if a < 0:
            continue
        blk = level.blocks[i]
        ax, ay = a % w, a // w
        is_frozen = blk.ice >= 0 and nex < blk.ice
        col = COLORS['ICE'] if is_frozen else COLORS.get(blk.color, COLORS['W'])

        for dx, dy in blk.offsets:
            gx, gy = ax + dx, ay + dy
            if 0 <= gx < w and 0 <= gy < h:
                grid[gy][gx] = f"{col}█{blk.id}{COLORS['RESET']}"

    # 4. Top/Bottom gate borders
    top_border = ["──"] * w
    bot_border = ["──"] * w
    for g in level.gates:
        col = COLORS.get(g.color, COLORS['W'])
        for x in range(g.lo, g.hi + 1):
            if g.side == "top":
                top_border[x] = f"{col}▼▼{COLORS['RESET']}"
            elif g.side == "bottom":
                bot_border[x] = f"{col}▲▲{COLORS['RESET']}"

    # 5. Left/Right gate borders
    left_border = ["│ "] * h
    right_border = [" │"] * h
    for g in level.gates:
        col = COLORS.get(g.color, COLORS['W'])
        for y in range(g.lo, g.hi + 1):
            if g.side == "left":
                left_border[y] = f"{col}► {COLORS['RESET']}"
            elif g.side == "right":
                right_border[y] = f"{col} ◄{COLORS['RESET']}"

    # Target width matching the box: 2 chars per cell + 4 border chars
    box_width = 2 * w + 4
    col_width = max(box_width, 28)

    # Format header lines
    title_raw = f" {solver_name.upper()} "
    dash_total = max(0, col_width - len(title_raw) - 2)
    d_left = dash_total // 2
    d_right = dash_total - d_left
    header_line = f"{header_color}{COLORS['BOLD']}┌{'─' * d_left}{title_raw}{'─' * d_right}┐{COLORS['RESET']}"

    line_step = f"Step: {step}/{total_steps}  |  Exited: {nex}/{level.n}"
    line_act = f"Action: \033[93m{last_action}\033[0m"

    lines = [
        pad_visible(header_line, col_width),
        pad_visible(line_step, col_width),
        pad_visible(line_act, col_width),
        pad_visible("┌─" + "".join(top_border) + "─┐", col_width)
    ]
    for y in range(h):
        row_str = "".join(grid[y])
        lines.append(pad_visible(f"{left_border[y]}{row_str}{right_border[y]}", col_width))
    lines.append(pad_visible("└─" + "".join(bot_border) + "─┘", col_width))

    return lines, col_width

def get_solver_solution(solver_script, level_file, mode):
    cmd = [sys.executable, solver_script, level_file, "--solver", mode]
    res = subprocess.run(cmd, capture_output=True, text=True)
    lines = res.stdout.strip().splitlines()
    if not lines or "STATUS: SOLVED" not in lines[0]:
        return "UNSOLVABLE", []
    
    moves = []
    for line in lines[2:]:
        parts = line.strip().split()
        if len(parts) == 3:
            bid, x, y = parts[0], int(parts[1]), int(parts[2])
            moves.append((bid, x, y))
    return "SOLVED", moves

def animate_dual(level_file, speed=0.15):
    try:
        from solve import parse_level, initial_state, resolve_exits
        solver_script = "solve_new_1.py"
    except ImportError:
        from solve_new_1 import parse_level, initial_state, resolve_exits
        solver_script = "solve_new_1.py"

    if not os.path.exists(solver_script):
        solver_script = "solve_new_1.py" if os.path.exists("solve_new_1.py") else "solve.py"

    with open(level_file, "r") as f:
        level = parse_level(f.read())

    print(f"\nEvaluating solutions for {level_file}...")
    status_c, moves_c = get_solver_solution(solver_script, level_file, "complete")
    status_f, moves_f = get_solver_solution(solver_script, level_file, "fast")

    if status_c != "SOLVED" and status_f != "SOLVED":
        print(f"\033[91mLevel {level_file} is UNSOLVABLE for both engines.\033[0m")
        time.sleep(2.0)
        return

    st_c = list(initial_state(level))
    st_f = list(initial_state(level))

    max_steps = max(len(moves_c), len(moves_f))
    act_c = "Start Configuration"
    act_f = "Start Configuration"

    for step in range(max_steps + 1):
        if 0 < step <= len(moves_c):
            bid, x, y = moves_c[step - 1]
            st_c[level.index[bid]] = y * level.w + x
            resolve_exits(level, st_c)
            act_c = f"Move '{bid}' -> ({x},{y})"
        elif step > len(moves_c):
            act_c = "DONE (Goal Reached)"

        if 0 < step <= len(moves_f):
            bid, x, y = moves_f[step - 1]
            st_f[level.index[bid]] = y * level.w + x
            resolve_exits(level, st_f)
            act_f = f"Move '{bid}' -> ({x},{y})"
        elif step > len(moves_f):
            act_f = "DONE (Goal Reached)"

        lines_c, width_c = build_board_lines(level, st_c, min(step, len(moves_c)), len(moves_c), act_c, "Complete", "\033[94m")
        lines_f, width_f = build_board_lines(level, st_f, min(step, len(moves_f)), len(moves_f), act_f, "Fast", "\033[92m")

        clear_screen()
        print(f"{COLORS['BOLD']}=== COLOR BLOCK CRUSH -- REALTIME DUAL COMPARISON ==={COLORS['RESET']}")
        print(f"File: \033[93m{level_file}\033[0m | Grid: {level.w}x{level.h} | Speed: {speed}s/move\n")

        # Join side by side with an 8-space gap
        for lc, lf in zip(lines_c, lines_f):
            print(f"{lc}{' ' * 8}{lf}")

        if step == 0:
            time.sleep(1.2)
        else:
            time.sleep(speed)

    print("\n\033[92m\033[1m✓ BOTH SOLVERS COMPLETED THE LEVEL!\033[0m")
    time.sleep(2.0)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "tests/test3.txt"
    spd = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15

    if target == "--all":
        test_dir = "tests"
        files = sorted([os.path.join(test_dir, f) for f in os.listdir(test_dir) if f.startswith("test") and f.endswith(".txt")])
        for tf in files:
            animate_dual(tf, spd)
    else:
        animate_dual(target, spd)