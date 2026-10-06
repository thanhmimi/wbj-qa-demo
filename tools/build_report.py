"""Build reports/index.html from JUnit XML + evidence + the Notion test-case export.

Same data that `notion_sync.py` pushes to the Notion "Automation Runs" database; this page is the
offline view for the CI artifact (and the live demo).
"""
from __future__ import annotations

import csv
import html
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
TC_CSV = ROOT / "testcases" / "WBJ_Test_Cases_Notion.csv"


def load_results(junit: Path):
    tree = ET.parse(junit)
    suite = tree.getroot().find("testsuite") if tree.getroot().tag == "testsuites" else tree.getroot()
    out = []
    for case in suite.iter("testcase"):
        props = {p.get("name"): p.get("value") for p in case.iter("property")}
        status, message = "passed", ""
        for tag in ("failure", "error", "skipped"):
            el = case.find(tag)
            if el is not None:
                status = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                message = (el.get("message") or "")[:400]
        out.append({"name": case.get("name"), "file": (case.get("classname") or "").split(".")[-1],
                    "time": float(case.get("time") or 0), "status": status, "message": message, **props})
    meta = {"tests": int(suite.get("tests", 0)), "time": float(suite.get("time", 0)),
            "timestamp": suite.get("timestamp", ""), "host": suite.get("hostname", "")}
    return out, meta


def load_tcs():
    if not TC_CSV.exists():
        return {}
    with TC_CSV.open(encoding="utf-8") as f:
        return {r["TC ID"]: r for r in csv.DictReader(f)}


def evidence_for(r):
    shot = r.get("screenshot")
    if not shot:
        return None, {}
    ev_path = ROOT / Path(shot).parent / "evidence.json"
    ev = json.loads(ev_path.read_text()) if ev_path.exists() else {}
    return Path(shot).relative_to("reports").as_posix(), ev


def main(junit_path: str = "reports/junit.xml"):
    results, meta = load_results(ROOT / junit_path)
    tcs = load_tcs()
    counts = Counter(r["status"] for r in results)
    by_tier = defaultdict(Counter)
    for r in results:
        by_tier[r.get("tier", "-")][r["status"]] += 1
    tc_ids_run = {t.strip() for r in results if r.get("tc_id") for t in r["tc_id"].split(",")}
    layers = Counter(t["Layer"] for t in tcs.values())
    auto = Counter(t["Automation"] for t in tcs.values())
    rate = 100 * counts["passed"] / max(1, len(results))

    rows = []
    for r in results:
        tc = tcs.get(r.get("tc_id", "").split(",")[0].strip(), {})
        shot, ev = evidence_for(r)
        snap = ev.get("snapshot", {})
        timing = ev.get("timing", {})
        rows.append(f"""
<tr class="{r['status']}">
  <td><span class="pill {r['status']}">{r['status'].upper()}</span></td>
  <td class="mono nw">{html.escape(r.get('tc_id', '-')).replace(', ', '<br>')}</td>
  <td><b>{html.escape(tc.get('Title', r['name']))}</b><div class="sub mono">{html.escape(r['file'])}::{html.escape(r['name'])}</div>
      {'<div class="err">' + html.escape(r['message']) + '</div>' if r['message'] else ''}</td>
  <td>{html.escape(tc.get('Layer', '-'))}</td>
  <td>{html.escape(r.get('tier', '-'))}</td>
  <td>{html.escape(tc.get('Priority', '-'))}</td>
  <td class="num">{r['time']:.1f}s</td>
  <td class="mono small ev">score={snap.get('score') if snap.get('score') is not None else '-'} · ready={timing.get('game_ready_s', '-')}s · fps={snap.get('fps', '-')}<br>{html.escape(str(snap.get('fen', ''))[:60])}</td>
  <td>{f'<a href="{shot}" target="_blank"><img src="{shot}" loading="lazy"></a>' if shot else ''}</td>
</tr>""")

    tier_rows = "".join(
        f"<tr><td>{html.escape(t)}</td><td class='num'>{c['passed']}</td><td class='num'>{c['failed'] + c['error']}</td></tr>"
        for t, c in sorted(by_tier.items()))
    layer_rows = "".join(
        f"<tr><td>{html.escape(l)}</td><td class='num'>{n}</td>"
        f"<td class='num'>{sum(1 for t in tcs.values() if t['Layer'] == l and t['Automation'] == 'Automated')}</td></tr>"
        for l, n in sorted(layers.items(), key=lambda x: int(x[0].split()[0][1:])))

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WBJ Automation Run</title>
<style>
:root{{--bg:#f6f4ef;--card:#fff;--ink:#1d1b16;--mut:#6b6559;--line:#e4dfd3;--ok:#1f8a4c;--bad:#c0392b;--warn:#b7791f;--acc:#8a5a2b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#16140f;--card:#201d17;--ink:#f1ece2;--mut:#a59d8d;--line:#352f25}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,Segoe UI,Inter,Roboto,sans-serif}}
.wrap{{max-width:1280px;margin:0 auto;padding:24px 16px 60px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:15px;margin:28px 0 10px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut)}}
.sub{{color:var(--mut);font-size:12px}} .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}} .small{{font-size:11px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:16px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}} .kpi b{{font-size:26px;display:block}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px}} @media(max-width:800px){{.grid2{{grid-template-columns:1fr}}}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}} th{{font-size:11px;text-transform:uppercase;color:var(--mut);letter-spacing:.05em}}
.num{{text-align:right;font-variant-numeric:tabular-nums}} .nw{{white-space:nowrap}} .ev{{max-width:230px;word-break:break-all}} img{{width:48px;border-radius:6px;border:1px solid var(--line)}}
.pill{{font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;color:#fff}} .pill.passed{{background:var(--ok)}} .pill.failed,.pill.error{{background:var(--bad)}} .pill.skipped{{background:var(--warn)}}
.err{{color:var(--bad);font-size:12px;margin-top:4px;white-space:pre-wrap}} .scroll{{overflow-x:auto}}
.ladder{{display:flex;gap:8px;flex-wrap:wrap}} .step{{flex:1;min-width:220px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}} .step b{{color:var(--acc)}}
</style></head><body><div class="wrap">
<h1>Wood Block Journey · Automation Run</h1>
<div class="sub">Sun.Studio · HTML5 build on Playhop/Yandex (same bundle as FB Instant) · Python + Pytest + Playwright · generated {datetime.now():%Y-%m-%d %H:%M}</div>
<div class="kpis">
 <div class="kpi"><b>{len(results)}</b>tests executed</div>
 <div class="kpi"><b style="color:var(--ok)">{rate:.0f}%</b>pass rate ({counts['passed']} passed)</div>
 <div class="kpi"><b style="color:var(--bad)">{counts['failed'] + counts['error']}</b>failed / error</div>
 <div class="kpi"><b>{meta['time'] / 60:.1f} min</b>wall time</div>
 <div class="kpi"><b>{len(tc_ids_run)}/{len(tcs)}</b>TCs covered by this run</div>
 <div class="kpi"><b>{auto.get('Automated', 0)} · {auto.get('Candidate', 0)} · {auto.get('Manual', 0)}</b>automated · candidate · manual</div>
</div>
<h2>Automation ladder used on this canvas game</h2>
<div class="ladder">
 <div class="step"><b>1 · Bridge</b><br>Read/arrange game state (board FEN, score, hand, screens). Deterministic setup instead of RNG. Shim today; dev-owned contract in-house.</div>
 <div class="step"><b>2 · Scene tree</b><br>Phaser display list read like Poco: screen names, text nodes, cell geometry. Real pointer drags with closed-loop correction.</div>
 <div class="step"><b>3 · Image</b><br>OpenCV template match (Airtest technique) when nothing else is reachable: PLAY button, titles, blank-canvas check.</div>
</div>
<div class="grid2">
 <div><h2>Result by tier</h2><table><tr><th>Tier</th><th class="num">Pass</th><th class="num">Fail</th></tr>{tier_rows}</table></div>
 <div><h2>Coverage by layer (test-case repository)</h2><table><tr><th>Layer</th><th class="num">TCs</th><th class="num">Automated</th></tr>{layer_rows}</table></div>
</div>
<h2>Test results</h2>
<div class="scroll"><table>
<tr><th>Status</th><th>TC ID</th><th>Test</th><th>Layer</th><th>Tier</th><th>Prio</th><th class="num">Time</th><th>Evidence</th><th>Shot</th></tr>
{''.join(rows)}
</table></div>
<p class="sub">Evidence per test: final screenshot, bridge snapshot (FEN, score, screens), console errors, blocked ad/analytics requests → <span class="mono">reports/evidence/</span>. JUnit: <span class="mono">reports/junit.xml</span>.</p>
</div></body></html>"""
    out = REPORTS / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"report: {out}  ({counts['passed']} passed, {counts['failed'] + counts['error']} failed)")


if __name__ == "__main__":
    main(*sys.argv[1:])
