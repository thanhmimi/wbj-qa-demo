# Wood Block Journey (web) — Test Analysis

> Output format of the **game-test-analysis** skill. Status: *Draft (AI) → QA-reviewed*.
> Scope: the HTML5 build distributed on Yandex Games / Playhop (same build ships to FB Instant).
> Source of truth used: the live build, store listing and observed behaviour. There was no spec, so every rule below is **observed**, and the open questions go to Game Design.

## 1. Product snapshot

| Item | Observation |
|---|---|
| Game | Wood Block Journey, Sun.Studio, puzzle classic (block + sudoku hybrid), portrait |
| Engine | Phaser 3.55.2 (WebGL), Redux-style store, Spine animations, Sentry/Rollbar error reporting |
| Platforms in build | Yandex Games / Playhop SDK, FB Instant code path (`FBInstant.initializeAsync`), web portals |
| Core loop | 3 pieces dealt → drag onto a 9×9 board → full row / column / 3×3 box clears → new hand when all 3 are used → game over when no piece fits |
| Progression | Target score per level: 100, 250, then +250 each (500, 750 …); progress bar; "Score reached" and "Next target" screens |
| Monetisation | Portal pre-roll/interstitial; **Second Chance** (rewarded, 10 s countdown); banner; interstitial after level |
| Retention | Save/resume of board + hand + score (match store, FEN); best score; daily tasks, daily rewards, missions (gems), lives, tournaments, leaderboard |
| FTUE | 4-step guided tutorial (row → column → box → combo) with Skip + confirm |

## 2. State model (what the tests drive)

```
LOAD → TUTORIAL(1..4) ──skip/complete──► TARGET_SCORE screen ► PLAYING
PLAYING ── place piece ─► (clear? +bonus, streak) ─► hand empty? deal 3 ─► any fit? ─► PLAYING
                                                                       └─ no ─► NO_SPACE_LEFT ► SECOND_CHANCE(10s)
SECOND_CHANCE ── watch ad (ok) ─► rescue (bomb) ► PLAYING
              └─ timeout / ad fails ─► (LOADING AD …) ► GAME_OVER(YOUR SCORE) ── PLAY ─► new game
PLAYING ── score ≥ target ─► SCORE_REACHED ► (interstitial) ► NEXT_TARGET ► PLAYING
any state ── reload ─► resume from saved FEN (board + hand + score)
```

## 3. Observed rules = oracle (`wbj/rules.py`)

| ID | Rule | Confidence |
|---|---|---|
| R-01 | Board 9×9; a piece may be placed only where every cell is empty and inside the board | verified by automation |
| R-02 | Full rows, full columns and full 3×3 boxes clear **simultaneously** after a placement | verified (row, column, box, row+column) |
| R-03 | Hand = 3 pieces; a new hand is dealt only when all 3 are used | verified |
| R-04 | Placement scores +1 per cell | verified (1/4/5/9-cell pieces) |
| R-05 | Clear bonus = 18 × groups + 10 × streak (streak = consecutive clearing moves) | **observed** in automation, needs GD sign-off → Q-03 |
| R-06 | Game over when no piece in hand fits; Second Chance offered first | verified |
| R-07 | First target 100; next 250; then +250 | verified from the level manager + screen |
| R-08 | A hand never contains two identical pieces. There are 50 piece variants, each a single object, and the dealer never repeats an index | verified (dealer code + assertion in TC-024) |
| R-09 | A returning player lands on the home dashboard (Play / Journey / Leaderboard / Daily / Settings), then resumes the saved board | verified (TC-050) |

## 4. Coverage matrix — 13 layers × risk

| # | Layer | What can break | Risk | Main test layer | Automation tier |
|---|---|---|---|---|---|
| L1 | Core rules | wrong fit/clear, ghost cells, box clear missed | **P0** | model-based, state injection | Bridge |
| L2 | State & progression | tutorial loops, target not advancing, soft-lock after screen | **P0** | state transitions | Bridge + scene |
| L3 | Scoring & economy | wrong points, streak drift, coins/diamonds rewards | **P0** | oracle per move | Bridge |
| L4 | UI screens & navigation | popup stuck, wrong score on panel, button dead | P1 | scene tree, image | Scene / Image |
| L5 | Input & controls | drag offset, drop on wrong cell, multi-touch, drop outside | **P0** | real pointer input | Scene |
| L6 | Persistence & session | lose board on reload, tutorial repeats, double rescue | **P0** | reload/resume | Bridge |
| L7 | Monetisation — ads | ad failure blocks player, rewarded not granted, ad over gameplay | **P0** | ads sandbox + failure injection | Scene |
| L8 | Analytics | missing/duplicate level_start/fail/complete, tutorial_complete | P1 | event capture | Bridge (network) |
| L9 | Platform SDK / API | player data, leaderboard, cloud save, SDK init failure | P1 | contract + mock | API |
| L10 | Performance | load time, FPS, memory growth, payload | P1 | budgets | Bridge |
| L11 | Compatibility | viewports, DPR, browsers, low-end Android WebView, portals | P1 | matrix | Scene + Image |
| L12 | Localisation & accessibility | text overflow (bitmap fonts), RU/EN/VI, colour contrast | P2 | visual | Image |
| L13 | Player experience | difficulty curve, piece RNG fairness, juice, audio | P1 | exploratory + data | Manual + data |

## 5. Risks found during analysis (feed to Dev/GD)

| ID | Risk / observation | Impact | Recommendation |
|---|---|---|---|
| RISK-01 | Portal ads (pre-roll, interstitial, mid-session) overlay the game at random | Flaky UI automation; ad-over-gameplay UX | Functional suites block ad networks; a separate ads suite uses test placements |
| RISK-02 | Score on the Game Over panel counts up from 0 | A naive check reads "0" → false bug | Assert after the animation settles. One was caught and **rejected** during this exercise |
| RISK-03 | Debug hooks exist in the production bundle (`createDebugButton`, `debuggerNextPieces`, gated by `isDebugger()`) | Low risk if the gate is safe | Confirm the gate cannot be enabled by a URL parameter on production |
| RISK-04 | Piece RNG is uniform over a weighted list with no "solvable hand" guarantee observed | Unfair game overs → churn | Q-04 to GD; add a data check on game-over boards |
| RISK-05 | Headless CI without a GPU renders through SwiftShader (≈40 fps, 7 CPU cores) | Perf numbers meaningless, slow runs | Run perf on GPU runners or real devices |
| RISK-06 | Test traffic hits production analytics and ad networks | Polluted KPIs and ad revenue data | Block analytics/ads in test runs; use a staging app ID |

## 6. What the exercise surfaced (honest log)

| Type | Item | How it was handled |
|---|---|---|
| False positive avoided | Game Over panel read "0" on first paint | Score counts up over about 2 s. The check now waits for the settled value (TC-042) |
| Test-hook artefact | Injecting two identical pieces made both slots share one sprite, so the wrong slot was consumed | Bridge now enforces the dealer invariant (R-08). Lesson: test hooks must respect game invariants |
| Test-design bug caught by the oracle | Placing the 3×3 piece at (0,0) completes box 0 (+37, not +9) | The model flagged it. The test now asserts "no clear" before checking the score |
| Infra noise | Portal answered 5xx / no "Play now" for returning players | Launch retry plus dashboard path. Recorded in evidence (`launch_retries`, `via_dashboard`) |
| Observation O-01 | In one run with ad/analytics hosts blocked, a returning player's auto-launch stayed black for more than 35 s | Not reproduced in later runs. Check manually with a mainstream ad-blocker before raising it with Playhop |
| Product defects | None confirmed in this scope | 31/31 automated checks green on the live build |

## 7. Questions for PO / GD / Dev

- **Q-01** Is the Second Chance limit one per game (`MaxRescueCount`)? What happens on reload during the countdown?
- **Q-02** Expected behaviour when the rewarded ad fails: today ~6 s of "LOADING AD …", then game over. Is that the intended UX?
- **Q-03** Confirm the scoring formula (R-05), including boxes vs lines and the streak reset rule.
- **Q-04** Does the dealer guarantee at least one placeable piece? Is there a difficulty or rate table per level?
- **Q-05** Can Dev expose an official Game Test Bridge (`window.__WBJ_QA__`: `getState`, `setState(fen)`, `seed(n)`, `forceAd(result)`) in dev/staging builds?

## 8. Assumptions

- The production web build is representative of the FB Instant build. Same bundle, different SDK path.
- The test hooks (state read and arrange) go through a QA shim over Phaser internals. In-house they are replaced by a dev-owned bridge contract with the same method names.
