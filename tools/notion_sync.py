"""Push a JUnit run to Notion: one 'Automation Runs' page + per-TC result update.

Dry-run by default (prints the payloads). Set NOTION_TOKEN, NOTION_RUNS_DB and NOTION_TC_DB to push.
Matching rule (same as the notion-test-case-sync skill): Test Cases are matched by the 'TC ID' property.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_report import ROOT, load_results  # noqa: E402

API = "https://api.notion.com/v1"
HEADERS = lambda: {"Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
                   "Notion-Version": "2022-06-28", "Content-Type": "application/json"}


def run_page(meta, results, build: str, commit: str):
    passed = sum(r["status"] == "passed" for r in results)
    failed = sum(r["status"] in ("failed", "error") for r in results)
    return {
        "parent": {"database_id": os.environ.get("NOTION_RUNS_DB", "<RUNS_DB>")},
        "properties": {
            "Run": {"title": [{"text": {"content": f"WBJ web · {build} · {meta['timestamp'][:16]}"}}]},
            "Game": {"select": {"name": "Wood Block Journey"}},
            "Suite": {"select": {"name": os.environ.get("SUITE", "Regression")}},
            "Build": {"rich_text": [{"text": {"content": build}}]},
            "Commit": {"rich_text": [{"text": {"content": commit}}]},
            "Passed": {"number": passed}, "Failed": {"number": failed},
            "Pass Rate": {"number": round(passed / max(1, len(results)), 4)},
            "Duration (min)": {"number": round(meta["time"] / 60, 1)},
            "Status": {"select": {"name": "Green" if failed == 0 else "Red"}},
        },
    }


def tc_updates(results):
    by_tc = {}
    for r in results:
        for tc in [t.strip() for t in (r.get("tc_id") or "").split(",") if t.strip()]:
            prev = by_tc.get(tc, "passed")
            by_tc[tc] = "failed" if "failed" in (prev, r["status"]) or r["status"] == "error" else "passed"
    return by_tc


def push(results, meta, build, commit):
    page = run_page(meta, results, build, commit)
    rp = requests.post(f"{API}/pages", headers=HEADERS(), json=page, timeout=30)
    rp.raise_for_status()
    run_id = rp.json()["id"]
    for tc, status in tc_updates(results).items():
        q = requests.post(f"{API}/databases/{os.environ['NOTION_TC_DB']}/query", headers=HEADERS(), timeout=30,
                          json={"filter": {"property": "TC ID", "rich_text": {"equals": tc}}}).json()
        for hit in q.get("results", []):
            requests.patch(f"{API}/pages/{hit['id']}", headers=HEADERS(), timeout=30, json={"properties": {
                "Last Result": {"select": {"name": status.capitalize()}},
                "Last Run": {"relation": [{"id": run_id}]}}}).raise_for_status()
    print("pushed run", run_id)


def main():
    results, meta = load_results(ROOT / "reports" / "junit.xml")
    build = os.environ.get("BUILD_ID", "playhop-live")
    commit = os.environ.get("CI_COMMIT_SHORT_SHA", "-")
    if not os.environ.get("NOTION_TOKEN"):
        print("[dry-run] Automation Run page:")
        print(json.dumps(run_page(meta, results, build, commit), indent=2))
        print("[dry-run] TC result updates:", json.dumps(tc_updates(results), indent=2))
        return
    push(results, meta, build, commit)


if __name__ == "__main__":
    main()
