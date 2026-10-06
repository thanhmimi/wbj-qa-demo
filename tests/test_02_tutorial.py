"""FTUE — first-time players get the 4-step tutorial and finish it with real drag input."""
import pytest

from wbj import rules

TUTORIAL_STEP1_BOARD = "x/x/x/x/bbbb1bbbb/x/x/x/x"


@pytest.mark.p0
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-010")
def test_new_player_starts_in_tutorial(game):
    game.wait_until(lambda: game.qa("tutorialState") == "running", 15, what="tutorial start")
    assert game.qa("fen").startswith(TUTORIAL_STEP1_BOARD)
    pieces = [p for p in game.qa("pieces") if not p["used"]]
    assert [p["type"] for p in pieces] == ["square_1"]


@pytest.mark.p0
@pytest.mark.demo
@pytest.mark.tier_scene
@pytest.mark.tc("WBJ-TC-011")
def test_complete_tutorial_with_real_drags(game):
    game.wait_until(lambda: game.qa("tutorialState") == "running", 15, what="tutorial start")
    steps = 0
    while game.qa("tutorialState") == "running":
        st = game.qa("state")
        pc = next(p for p in st["pieces"] if not p["used"])
        move = rules.best_move(st["board"], pc["cells"])
        expected_board, cleared = rules.place(st["board"], pc["cells"], *move)
        assert sum(map(len, cleared.values())) >= 1, "every tutorial step is designed to clear a line"
        game.place(pc["slot"], *move)
        steps += 1
        assert steps <= 4, "tutorial longer than 4 steps"
        game.wait_until(lambda: game.qa("state")["fen"] != st["fen"], 6, what="next tutorial step")
    assert steps == 4
    assert game.qa("tutorialState") == "stopped"
    game.wait_playable(30)
    assert game.qa("score") == 0, "tutorial must not award score"
    assert game.qa("filled") == 0, "real game starts on an empty board"
    assert len([p for p in game.qa("pieces") if not p["used"]]) == 3
