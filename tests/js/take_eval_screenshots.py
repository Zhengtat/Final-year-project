"""CR-013 STOP 4: screenshots and behaviour checks of the evaluation overlay in headless Chromium (not part of pytest; playwright is NOT a project dependency).

    uv run --no-project --with playwright python tests/js/take_eval_screenshots.py reports/kg_explorer/index.html reports/cr013/screenshots
Files starting with `_` contain SciNLP text (CC BY-NC) and are gitignored."""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

html = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2])
errors: list[str] = []
checks: dict[str, bool] = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 950})
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)
    page.goto(html.as_uri())
    page.wait_for_selector("#tabs button")
    # --- production isolation: nothing evaluation-related is loaded or shown until the user opts in
    checks["overlay_payload_not_decoded_at_start"] = page.evaluate("EV === null")
    for tab in ("Pipeline", "Explain a section", "Why not?", "Rejected / lost", "Stage snapshots", "Graph"):
        page.click(f"#tabs button:has-text('{tab}')")
        page.wait_for_timeout(500)
    page.evaluate("selectEdge(S.G.edges.find(e=>e.id.startsWith('RP-')))")
    page.wait_for_timeout(900)
    prod_text = page.evaluate("document.querySelector('main').innerText").lower()
    checks["production_views_show_no_gold_or_evaluation_text"] = "gold" not in prod_text and "frozen cr-012" not in prod_text and "evaluation overlay" not in prod_text.replace("cr-012 evaluation overlay", "")
    checks["overlay_still_not_decoded_after_all_production_views"] = page.evaluate("EV === null")
    # --- opt in
    page.click("#m-ev")
    page.wait_for_selector("#v-evmap .evmatrix")
    checks["opt_in_loads_the_overlay"] = page.evaluate("EV !== null")
    checks["banner_marks_evaluation_output"] = "EVALUATION OUTPUT" in page.inner_text("#banner") and "NOT the production Expert KG" in page.inner_text("#banner")
    checks["no_graph_tab_in_evaluation_mode"] = "Graph" not in page.inner_text("#tabs").replace("Failure map", "")
    page.screenshot(path=str(out / "_eval_scinlp_failure_map.png"))
    checks["scinlp_failure_map_shows_the_frozen_headline"] = "0.050" in page.inner_text("#v-evmap") and "NOT_EVALUABLE_SMALL_N" in page.inner_text("#v-evmap")
    page.click("button[data-ds='pd']")
    page.wait_for_selector("#v-evmap .evmatrix")
    page.wait_for_timeout(500)
    checks["pd_overlay_is_a_separate_dataset"] = "P&D held-out" in page.inner_text("#banner") and "0.053" in page.inner_text("#v-evmap") and "SciNLP" not in page.inner_text("#v-evmap")
    page.screenshot(path=str(out / "15_eval_pd_failure_map.png"))
    # click a P0 cell of the first section -> gold list filtered
    page.click("#v-evmap td.evcell[data-code='P0']")
    page.wait_for_selector("#v-evlist table.t tr[data-u]")
    page.wait_for_timeout(400)
    checks["matrix_cell_filters_the_gold_list"] = "P0" in page.inner_text("#v-evlist .leg button.on")
    page.screenshot(path=str(out / "16_eval_pd_gold_relations_p0.png"))
    page.click("#v-evlist tr[data-u]")
    page.wait_for_timeout(500)
    checks["detail_names_the_earliest_failure_and_marks_later_stages"] = "earliest failure" in page.inner_text("#detail").lower() and "not evaluated" in page.inner_text("#detail")
    page.screenshot(path=str(out / "17_eval_pd_detail_p0.png"))
    # an R1 (wrong relation) example from the glossary
    page.click("#tabs button:has-text('Failure map')")
    page.wait_for_selector("#v-evmap .evmatrix")
    page.evaluate("document.querySelectorAll('#v-evmap a[data-ex]').forEach(a=>{ if(a.closest('tr').innerText.startsWith('R1')) a.click(); })")
    page.wait_for_timeout(700)
    page.screenshot(path=str(out / "18_eval_pd_detail_r1_example.png"))
    # SciNLP detail (local only)
    page.click("button[data-ds='scinlp']")
    page.click("#tabs button:has-text('Failure map')")
    page.wait_for_selector("#v-evmap .evmatrix")
    page.click("#v-evmap td.evcell[data-code='P0']")
    page.wait_for_selector("#v-evlist tr[data-u]")
    page.click("#v-evlist tr[data-u]")
    page.wait_for_timeout(500)
    checks["scinlp_detail_offers_the_graph_link_for_a_missed_relation"] = page.locator("#ev-opengraph").count() == 1
    page.screenshot(path=str(out / "_eval_scinlp_detail.png"))
    page.click("#ev-opengraph")
    page.wait_for_timeout(1200)
    checks["open_in_graph_switches_to_the_scinlp_graph_and_selects_the_missed_edge"] = "Missed by the system" in page.inner_text("#detail")
    # back to production: overlay content gone from production views
    page.click("#m-pd")
    page.wait_for_timeout(700)
    checks["leaving_the_overlay_returns_to_the_production_graph"] = "P&D Expert KG" in page.inner_text("#banner") and "gold" not in page.inner_text("#banner").lower()
    # debug / review toggle inside the overlay and keyboard reachability of the dataset buttons
    page.click("#m-ev")
    page.wait_for_selector("#v-evmap .evmatrix")
    page.click("#v-debug")
    page.wait_for_timeout(500)
    checks["debug_view_keeps_the_overlay_open"] = page.locator("#v-evmap .evmatrix").count() == 1
    page.click("#v-review")
    nr = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    nr.goto(html.as_uri())
    nr.wait_for_selector("#tabs button")
    nr.click("#m-ev")
    nr.click("button[data-ds='pd']")
    nr.wait_for_selector("#v-evmap .evmatrix")
    nr.wait_for_timeout(800)
    checks["narrow_overlay_has_no_horizontal_page_scroll"] = nr.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2")
    nr.screenshot(path=str(out / "19_eval_pd_narrow.png"))
    dk = b.new_context(viewport={"width": 1500, "height": 950}, color_scheme="dark").new_page()
    dk.goto(html.as_uri())
    dk.wait_for_selector("#tabs button")
    dk.click("#m-ev")
    dk.click("button[data-ds='pd']")
    dk.wait_for_selector("#v-evmap .evmatrix")
    dk.wait_for_timeout(800)
    dk.screenshot(path=str(out / "20_eval_pd_dark.png"))
    b.close()
checks["no_page_errors"] = not errors
print(json.dumps(checks, indent=1))
print("errors:", errors if errors else "none")
print("ALL TRUE" if all(checks.values()) else "FAILURES: " + str([k for k, v in checks.items() if not v]))
