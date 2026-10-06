"""Scoring and target-score progression.

Observed rule (to be confirmed with Game Design — see analysis Q-03):
  placement = +1 per cell;  clear bonus = 18 x groups_cleared + 10 x streak
  (streak = consecutive moves that cleared at least one group, starting at 1).
"""
import pytest

from wbj import rules


def expected_points(cells: int, groups: int, streak: int) -> int:
    return cells + (18 * groups + 10 * streak if groups else 0)


def _row_almost_full(row=4, gap=0):
    b = rules.empty()
    for c in range(9):
        if c != gap:
            b[row][c] = 1
    return b


@pytest.mark.p0
@pytest.mark.demo
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-030")
@pytest.mark.parametrize("piece,cells", [({"type": "square_1"}, 1), ({"type": "square_2"}, 4),
                                         ({"type": "square_3"}, 9), ({"type": "line_5", "direction": "vertical"}, 5)])
def test_placement_scores_one_point_per_cell(ready, piece, cells):
    fillers = [f for f in ({"type": "line_2", "direction": "vertical"}, {"type": "line_3", "direction": "vertical"})]
    st = ready.arrange(rules.empty(), [piece, *fillers])
    # (1,1) straddles box borders, so even the 3x3 piece completes no box (at (0,0) it would clear box 0)
    _, cleared = rules.place(st["board"], st["pieces"][0]["cells"], 1, 1)
    assert not any(cleared.values())
    r = ready.place(0, 1, 1)
    assert r["after"]["score"] - r["before"]["score"] == cells


@pytest.mark.p1
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-031")
def test_clear_bonus_and_streak(ready):
    # move 1 clears row 4 (streak 1); move 2 clears row 5 (streak 2); move 3 clears nothing (streak resets)
    b = _row_almost_full(4, 0)
    for c in range(2, 9):
        b[5][c] = 1
    ready.arrange(b, [{"type": "square_1"}, {"type": "line_2", "direction": "horizontal"}, {"type": "square_2"}])
    s1 = ready.place(0, 4, 0)
    assert s1["after"]["score"] - s1["before"]["score"] == expected_points(1, 1, 1)
    s2 = ready.place(1, 5, 0)
    assert s2["after"]["score"] - s2["before"]["score"] == expected_points(2, 1, 2)
    s3 = ready.place(2, 0, 4)
    assert s3["after"]["score"] - s3["before"]["score"] == expected_points(4, 0, 0)


@pytest.mark.p1
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-032")
def test_double_clear_bonus(ready):
    b = rules.empty()
    for i in range(1, 9):
        b[0][i] = 1
        b[i][0] = 1
    ready.arrange(b, [{"type": "square_1"}, {"type": "line_2", "direction": "vertical"}, {"type": "square_2"}])
    r = ready.place(0, 0, 0)
    assert r["after"]["board"] == rules.empty()
    assert r["after"]["score"] - r["before"]["score"] == expected_points(1, 2, 1)


@pytest.mark.p1
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-033")
def test_first_target_is_100_and_reaching_it_opens_score_reached(ready):
    assert ready.qa("targetScore") == 100
    # four row+column double clears (~47 each) cross 100 quickly
    for _ in range(3):
        b = rules.empty()
        for i in range(1, 9):
            b[0][i] = 1
            b[i][0] = 1
        ready.arrange(b, [{"type": "square_1"}, {"type": "line_2", "direction": "vertical"}, {"type": "square_2"}])
        ready.place(0, 0, 0)
        if ready.qa("score") >= 100:
            break
    assert ready.qa("score") >= 100
    ready.wait_until(lambda: "SCORE_REACHED_SCREEN" in ready.qa("openScreens")
                     or "NEXT_TARGET_SCORE_SCREEN" in ready.qa("openScreens"), 8, what="target reached screen")
    ready.wait_until(lambda: ready.qa("targetScore") == 250, 15, what="next target 250")
