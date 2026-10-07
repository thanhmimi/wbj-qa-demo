# Wood Block Journey — QA demo (analysis → test cases → automation)

> **▶ Presentation (works in the GitHub app): [PRESENTATION.md](PRESENTATION.md)** · PDF: [docs/WBJ_QA_Demo_slides.pdf](docs/WBJ_QA_Demo_slides.pdf)

A small, end-to-end run of the proposed QA framework on a live Sun.Studio game:
**Wood Block Journey** (HTML5 / Phaser 3, Playhop–Yandex Games; the same bundle carries the FB Instant path).

```
testcases/WBJ_Test_Analysis.md      game-test-analysis output: state model, 13-layer matrix, risks, questions
testcases/WBJ_Test_Cases_Notion.csv  game-test-case-design output: 47 TCs in the Notion schema (import as a DB)
wbj/bridge.js     QA bridge: captures the Phaser game, exposes read/arrange API (window.__WBJ_QA__)
wbj/driver.py     GameDriver: launch, portal-ad handling, closed-loop drag, evidence
wbj/rules.py      independent rules model = test oracle (fits, clears, FEN)
wbj/vision.py     image tier (OpenCV template match — the Airtest technique)
tests/            32 pytest tests, tagged by TC ID, priority and tier
tools/            build_report.py (HTML report), notion_sync.py (Automation Run → Notion)
```

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium

.venv/bin/pytest                         # full suite, headless (~12 min, fresh player per test)
.venv/bin/pytest -m demo --headed --slowmo 150   # live-demo subset, browser visible
.venv/bin/pytest -m "smoke or p0"        # build gate
.venv/bin/pytest --device small          # same suite on a 360x740 viewport
.venv/bin/pytest --video                 # + one .webm per test in reports/video (demo backup)
.venv/bin/python tools/build_report.py   # -> reports/index.html
.venv/bin/python tools/notion_sync.py    # dry-run payloads; set NOTION_TOKEN/NOTION_RUNS_DB/NOTION_TC_DB to push
```

## How the three tiers map to this game

| Tier | Proposal | Here |
|---|---|---|
| 1 · Game Test Bridge | Dev exposes state/seed/force hooks in dev & staging | `bridge.js` shim over Phaser internals: read board FEN / score / screens, arrange board + hand (replaces RNG) |
| 2 · Poco (UI tree) | read engine node tree | Phaser display list: screen containers, text nodes, cell geometry; real pointer drags with closed-loop correction |
| 3 · Airtest (image) | when nothing else is reachable | OpenCV template match: PLAY button, titles, blank-canvas check |

Rules: **arrange through the bridge, act through real input, assert against the model.**
Ads and analytics networks are blocked in functional runs (`--live-ads` to disable). This keeps runs
deterministic and keeps test traffic out of production KPIs.

## Notes / limits

- The bridge reads production internals of a minified build. That is fine for a demo but it is not a contract.
  In-house, the same method names become a dev-owned `Game Test Bridge` shipped in dev and staging builds.
- Run on GPU-backed Chromium (`channel="chromium"`). The headless shell's software GL halves FPS.
- Tests use the live portal; network or portal changes can fail a run → `reports/evidence/` has screenshots + state.
