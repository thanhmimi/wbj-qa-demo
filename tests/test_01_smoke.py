"""P0 smoke — the build loads, renders and accepts input. Runs on every build (CI gate G2)."""
import pytest

from wbj import vision

LOAD_BUDGET_S = 15.0  # Play-click -> GAME_SCENE ready, on a normal connection


@pytest.mark.smoke
@pytest.mark.p0
@pytest.mark.demo
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-001")
def test_game_loads_to_game_scene_within_budget(game):
    assert game.qa("ready"), "GAME_SCENE not active"
    assert "GAME_SCENE" in game.qa("activeScenes")
    assert game.timing.game_ready_s <= LOAD_BUDGET_S, f"load took {game.timing.game_ready_s}s"
    assert game.qa("renderer") == "WEBGL"
    assert game.qa("phaserVersion"), "engine version not detected"


@pytest.mark.smoke
@pytest.mark.p0
@pytest.mark.tier_image
@pytest.mark.tc("WBJ-TC-002")
def test_canvas_actually_renders(game):
    # a black/blank canvas passes most DOM checks; look at the pixels instead
    game.wait_idle(20)
    png = game.frame.frame_element().screenshot()
    assert vision.non_blank(png) > 12, "game frame looks blank"


@pytest.mark.smoke
@pytest.mark.p0
@pytest.mark.demo
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-003")
def test_no_uncaught_js_errors_during_launch_and_first_moves(ready):
    from wbj import rules
    for _ in range(3):
        st = ready.qa("state")
        pc = next(p for p in st["pieces"] if not p["used"])
        ready.place(pc["slot"], *rules.best_move(st["board"], pc["cells"]))
    assert ready.qa("errors") == [], ready.qa("errors")


@pytest.mark.smoke
@pytest.mark.p0
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-062")
def test_test_traffic_never_reaches_analytics_or_ads(game, request):
    """Guardrail: functional runs must not inflate production DAU/events or ad impressions."""
    from wbj.driver import BLOCKED_HOSTS
    leaked = []
    game.page.context.on("requestfinished", lambda r: any(h in r.url for h in BLOCKED_HOSTS) and leaked.append(r.url))
    game.wait_idle(20)
    game.qa("skipTutorial")
    game.wait_playable(20)
    blocked = request.node.blocked_requests
    assert blocked, "network policy not active: nothing was blocked"
    assert not leaked, f"analytics/ad requests escaped: {leaked[:3]}"
