"""Performance guardrails (web build). Numbers are budgets to agree with the team, not absolutes.

Run on GPU-backed Chromium; SwiftShader (software GL) halves FPS and makes these meaningless.
"""
import time

import pytest

from wbj import rules

MIN_AVG_FPS = 50
MAX_HEAP_GROWTH_MB = 25
MAX_GAME_DOWNLOAD_MB = 15


@pytest.mark.perf
@pytest.mark.p1
@pytest.mark.demo
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-070")
def test_fps_and_memory_during_play(ready):
    heap = lambda: ready.frame.evaluate("performance.memory ? performance.memory.usedJSHeapSize : 0")
    h0 = heap()
    samples = []
    for _ in range(12):
        st = ready.qa("state")
        if st["screens"]:
            break
        pc = next((p for p in st["pieces"] if not p["used"]), None)
        if pc is None:
            time.sleep(0.5)
            continue
        mv = rules.best_move(st["board"], pc["cells"])
        if mv is None:
            break
        ready.place(pc["slot"], *mv, settle_s=1.0)
        samples.append(ready.qa("fps"))
    avg = sum(samples) / len(samples)
    growth_mb = (heap() - h0) / 1e6
    print(f"fps samples={samples} avg={avg:.1f} heap_growth={growth_mb:.1f}MB")
    assert avg >= MIN_AVG_FPS, f"average FPS {avg:.1f} < {MIN_AVG_FPS}"
    assert min(samples) >= 30, f"FPS dipped to {min(samples)}"
    assert growth_mb < MAX_HEAP_GROWTH_MB


@pytest.mark.perf
@pytest.mark.p2
@pytest.mark.tier_bridge
@pytest.mark.tc("WBJ-TC-071")
def test_game_payload_size(game):
    sizes = game.frame.evaluate(
        "performance.getEntriesByType('resource').map(e => e.transferSize || e.encodedBodySize || 0)")
    total_mb = sum(sizes) / 1e6
    print(f"game frame resources={len(sizes)} transfer={total_mb:.2f}MB")
    assert total_mb < MAX_GAME_DOWNLOAD_MB
