"""Image tier (Airtest-equivalent) for canvas games.

When neither a Game Test Bridge nor a UI tree is available, we locate UI by image templates.
This is the same technique Airtest uses (OpenCV template matching); on Android/iOS builds the
tests would call airtest.core.api.touch(Template(...)) directly. For the web build we keep the
stack in Python + OpenCV so it runs in the same Pytest/Playwright session.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

TEMPLATES = Path(__file__).parent / "templates"


@dataclass
class Match:
    name: str
    score: float
    x: float  # centre, CSS px (page coordinates)
    y: float
    scale: float


def _decode(png: bytes):
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)


def find(page, name: str, threshold: float = 0.80, scales=(0.8, 0.9, 1.0, 1.1, 1.2)) -> Match | None:
    """Find template `name` on the current page screenshot (multi-scale). Returns centre in CSS px."""
    dpr = page.evaluate("window.devicePixelRatio")
    shot = _decode(page.screenshot())
    tpl0 = cv2.imread(str(TEMPLATES / f"{name}.png"), cv2.IMREAD_COLOR)
    if tpl0 is None:
        raise FileNotFoundError(TEMPLATES / f"{name}.png")
    # templates were captured at DPR 2; normalise to the current DPR first
    base = dpr / 2.0
    best: Match | None = None
    for s in scales:
        f = base * s
        tpl = cv2.resize(tpl0, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        if tpl.shape[0] > shot.shape[0] or tpl.shape[1] > shot.shape[1]:
            continue
        res = cv2.matchTemplate(shot, tpl, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(res)
        if best is None or score > best.score:
            h, w = tpl.shape[:2]
            best = Match(name, float(score), (loc[0] + w / 2) / dpr, (loc[1] + h / 2) / dpr, s)
    return best if best and best.score >= threshold else None


def tap(page, name: str, threshold: float = 0.80) -> Match:
    m = find(page, name, threshold)
    assert m, f"template '{name}' not found on screen (threshold {threshold})"
    page.mouse.click(m.x, m.y)
    return m


def wait_for(page, name: str, timeout_s: float = 15, threshold: float = 0.80) -> Match:
    import time
    end = time.time() + timeout_s
    while time.time() < end:
        m = find(page, name, threshold)
        if m:
            return m
        time.sleep(0.5)
    raise AssertionError(f"template '{name}' did not appear within {timeout_s}s")


def non_blank(png: bytes, min_std: float = 12.0) -> float:
    """Cheap 'did the canvas actually render' oracle: pixel standard deviation of the frame."""
    img = _decode(png)
    return float(np.std(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)))
