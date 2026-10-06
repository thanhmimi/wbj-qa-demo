"""Pytest wiring: browser per test (fresh player), game driver fixtures, evidence on every test."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from wbj.driver import BRIDGE_JS, GameDriver, install_network_policy

ROOT = Path(__file__).parent
EVIDENCE = ROOT / "reports" / "evidence"

DEVICES = {
    # portrait phone-sized web view (the game is portrait-only)
    "mobile": dict(viewport={"width": 430, "height": 932}, device_scale_factor=2, has_touch=False),
    "small": dict(viewport={"width": 360, "height": 740}, device_scale_factor=2, has_touch=False),
    "desktop": dict(viewport={"width": 1280, "height": 800}, device_scale_factor=2, has_touch=False),
}


def pytest_addoption(parser):
    g = parser.getgroup("wbj")
    g.addoption("--portal", default="playhop", help="distribution portal to test (default: playhop)")
    g.addoption("--device", default="mobile", choices=list(DEVICES), help="viewport profile")
    g.addoption("--headed", action="store_true", help="show the browser (use for the live demo)")
    g.addoption("--slowmo", type=int, default=0, help="slow down every action (ms), handy for demos")
    g.addoption("--live-ads", action="store_true", help="do NOT block ad/analytics networks")
    g.addoption("--video", action="store_true", help="record a .webm per test into reports/video (demo backup)")


def pytest_configure(config):
    for m in ("tc(id): test case ID in Notion", "smoke", "p0", "p1", "p2",
              "tier_bridge: Game Test Bridge tier", "tier_scene: scene-graph (Poco-like) tier",
              "tier_image: image (Airtest-like) tier", "perf", "demo: subset for the live demo"):
        config.addinivalue_line("markers", m)


@pytest.fixture(scope="session")
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(pw, pytestconfig):
    # channel="chromium" = full Chromium (new headless) -> GPU (Metal/ANGLE) rendering.
    # The lightweight headless shell falls back to SwiftShader: ~40 fps and 7 CPU cores on this game,
    # which makes both timings and perf numbers meaningless.
    b = pw.chromium.launch(channel="chromium", headless=not pytestconfig.getoption("--headed"),
                           slow_mo=pytestconfig.getoption("--slowmo"))
    yield b
    b.close()


@pytest.fixture
def context(browser, pytestconfig, request):
    """Fresh browser context = fresh player (no saved progress, tutorial on)."""
    opts = dict(DEVICES[pytestconfig.getoption("--device")])
    if pytestconfig.getoption("--video"):
        opts.update(record_video_dir=str(ROOT / "reports" / "video"), record_video_size=opts["viewport"])
    ctx = browser.new_context(**opts)
    blocked: list[str] = []
    install_network_policy(ctx, not pytestconfig.getoption("--live-ads"), blocked)
    ctx.add_init_script(BRIDGE_JS)
    request.node.blocked_requests = blocked
    yield ctx
    videos = [pg.video for pg in ctx.pages if pg.video]
    ctx.close()
    if videos:  # name recordings after the test so the demo backup is easy to find
        name = re.sub(r"[^\w\-]+", "_", request.node.name)[:90]
        for i, v in enumerate(videos):
            try:
                Path(v.path()).rename(ROOT / "reports" / "video" / f"{name}{'_' + str(i) if i else ''}.webm")
            except Exception:
                pass


@pytest.fixture
def game(context, pytestconfig, request) -> GameDriver:
    """Game launched to GAME_SCENE. Tutorial still running (first-time player)."""
    page = context.new_page()
    d = GameDriver(page, portal=pytestconfig.getoption("--portal")).launch()
    request.node.game = d
    return d


@pytest.fixture
def ready(game) -> GameDriver:
    """Game past the tutorial with a playable hand dealt."""
    game.wait_until(lambda: game.qa("tutorialState") == "running", 15, what="tutorial start")
    game.qa("skipTutorial")
    game.wait_playable(30)
    return game


# ---------------------------------------------------------------- evidence + junit properties
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call":
        return
    tcs = [m.args[0] for m in item.iter_markers("tc")]
    if tcs:
        item.user_properties.append(("tc_id", ", ".join(sorted(tcs))))
    layers = [m.name for m in item.iter_markers() if m.name.startswith("tier_")]
    if layers:
        item.user_properties.append(("tier", layers[0].replace("tier_", "")))
    d: GameDriver | None = getattr(item, "game", None)
    if d is None:
        return
    folder = EVIDENCE / re.sub(r"[^\w\-]+", "_", item.nodeid)[-120:]
    folder.mkdir(parents=True, exist_ok=True)
    try:
        d.page.screenshot(path=str(folder / "final.png"))
        item.user_properties.append(("screenshot", str((folder / "final.png").relative_to(ROOT))))
    except Exception:
        pass
    ev = {"outcome": rep.outcome, "timing": d.timing.__dict__, "snapshot": d.snapshot(),
          "drag_retries": d.drag_retries,
          "console_errors": d.console_errors[:20],
          "blocked_requests": len(getattr(item, "blocked_requests", []) or []),
          "captured_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (folder / "evidence.json").write_text(json.dumps(ev, indent=2, default=str))
    item.user_properties.append(("fen", ev["snapshot"].get("fen")))
