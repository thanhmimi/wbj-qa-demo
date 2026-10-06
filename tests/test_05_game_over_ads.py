"""Game over, Second Chance (rewarded ad) and ad-failure resilience."""
import time

import pytest

from wbj import rules, vision

# every row/col/box keeps holes, holes are isolated -> only square_1 can ever fit
HOLES = {(r, (r * 2) % 9) for r in range(9)} | {(r, (r * 2 + 5) % 9) for r in range(9)}
NO_SPACE_BOARD = [[0 if (r, c) in HOLES else 1 for c in range(9)] for r in range(9)]
DEAD_HAND = [{"type": "square_1"}, {"type": "square_2"}, {"type": "line_5", "direction": "vertical"}]


def _trigger_game_over(game):
    game.arrange(NO_SPACE_BOARD, DEAD_HAND)
    hole = sorted(HOLES)[0]
    after, cleared = rules.place(NO_SPACE_BOARD, [[0, 0]], *hole)
    assert not any(cleared.values())
    assert not rules.any_move(after, [[[0, 0], [0, 1], [1, 0], [1, 1]], [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]]])
    return game.place(0, *hole, settle_s=0.3)


@pytest.mark.p0
@pytest.mark.demo
@pytest.mark.tier_scene
@pytest.mark.tc("WBJ-TC-040")
def test_no_fit_offers_second_chance_with_countdown(ready):
    _trigger_game_over(ready)
    ready.wait_until(lambda: "RESCUE_SCREEN" in ready.qa("openScreens"), 6, what="Second Chance screen")
    first = ready.wait_until(lambda: [t for t in ready.qa("screenTexts", "RESCUE_SCREEN") if t.isdigit()], 3,
                             what="countdown")
    time.sleep(2.2)
    later = [t for t in ready.qa("screenTexts", "RESCUE_SCREEN") if t.isdigit()]
    assert int(later[0]) < int(first[0]), "countdown must tick down"


@pytest.mark.p0
@pytest.mark.tier_scene
@pytest.mark.tc("WBJ-TC-041")
def test_ad_unavailable_never_blocks_the_player(ready):
    """Ads network blocked (fixture default): the flow must still reach game over, not hang on LOADING AD."""
    _trigger_game_over(ready)
    t0 = time.time()
    ready.wait_until(lambda: "GAME_OVER_SCREEN" in ready.qa("openScreens"), 30, what="game over screen")
    assert time.time() - t0 < 25, "fallback when ad fails must be bounded"
    assert ready.qa("matchStore")["status"] == "finished"


@pytest.mark.p1
@pytest.mark.tier_scene
@pytest.mark.tc("WBJ-TC-042")
def test_game_over_screen_shows_final_score(ready):
    r = _trigger_game_over(ready)
    final = r["before"]["score"] + 1
    ready.wait_until(lambda: "GAME_OVER_SCREEN" in ready.qa("openScreens"), 30, what="game over screen")
    # score counts up on the panel — assert after the animation settles, not on first paint
    ready.wait_until(lambda: str(final) in ready.qa("screenTexts", "GAME_OVER_SCREEN"), 6,
                     what=f"panel shows {final}")


@pytest.mark.p1
@pytest.mark.demo
@pytest.mark.tier_image
@pytest.mark.tc("WBJ-TC-043")
def test_play_again_by_image_starts_fresh_game(ready):
    """Image tier: no ids/tree used to find the button — OpenCV template, Airtest style."""
    _trigger_game_over(ready)
    vision.wait_for(ready.page, "title_your_score", timeout_s=30)
    time.sleep(2.5)
    m = vision.tap(ready.page, "btn_play")
    assert m.score > 0.8
    ready.wait_playable(20)
    st = ready.qa("state")
    assert st["score"] == 0 and st["filled"] == 0, "replay must start from an empty board and zero score"
