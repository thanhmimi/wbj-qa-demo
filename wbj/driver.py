"""GameDriver: one place that knows how to launch Wood Block Journey and talk to it.

Tests never touch Playwright selectors or JS directly; they call this driver.
Ladder: bridge (state) -> scene geometry (real pointer input) -> image (OpenCV, see vision.py).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Frame, Page

BRIDGE_JS = (Path(__file__).parent / "bridge.js").read_text()

PORTALS = {
    # Official Sun.Studio distribution on Yandex Games / Playhop. Same HTML5 build also targets FB Instant.
    "playhop": {
        "url": "https://playhop.com/app/wood-block-journey-181186",
        "play_button": "Play now",
        "game_frame": "games.s3.yandex.net",
        "ad_close": "[class*=desktopClose]",
    },
}


# Functional suites run with ad and tracking networks blocked:
#  - portal ads are third-party, random and the #1 source of flaky UI runs;
#  - test traffic must not pollute production analytics or ad revenue data.
# Ads get their own suite (ads sandbox / test placements), not random live fills.
BLOCKED_HOSTS = (
    "imasdk.googleapis.com", "googlesyndication.com", "doubleclick.net", "googleadservices.com",
    "adfox.ru", "an.yandex.ru", "yandex.ru/ads", "ads.adfox", "mc.yandex", "criteo.com", "pubmatic.com",
    "rubiconproject.com", "openx.net", "3lift.com", "indexww.com", "adnxs.com", "amazon-adsystem.com",
    "google-analytics.com", "googletagmanager.com", "rollbar.com", "sentry.io", "facebook.net",
)


def install_network_policy(context, block_ads: bool = True, blocked_log: list | None = None):
    if not block_ads:
        return

    def handler(route):
        url = route.request.url
        if any(h in url for h in BLOCKED_HOSTS):
            if blocked_log is not None:
                blocked_log.append(url[:120])
            return route.abort()
        return route.continue_()

    context.route("**/*", handler)


class GameNotReady(AssertionError):
    pass


@dataclass
class LoadTiming:
    page_dom_s: float = 0.0
    frame_attached_s: float = 0.0
    game_ready_s: float = 0.0
    ads_closed: int = 0
    launch_retries: int = 0
    via_dashboard: bool = False


@dataclass
class GameDriver:
    page: Page
    portal: str = "playhop"
    frame: Frame | None = None
    timing: LoadTiming = field(default_factory=LoadTiming)
    console_errors: list[str] = field(default_factory=list)
    drag_retries: int = 0  # reported in evidence; a rising trend = input/perf problem worth a look

    # ------------------------------------------------------------------ launch
    def launch(self, timeout_s: int = 90) -> "GameDriver":
        cfg = PORTALS[self.portal]
        self.page.on("console", lambda m: m.type == "error" and self.console_errors.append(m.text[:300]))
        t0 = time.time()
        for attempt in range(3):  # infra retry: the portal itself sometimes answers 5xx
            try:
                self.page.goto(cfg["url"], wait_until="domcontentloaded")
                break
            except Exception:
                if attempt == 2:
                    raise
                self.timing.launch_retries += 1
                time.sleep(3)
        self.timing.page_dom_s = round(time.time() - t0, 2)
        deadline = time.time() + timeout_s
        play = self.page.get_by_text(cfg["play_button"]).first
        clicked = False
        while time.time() < deadline:
            # first-time players get a "Play now" landing; returning players are auto-launched
            if not clicked and self.frame is None:
                try:
                    if play.is_visible():
                        play.click(timeout=5_000)
                        clicked = True
                except Exception:
                    pass
            self.close_portal_ads()
            if self.frame is None:
                for f in self.page.frames:
                    if cfg["game_frame"] in f.url:
                        self.frame = f
                        self.timing.frame_attached_s = round(time.time() - t0, 2)
            if self.frame is not None and self._safe_eval("window.__WBJ_QA__ && window.__WBJ_QA__.ready()"):
                self.timing.game_ready_s = round(time.time() - t0, 2)
                return self
            # returning players land on the home dashboard: press "Play" by node name (tier 2)
            if self.frame is not None and self._safe_eval("window.__WBJ_QA__ && window.__WBJ_QA__.currentScene()") == "DASHBOARD_SCENE":
                if self.portal_overlay() is None:
                    try:
                        self.tap_node("PlaySingle")
                        self.timing.via_dashboard = True
                        time.sleep(1.5)
                    except AssertionError:
                        pass
            time.sleep(0.5)
        raise GameNotReady(f"GAME_SCENE not ready after {timeout_s}s (frame={'yes' if self.frame else 'no'})")

    def close_portal_ads(self) -> bool:
        """Portal pre-roll / interstitial ads are outside the game's control; close them when they appear."""
        try:
            loc = self.page.locator(PORTALS[self.portal]["ad_close"])
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=2_000)
                self.timing.ads_closed += 1
                return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------ bridge
    def _safe_eval(self, expr: str):
        try:
            return self.frame.evaluate(expr)
        except Exception:
            return None

    def qa(self, method: str, *args):
        js_args = ", ".join(json.dumps(a) for a in args)
        return self.frame.evaluate(f"window.__WBJ_QA__.{method}({js_args})")

    def wait_until(self, predicate, timeout_s: float = 10, poll: float = 0.2, what: str = "condition"):
        end = time.time() + timeout_s
        last = None
        while time.time() < end:
            self.close_portal_ads()
            last = predicate()
            if last:
                return last
            time.sleep(poll)
        raise AssertionError(f"Timed out after {timeout_s}s waiting for {what} (last={last!r})")

    def portal_overlay(self) -> str | None:
        """Return a description of whatever portal element covers the game, or None if the game gets the input."""
        box = self.frame.frame_element().bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        return self.page.evaluate(
            """([x, y, needle]) => { const e = document.elementFromPoint(x, y);
                 if (!e) return 'nothing';
                 if (e.tagName === 'IFRAME' && e.src.includes(needle)) return null;
                 return e.tagName + '.' + String(e.className).slice(0, 60); }""",
            [cx, cy, PORTALS[self.portal]["game_frame"]])

    def wait_idle(self, timeout_s: float = 15):
        """Portal overlay gone, input enabled, no tweens running, no blocking screen."""
        return self.wait_until(
            lambda: self.portal_overlay() is None and self.qa("inputEnabled") and not self.qa("openScreens"),
            timeout_s, what="game idle")

    def wait_playable(self, timeout_s: float = 20):
        self.wait_idle(timeout_s)
        return self.wait_until(lambda: any(not p["used"] for p in self.qa("pieces")), timeout_s, what="pieces dealt")

    # ------------------------------------------------------------------ input
    def frame_offset(self):
        box = self.frame.frame_element().bounding_box()
        return box["x"], box["y"]

    def to_page(self, pt):
        ox, oy = self.frame_offset()
        return pt["x"] + ox, pt["y"] + oy

    def drag_piece(self, slot: int, row: int, col: int, *, release: bool = True, max_corrections: int = 4) -> dict:
        """Drag piece `slot` so that its top-left cell lands on board (row, col).

        Uses real pointer events on the canvas. The game draws a drop preview while dragging;
        the driver reads it through the bridge and corrects the pointer (closed loop), so the test
        does not depend on hard-coded pixel offsets or device size.
        """
        # the hand slides in with a tween after a deal/arrange: wait until the piece stops moving
        last = None
        for _ in range(20):
            cur = self.qa("pieceCss", slot)
            cur = (round(cur["x"]), round(cur["y"]))
            if cur == last:
                break
            last = cur
            time.sleep(0.1)
        start = self.to_page(self.qa("pieceCss", slot))
        tx, ty = self.to_page(self.qa("cellCss", row, col))
        k = self.qa("cssPerWorld")
        target_w = self.qa("boardCellWorld", row, col)
        m = self.page.mouse
        for attempt in range(2):
            rest = self.qa("dragAnchorWorld", slot)
            m.move(*start)
            m.down()
            m.move(start[0], start[1] - 10, steps=3)
            m.move(tx, ty, steps=12)
            time.sleep(0.15)
            picked = self.qa("dragAnchorWorld", slot)
            if picked and rest and abs(picked[1] - rest[1]) > 20:
                break
            # the press did not pick the piece up (busy main thread / mid-tween): release and retry once
            m.up()
            self.drag_retries += 1
            time.sleep(0.4)
        err = None
        for _ in range(max_corrections + 1):
            anchor_w = self.qa("dragAnchorWorld", slot)
            if anchor_w is None:
                break
            dx, dy = (target_w[0] - anchor_w[0]) * k, (target_w[1] - anchor_w[1]) * k
            err = (round(dx, 1), round(dy, 1))
            if abs(dx) < 3 and abs(dy) < 3:
                break
            tx, ty = tx + dx, ty + dy
            m.move(tx, ty, steps=4)
            time.sleep(0.12)
        preview = self.qa("highlight")
        if release:
            m.up()
        return {"pointer": (round(tx), round(ty)), "residual_css": err, "highlight": preview}

    def place(self, slot: int, row: int, col: int, settle_s: float = 1.6) -> dict:
        """Drag + release, then let the clear/score animation finish. Returns before/after state.

        Score is credited at the end of the '+N' animation (~1.1 s), so settle_s must cover it.
        """
        before = self.qa("state")
        info = self.drag_piece(slot, row, col)
        time.sleep(settle_s)
        after = self.qa("state")
        return {"before": before, "after": after, "drag": info}

    def drag_to_css(self, slot: int, x: float, y: float, settle_s: float = 1.0) -> dict:
        """Drag a piece to an arbitrary point (inside the game frame, CSS px) — used for invalid drops."""
        before = self.qa("state")
        start = self.to_page(self.qa("pieceCss", slot))
        tx, ty = self.to_page({"x": x, "y": y})
        m = self.page.mouse
        m.move(*start); m.down(); m.move(start[0], start[1] - 10, steps=3); m.move(tx, ty, steps=12)
        time.sleep(0.15); m.up(); time.sleep(settle_s)
        return {"before": before, "after": self.qa("state")}

    def arrange(self, board, pieces: list[dict]) -> dict:
        """Deterministic setup through the bridge: board (matrix) + the 3 pieces in hand.

        Replaces RNG and long play-throughs. In-house this is the Game Test Bridge
        `setState(fen)` call owned by the dev team.
        """
        from wbj import rules
        self.qa("setBoard", rules.to_fen(board))
        self.qa("setPieces", pieces)
        time.sleep(0.4)
        st = self.qa("state")
        assert st["board"] == board, "bridge could not arrange the board"
        return st

    def tap_node(self, name: str) -> dict:
        """Tier 2: tap a game object by its scene-graph name (Poco-style), not by pixels."""
        pt = self.qa("nodeCss", name)
        assert pt, f"node '{name}' not found/visible in active scenes"
        self.page.mouse.click(*self.to_page(pt))
        return pt

    def tap_world(self, wx: float, wy: float):
        pt = self.frame.evaluate(f"window.__WBJ_QA__.worldToCss({wx}, {wy})")
        self.page.mouse.click(*self.to_page(pt))

    # ------------------------------------------------------------------ evidence
    def snapshot(self) -> dict:
        snap = {}
        for k in ("fen", "score", "bestScore", "targetScore", "levelIndex", "tutorialState", "openScreens", "isGameOver", "fps"):
            try:
                snap[k] = self.qa(k)
            except Exception as e:  # evidence must never fail the test
                snap[k] = f"<err {e.__class__.__name__}>"
        return snap


def piece_center_offset(cells):
    """Geometric centre (row, col) of a piece in cell units; the pointer drags the piece by its centre."""
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    return ((min(rows) + max(rows)) / 2, (min(cols) + max(cols)) / 2)
