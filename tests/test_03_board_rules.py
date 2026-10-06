"""Core rules, checked against an independent model (wbj/rules.py).

Setup goes through the bridge (deterministic board + hand); the action under test is always a
real pointer drag on the canvas; the oracle is the model, not the screenshot.
"""
import pytest

from wbj import rules

R = rules.board_from_rows

PIECES = {
    "square_1": {"type": "square_1"},
    "square_2": {"type": "square_2"},
    "square_3": {"type": "square_3"},
    "line_5_v": {"type": "line_5", "direction": "vertical"},
    "line_5_h": {"type": "line_5", "direction": "horizontal"},
    "l_top": {"type": "l", "direction": "top"},
    "t_top": {"type": "t_piece", "direction": "top"},
    "plus": {"type": "plus_piece"},
    "line_2_v": {"type": "line_2", "direction": "vertical"},
    "line_3_v": {"type": "line_3", "direction": "vertical"},
}


def hand(*names):
    """Hand of 3 *different* pieces (game invariant: the dealer never deals duplicates)."""
    names = list(names)
    for filler in ("line_2_v", "line_3_v", "square_1", "square_2"):
        if len(names) == 3:
            break
        if filler not in names:
            names.append(filler)
    assert len(set(names)) == 3, names
    return [PIECES[n] for n in names]


def _assert_matches_model(game, before, slot, row, col):
    pc = before["pieces"][slot]
    expected, cleared = rules.place(before["board"], pc["cells"], row, col)
    result = game.place(slot, row, col)
    assert result["after"]["board"] == expected, (
        f"board differs from model after placing {pc['type']} at {(row, col)}; cleared={cleared}")
    assert result["after"]["pieces"][slot]["used"], "placed piece must leave the hand"
    return result, cleared


@pytest.mark.p0
@pytest.mark.demo
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-020")
@pytest.mark.parametrize("piece", ["square_3", "l_top", "t_top", "plus", "line_5_v"])
def test_placement_fills_exact_footprint(ready, piece):
    before = ready.arrange(rules.empty(), hand(piece))
    _assert_matches_model(ready, before, 0, 2, 2)


@pytest.mark.p0
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-021")
def test_drop_on_occupied_cells_is_rejected(ready):
    board = R([".........", ".........", "....#....", ".........", ".........",
               ".........", ".........", ".........", "........."])
    before = ready.arrange(board, hand("square_3"))
    # 3x3 at (1,3) would cover the filled cell (2,4)
    assert not rules.fits(board, before["pieces"][0]["cells"], 1, 3)
    res = ready.drag_to_css(0, **ready.qa("cellCss", 2, 4))
    assert res["after"]["board"] == board, "illegal drop must not change the board"
    assert not res["after"]["pieces"][0]["used"], "piece must return to the hand"
    assert res["after"]["score"] == res["before"]["score"]


@pytest.mark.p1
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-022")
def test_drop_outside_the_board_is_rejected(ready):
    before = ready.arrange(rules.empty(), hand("line_5_h"))
    edge = ready.qa("cellCss", 0, 8)
    res = ready.drag_to_css(0, edge["x"] + 60, edge["y"] - 120)  # above / right of the board
    assert res["after"]["board"] == before["board"]
    assert not res["after"]["pieces"][0]["used"]


@pytest.mark.p0
@pytest.mark.demo
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-023")
@pytest.mark.parametrize("kind", ["row", "column", "box", "row+column"])
def test_line_and_box_clears(ready, kind):
    b = rules.empty()
    if kind in ("row", "row+column"):
        for c in range(1, 9):
            b[4][c] = 1
    if kind in ("column", "row+column"):
        for r in range(9):
            if r != 4:
                b[r][0] = 1
    if kind == "column":
        b[4][0] = 0
    if kind == "box":
        for r in range(3, 6):
            for c in range(3, 6):
                b[r][c] = 1
        b[4][4] = 0
    target = (4, 0) if kind != "box" else (4, 4)
    before = ready.arrange(b, hand("square_1"))
    _, cleared = _assert_matches_model(ready, before, 0, *target)
    expected_groups = {"row": 1, "column": 1, "box": 1, "row+column": 2}[kind]
    assert sum(map(len, cleared.values())) == expected_groups


@pytest.mark.p1
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-024")
def test_new_hand_is_dealt_only_after_all_three_pieces_are_used(ready):
    before = ready.arrange(rules.empty(), hand("square_1", "line_2_v", "square_2"))
    ready.place(0, 0, 0)
    mid = ready.qa("state")
    assert [p["used"] for p in mid["pieces"]] == [True, False, False]
    ready.place(1, 0, 8)
    ready.place(2, 7, 0)
    ready.wait_until(lambda: all(not p["used"] for p in ready.qa("pieces")), 6, what="new hand")
    dealt = ready.qa("pieces")
    assert len(dealt) == 3
    kinds = [(p["type"], p["direction"]) for p in dealt]
    assert len(set(kinds)) == 3, f"dealer gave duplicate pieces: {kinds}"
