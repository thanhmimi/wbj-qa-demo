"""Session save/resume — a returning player continues the same board, score and hand."""
import time

import pytest

from wbj import rules
from wbj.driver import GameDriver


@pytest.mark.p0
@pytest.mark.demo
@pytest.mark.tier_scene
@pytest.mark.tc("WBJ-TC-050")
@pytest.mark.tc("WBJ-TC-013")
def test_reload_resumes_board_score_and_hand(ready, request):
    for _ in range(3):
        st = ready.qa("state")
        pc = next(p for p in st["pieces"] if not p["used"])
        ready.place(pc["slot"], *rules.best_move(st["board"], pc["cells"]))
    saved = ready.qa("state")
    assert ready.qa("matchStore")["fen"] == saved["fen"], "match store must hold the latest board + hand"
    time.sleep(1.5)  # let the save flush

    # same browser profile = same player; the portal auto-launches the game for returning players
    page2 = ready.page.context.new_page()
    ready.page.close()
    again = GameDriver(page2).launch(timeout_s=120)  # lands on DASHBOARD -> taps node 'PlaySingle'
    request.node.game = again
    again.wait_playable(30)
    resumed = again.qa("state")

    assert again.timing.via_dashboard, "returning player should land on the home dashboard"
    assert resumed["tutorial"] != "running", "returning player must not see the tutorial again"
    assert resumed["board"] == saved["board"], "board not restored"
    assert resumed["score"] == saved["score"], "score not restored"
    held = sorted((p["type"], p["direction"]) for p in saved["pieces"] if not p["used"])
    assert sorted((p["type"], p["direction"]) for p in resumed["pieces"] if not p["used"]) == held, "hand not restored"
