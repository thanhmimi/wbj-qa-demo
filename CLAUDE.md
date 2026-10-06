# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A QA automation demo for **Wood Block Journey** (Sun.Studio; HTML5 / Phaser 3.55), run black-box against the **live production build** on the Playhop / Yandex Games portal. There is no game source here and no spec: the suite drives a real browser against `https://playhop.com/app/wood-block-journey-181186`, so every test needs network access and a run can fail because the portal or the minified build changed.

`DEMO.md` (presentation script) is written in Vietnamese; code, comments and the other docs are in English.

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium

.venv/bin/pytest                                   # full suite, headless, ~12 min
.venv/bin/pytest -m "smoke or p0"                  # build gate
.venv/bin/pytest -m demo --headed --slowmo 150     # live-demo subset, visible browser
.venv/bin/pytest --device small                    # 360x740 viewport (mobile | small | desktop)
.venv/bin/pytest --video                           # one .webm per test in reports/video
.venv/bin/pytest --live-ads                        # do NOT block ad/analytics hosts

# single test / single parametrized case
.venv/bin/pytest -o addopts="" tests/test_03_board_rules.py::test_drop_on_occupied_cells_is_rejected
.venv/bin/pytest -o addopts="" "tests/test_03_board_rules.py::test_line_and_box_clears[row+column]"

.venv/bin/python tools/build_report.py             # reports/junit.xml + evidence -> reports/index.html
.venv/bin/python tools/notion_sync.py              # dry-run; pushes only if NOTION_TOKEN, NOTION_RUNS_DB, NOTION_TC_DB are set
```

- `pytest.ini` `addopts` always writes `reports/junit.xml`. A partial run **overwrites** the full-suite results that `build_report.py` and `notion_sync.py` read; pass `-o addopts=""` for ad-hoc runs.
- `--headed`, `--slowmo`, `--device`, `--video`, `--portal`, `--live-ads` are custom options defined in `conftest.py` (pytest-playwright is not installed, so its flags don't exist).
- There is no linter, formatter or type-checker configured.
- The browser is launched with `channel="chromium"` (full Chromium, GPU-backed). The default headless shell falls back to software GL, which halves FPS and breaks the load-time and perf budgets.

## Architecture

The guiding rule (from the README): **arrange through the bridge, act through real input, assert against the model.**

Three automation tiers, used in order of preference and recorded on each test with a `tier_*` marker:

1. **Bridge** — `wbj/bridge.js` is injected as a Playwright init script into every frame. It traps the `window.Phaser` setter to capture the `Phaser.Game` instance at boot, then exposes `window.__WBJ_QA__`: state reads (`state`, `fen`, `score`, `pieces`, `openScreens`, `matchStore`, …), geometry (`cellCss`, `pieceCss`, `dragAnchorWorld`, …) and state injection (`setBoard`, `setPieces`, `skipTutorial`). It reaches into minified production internals (`GAME_SCENE`, `main.board.dataBoard`, `footer.pieces`, …), so it is the first thing to break when the game ships a new build.
2. **Scene tree** — the Phaser display list read by node name (`nodeCss`, `screenTexts`, `uiTree`), plus real mouse input.
3. **Image** — `wbj/vision.py`, OpenCV multi-scale template matching against `wbj/templates/*.png`. Templates were captured at DPR 2; `find()` rescales for the current DPR.

`wbj/driver.py` `GameDriver` is the only layer that talks to Playwright or the bridge; tests call `game.qa("<bridgeMethod>", *args)` and the driver helpers, never selectors or raw JS. Key behaviours:

- `launch()` handles the portal: clicks "Play now" for a new player, finds the game iframe by URL (`games.s3.yandex.net`), closes portal ads, and for a returning player taps the `PlaySingle` node on `DASHBOARD_SCENE`.
- `drag_piece()` is closed-loop: it drags with real pointer events, reads the dragged piece's anchor cell back through the bridge and corrects the pointer until it is within 3 CSS px. No pixel offsets are hard-coded, which is what makes `--device` work.
- `place()` = drag + release + `settle_s` sleep, returning `{before, after, drag}` state. Score is credited at the end of the "+N" animation (~1.1 s), so shortening `settle_s` gives stale scores.
- `arrange(board, pieces)` injects a board (via FEN) and a hand, replacing RNG.
- `install_network_policy()` aborts requests to `BLOCKED_HOSTS` (ads, analytics, Sentry/Rollbar) so runs are deterministic and test traffic stays out of production KPIs. `test_test_traffic_never_reaches_analytics_or_ads` guards this.

`wbj/rules.py` is an independent model of the board rules (fit, simultaneous row/column/3×3-box clears, FEN encode/decode, a greedy `best_move` bot). It is the test oracle: tests compare the game's board after a move with `rules.place(...)`, not with screenshots. Piece `cells` are `[dy, dx]` lists and placement coordinates refer to the piece's **row-major first occupied cell** (`rules.anchor`), matching `dragAnchorWorld` in the bridge.

### Fixtures (`conftest.py`)

- `context` — a new browser context per test = a fresh player (no save, tutorial on), with the network policy and bridge installed.
- `game` — launched to `GAME_SCENE`, tutorial still running.
- `ready` — tutorial skipped through the bridge, hand dealt. Most tests use this.
- `pytest_runtest_makereport` writes `reports/evidence/<nodeid>/{final.png,evidence.json}` for every test and attaches `tc_id`, `tier`, `screenshot` and `fen` as JUnit properties. A test that swaps drivers (see `test_06_persistence.py`) must set `request.node.game` to the new one.

### Traceability chain

`testcases/WBJ_Test_Cases_Notion.csv` (47 TCs, Notion schema, keyed by `TC ID`) ← `@pytest.mark.tc("WBJ-TC-0xx")` on each test → JUnit property `tc_id` → `tools/build_report.py` (joins results to the CSV for title/layer/priority and coverage counts) and `tools/notion_sync.py` (updates Notion pages matched by `TC ID`). When adding or renaming a test, keep the marker, the CSV row's `Automation` / `Automation Approach` columns, and the rules table in `testcases/WBJ_Test_Analysis.md` in step.

Every test also carries a priority marker (`p0`/`p1`/`p2`) and exactly one `tier_*` marker; `smoke`, `perf` and `demo` select subsets. Markers are registered in `pytest_configure`, not `pytest.ini`.

## Game invariants the tests rely on

- **A hand never contains two identical pieces.** `setPieces` picks a distinct piece object per slot and throws otherwise; two identical specs would share one sprite. Build hands from three different pieces (see the `hand()` helper in `test_03_board_rules.py`).
- Rows, columns and 3×3 boxes clear simultaneously. When arranging a board, check the placement does not complete an unintended group (a 3×3 piece at (0,0) on an empty board clears its own box).
- UI values animate: the game-over panel counts the score up from 0. Assert with `wait_until(...)` on the final value, not on first paint.
- All rules are *observed*, not specified. The clear bonus (18 × groups + 10 × streak) is unconfirmed; see the open questions in `testcases/WBJ_Test_Analysis.md`.
- Performance thresholds in `test_07_performance.py` and `LOAD_BUDGET_S` in `test_01_smoke.py` are proposed budgets, not agreed limits.
