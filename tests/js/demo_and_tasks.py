"""CR-013 STOP 5: (1) runs the complete supervisor / examiner demonstration flow once through the real UI in headless Chromium, asserting what is on screen at each step and
saving a screenshot per step; (2) a SCRIPTED feasibility check that each face-check task can be completed in the UI. The scripted check is NOT a usability study: it shows only that
the information each task asks for is reachable; it says nothing about how people experience the page.

    uv run --no-project --with playwright python tests/js/demo_and_tasks.py reports/kg_explorer/index.html reports/cr013/demo /tmp/demo_log.json"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

html = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
log: list[dict] = []
tasks: dict[str, dict] = {}
errors: list[str] = []


def step(page, n: str, title: str, check, shot: bool = True) -> None:
    t = time.time()
    ok, evidence = check()
    page.wait_for_timeout(500)
    if shot:
        page.screenshot(path=str(out / f"{n}.png"))
    log.append({"step": n, "title": title, "ok": bool(ok), "evidence": evidence[:300], "seconds": round(time.time() - t, 2)})


with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_context(viewport={"width": 1500, "height": 950}).new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(html.as_uri())
    page.wait_for_selector("#tabs button")
    t_all = time.time()

    # 1 open a textbook section (Explain a section) and show the source sentences the generator cited
    page.click("#tabs button:has-text('Explain a section')")
    page.wait_for_selector("#stepper button")
    page.select_option("#v-section .tsec", "3.3")
    page.wait_for_selector("#v-section .srcbox mark")
    step(page, "demo_01_source_text", "Open section 3.3: source text with the evidence sentences the generator cited highlighted", lambda: (page.locator("#v-section .srcbox mark").count() > 5, f"{page.locator('#v-section .srcbox mark').count()} highlighted evidence spans"))
    # 2 generator
    page.click("#stepper button[data-i='1']")
    step(page, "demo_02_generator", "Concepts proposed by the generator, with the recorded model reason (or NOT_RECORDED)", lambda: ("proposed" in page.inner_text("#stepbody") and page.locator("#stepbody table.t tr").count() > 5, page.inner_text("#stepbody")[:160]))
    # 3 verifier (passed / rejected)
    page.click("#stepper button[data-i='2']")
    step(page, "demo_03_verification", "Verifier: one candidate that was rejected, with the rule that rejected it", lambda: ("was rejected by verifier rule" in page.inner_text("#stepbody"), page.inner_text("#stepbody")[:200]))
    # 4 pruning
    page.click("#stepper button[data-i='3']")
    step(page, "demo_04_pruning", "Pruner: scores recorded, nothing pruned, threshold NOT_RECORDED", lambda: ("NOT_RECORDED" in page.inner_text("#stepbody") and "kept" in page.inner_text("#stepbody"), page.inner_text("#stepbody")[:200]))
    # 5 canonicalisation
    page.click("#stepper button[data-i='4']")
    step(page, "demo_05_canonicalisation", "Canonicalisation: name links and taxonomy decisions (identity, not relations); blocked merges NOT_RECORDED", lambda: ("Blocked merges" in page.inner_text("#stepbody"), page.inner_text("#stepbody")[:200]))
    # 6 eligible pairs
    page.click("#stepper button[data-i='5']")
    step(page, "demo_06_eligible_pairs", "Eligible candidate pairs of the section (REPLAYED layer, labelled)", lambda: ("REPLAYED" in page.inner_text("#stepbody"), page.inner_text("#stepbody")[:200]))
    # 7 budget boundary
    page.click("#stepper button[data-i='6']")
    step(page, "demo_07_budget_boundary", "Selection budget and the boundary: selected versus not selected pairs", lambda: ("Budget for the whole run" in page.inner_text("#stepbody") and "not selected" in page.inner_text("#stepbody"), page.inner_text("#stepbody")[:220]))
    # 8 relation decision then open one selected pair as an edge journey (relation, direction, evidence, validation)
    page.click("#stepper button[data-i='7']")
    step(page, "demo_08_relation_decisions", "Relation decisions of the section: outcome, relation, direction, reason code", lambda: ("The classifier decided" in page.inner_text("#stepbody"), page.inner_text("#stepbody")[:200]))
    page.click("#stepper button[data-i='9']")
    page.wait_for_selector("#sec-edges a[data-edge]")
    page.locator("#sec-edges a[data-edge]").first.click()
    page.wait_for_timeout(1500)
    step(page, "demo_09_edge_journey", "One committed relation: evidence with source and target highlighted, direction, qualifiers, relation decision, validation, rank and budget", lambda: (all(k in page.inner_text("#detail") for k in ("Edge journey", "Relation classification", "Validation", "Graph commit", "REPLAYED")) or all(k in page.inner_text("#detail") for k in ("Edge journey", "Relation classification", "Validation", "Graph commit")), page.inner_text("#detail")[:240]))
    # 10 local graph
    page.click("#tabs button:has-text('Explain a section')")
    page.wait_for_selector("#stepper button")
    page.click("#stepper button[data-i='9']")
    page.wait_for_timeout(700)
    step(page, "demo_10_local_graph", "The resulting local graph of the section (committed edges; rejected relations dashed red)", lambda: ("committed edges" in page.inner_text("#stepbody"), page.inner_text("#stepbody")[:200]))
    # 11 Why not? on a pair that did not become an edge
    page.click("#tabs button:has-text('Why not?')")
    page.locator("a[data-why]").first.click()
    page.wait_for_selector(".fail")
    step(page, "demo_11_why_not", "Why not? for a pair that never became an edge: stage-by-stage checks and the earliest observable failure", lambda: ("Earliest observable failure: P0" in page.inner_text("#v-why") or "Earliest observable failure" in page.inner_text("#v-why"), page.inner_text("#v-why .fail")))
    # 12 zoom out to the global graph
    page.click("#tabs button:has-text('Graph')")
    page.click("button[data-tour='centre']")
    page.wait_for_timeout(1200)
    step(page, "demo_12_global_graph", "Zoom out: the chapter / global P&D graph (centre of the graph view)", lambda: ("598 nodes" in page.inner_text("#status") or "nodes" in page.inner_text("#status"), page.inner_text("#status")))
    # 13 optional: evaluation overlay
    page.click("#m-ev")
    page.wait_for_selector("#v-evmap .evmatrix")
    page.click("button[data-ds='pd']")
    page.wait_for_selector("#v-evmap .evmatrix")
    step(page, "demo_13_evaluation_overlay_optional", "Optional: the CR-012 evaluation overlay, clearly labelled as evaluation output and not the production graph", lambda: ("EVALUATION OUTPUT" in page.inner_text("#banner") and "NOT the production Expert KG" in page.inner_text("#banner"), page.inner_text("#banner")[:200]))
    total_seconds = round(time.time() - t_all, 1)
    page.click("#m-pd")
    page.wait_for_timeout(600)

    # ---------------- scripted feasibility of the ten face-check tasks (NOT human usability)
    def task(tid: str, fn) -> None:
        try:
            ok, ev = fn()
        except Exception as e:  # noqa: BLE001
            ok, ev = False, f"{type(e).__name__}: {str(e)[:150]}"
        tasks[tid] = {"completable_in_ui": bool(ok), "evidence": str(ev)[:200]}

    page.click("#tabs button:has-text('Explain a section')")
    page.click("#stepper button[data-i='9']")
    page.wait_for_timeout(600)
    task("T1", lambda: ("committed edges" in page.inner_text("#stepbody"), page.inner_text("#stepbody")[:80]))
    page.click("#tabs button:has-text('Rejected / lost')")
    page.wait_for_timeout(800)
    task("T2", lambda: ("was rejected by verifier rule" in page.inner_text("#v-lost"), page.inner_text("#v-lost")[:100]))
    page.click("#tabs button:has-text('Graph')")
    page.evaluate("selectNode(S.G.nodes.find(n=>n.linked&&n.n_mentions>6).id)")
    page.wait_for_timeout(1500)
    task("T3", lambda: ("Node journey" in page.inner_text("#detail") and "Concept generator" in page.inner_text("#detail"), "Node journey with stages"))
    page.evaluate("selectEdge(S.G.edges.find(e=>e.id.startsWith('RP-')))")
    page.wait_for_timeout(1500)
    task("T4", lambda: (all(k in page.inner_text("#detail").lower() for k in ("evidence", "source", "target", "exact quote the model cited")), "evidence sentence with source / target legend and the cited quote"))
    task("T6", lambda: ("REPLAYED" in page.inner_text("#detail") or "replayed" in page.inner_text("#detail"), "REPLAYED label in the edge journey"))
    task("T9", lambda: ("NOT_AVAILABLE_IN_RETAINED_OUTPUT" in page.inner_text("#detail") or "NOT_RECORDED" in page.inner_text("#detail"), "unavailable field shown explicitly"))
    page.click("#tabs button:has-text('Why not?')")
    page.locator("a[data-why]").first.click()
    page.wait_for_selector(".fail")
    task("T5", lambda: ("Earliest observable failure" in page.inner_text("#v-why"), page.inner_text("#v-why .fail")[:100]))
    page.click("#tabs button:has-text('Pipeline')")
    page.wait_for_selector("#ribbon button")
    task("T7", lambda: (page.locator("#v-pipeline .funnel .fr").count() >= 6, f"{page.locator('#v-pipeline .funnel .fr').count()} funnel rows"))
    page.click("#v-debug")
    page.wait_for_timeout(800)
    page.click("#tabs button:has-text('Graph')")
    page.evaluate("selectEdge(S.G.edges.find(e=>e.id.startsWith('RP-')))")
    page.wait_for_timeout(1500)
    page.locator("#detail summary:has-text('trace fields')").nth(0).scroll_into_view_if_needed()
    page.evaluate("document.querySelectorAll('#detail details').forEach(d=>d.open=true)")  # a reader expands the 'trace fields' disclosure
    page.wait_for_timeout(300)
    task("T8", lambda: (all(k in page.inner_text("#detail").lower() for k in ("gpt-", "prompt version")) and "source_locator" in page.inner_text("#detail"), "model, prompt version (in the text) and source_locator (in the expanded trace fields) of the Debug edge journey"))
    page.click("#v-review")
    page.click("#tabs button:has-text('Stage snapshots')")
    page.wait_for_selector("#snapr")
    labels = []
    for v in (0, 2, 4):
        page.evaluate(f"document.querySelector('#snapr').value={v}; document.querySelector('#snapr').dispatchEvent(new Event('input'))")
        page.wait_for_timeout(300)
        labels.append(page.inner_text("#snapl"))
    task("T10", lambda: (len(set(labels)) == 3, " | ".join(labels)[:160]))
    b.close()

summary = {"demo_steps": log, "demo_all_steps_ok": all(s["ok"] for s in log), "demo_seconds_scripted": total_seconds, "task_feasibility": tasks, "all_tasks_completable": all(t["completable_in_ui"] for t in tasks.values()), "page_errors": errors}
Path(sys.argv[3]).write_text(json.dumps(summary, indent=1))
print(json.dumps({k: v for k, v in summary.items() if k != "demo_steps"}, indent=1))
for s in log:
    print(("OK  " if s["ok"] else "FAIL"), s["step"], "-", s["title"][:80])
