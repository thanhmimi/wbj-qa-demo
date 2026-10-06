"""Reference model of the Wood Block Journey board rules (test oracle).

Written from the game design (9x9 board; a placed piece fills cells; any full row, full column
or full 3x3 box is cleared). Tests compare the real game against this model, so a rule change
in the game shows up as a model/game mismatch instead of a silently "green" UI script.
"""
from __future__ import annotations

from itertools import product

N = 9
Board = list[list[int]]
Cells = list[list[int]]  # [[dy, dx], ...] relative to the piece matrix


def empty() -> Board:
    return [[0] * N for _ in range(N)]


def anchor(cells: Cells) -> tuple[int, int]:
    return tuple(min(cells))  # row-major first occupied cell


def footprint(cells: Cells, row: int, col: int) -> list[tuple[int, int]]:
    ay, ax = anchor(cells)
    return [(row + dy - ay, col + dx - ax) for dy, dx in cells]


def fits(board: Board, cells: Cells, row: int, col: int) -> bool:
    return all(0 <= r < N and 0 <= c < N and board[r][c] == 0 for r, c in footprint(cells, row, col))


def full_lines(board: Board) -> dict:
    rows = [r for r in range(N) if all(board[r])]
    cols = [c for c in range(N) if all(board[r][c] for r in range(N))]
    boxes = [(br, bc) for br, bc in product(range(3), range(3))
             if all(board[br * 3 + i][bc * 3 + j] for i, j in product(range(3), range(3)))]
    return {"rows": rows, "cols": cols, "boxes": boxes}


def place(board: Board, cells: Cells, row: int, col: int) -> tuple[Board, dict]:
    """Return (board_after, cleared) — the expected result of a legal placement."""
    assert fits(board, cells, row, col), "illegal placement"
    b = [r[:] for r in board]
    for r, c in footprint(cells, row, col):
        b[r][c] = 1
    cleared = full_lines(b)
    for r in cleared["rows"]:
        b[r] = [0] * N
    for c in cleared["cols"]:
        for r in range(N):
            b[r][c] = 0
    for br, bc in cleared["boxes"]:
        for i, j in product(range(3), range(3)):
            b[br * 3 + i][bc * 3 + j] = 0
    # clear on the board *before* removals: rows/cols/boxes are evaluated simultaneously
    return b, cleared


def legal_moves(board: Board, cells: Cells):
    return [(r, c) for r, c in product(range(N), range(N)) if fits(board, cells, r, c)]


def best_move(board: Board, cells: Cells):
    """Greedy bot: prefer moves that clear the most lines, then lowest-row moves."""
    best, best_key = None, None
    for r, c in legal_moves(board, cells):
        _, cl = place(board, cells, r, c)
        key = (len(cl["rows"]) + len(cl["cols"]) + len(cl["boxes"]), -r, -c)
        if best_key is None or key > best_key:
            best, best_key = (r, c), key
    return best


def any_move(board: Board, pieces: list[Cells]) -> bool:
    return any(legal_moves(board, p) for p in pieces)


def board_from_rows(rows: list[str]) -> Board:
    """Helper for readable fixtures: '#' filled, '.' empty, 9 chars per row."""
    assert len(rows) == N and all(len(r) == N for r in rows)
    return [[1 if ch == "#" else 0 for ch in r] for r in rows]


def to_fen(board: Board) -> str:
    """Board -> the game's FEN board part ('b' = filled, digits = empty run, 'x' = empty row)."""
    out = []
    for row in board:
        if not any(row):
            out.append("x")
            continue
        s, run = "", 0
        for v in row:
            if v:
                if run:
                    s += str(run)
                    run = 0
                s += "b"
            else:
                run += 1
        if run:
            s += str(run)
        out.append(s)
    return "/".join(out)


def from_fen(fen: str) -> Board:
    rows = fen.split(" ")[0].split("/")
    board = []
    for r in rows:
        if r == "x":
            board.append([0] * N)
            continue
        row = []
        for ch in r:
            if ch.isdigit():
                row += [0] * int(ch)
            else:
                row.append(1)
        board.append(row)
    return board
