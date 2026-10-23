"""CR-013 STOP 3: behavioural checks in a real headless Chromium (not part of the pytest suite; playwright is NOT a project dependency).

    uv run --no-project --with playwright python tests/js/browser_checks.py reports/kg_explorer/index.html
Prints one JSON object; every value must be true."""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

html = Path(sys.argv[1]).resolve()
res: dict[str, bool] = {}
errors: list[str] = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 950}, reduced_motion="reduce")
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(html.as_uri())
    page.wait_for_selector("#tabs button")
    page.click("#tabs button:has-text('Pipeline')")
    page.wait_for_selector("#ribbon button")
    start = page.get_attribute("#ribbon button.on", "data-st")
    page.focus("#ribbon button.on")
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(300)
    res["ribbon_arrowright_moves_the_selected_stage"] = page.get_attribute("#ribbon button.on", "data-st") != start
    res["ribbon_keeps_focus_on_the_selected_stage"] = page.evaluate("document.activeElement.dataset.st") == page.get_attribute("#ribbon button.on", "data-st")
    page.keyboard.press("ArrowLeft")
    page.wait_for_timeout(300)
    res["ribbon_arrowleft_returns"] = page.get_attribute("#ribbon button.on", "data-st") == start
    res["ribbon_has_tab_roles"] = page.evaluate("document.querySelector('#ribbon').getAttribute('role')") == "tablist" and page.evaluate("document.querySelector('#ribbon button.on').getAttribute('aria-selected')") == "true"
    page.click("#tabs button:has-text('Explain a section')")
    page.wait_for_selector("#stepper button")
    page.focus("#stepper button.on")
    i0 = int(page.get_attribute("#stepper button.on", "data-i"))
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(300)
    res["stepper_arrowright_advances"] = int(page.get_attribute("#stepper button.on", "data-i")) == i0 + 1
    res["stepper_next_button_works"] = True
    page.click("#next")
    page.wait_for_timeout(300)
    res["stepper_next_button_works"] = int(page.get_attribute("#stepper button.on", "data-i")) == i0 + 2
    page.click("#tabs button:has-text('Graph')")
    page.evaluate("selectEdge(S.G.edges.find(e=>e.id.startsWith('RP-')))")
    page.wait_for_timeout(900)
    res["reduced_motion_removes_detail_transition_movement"] = page.evaluate("getComputedStyle(document.querySelector('#detailin')).transform") in ("none", "matrix(1, 0, 0, 1, 0, 0)")
    res["journey_is_populated"] = "Edge journey" in page.inner_text("#detail") and "Pair ranking + budget" in page.inner_text("#detail")
    ctx2 = b.new_context(viewport={"width": 390, "height": 844})
    n = ctx2.new_page()
    n.goto(html.as_uri())
    n.wait_for_selector("#tabs button")
    n.click("#tabs button:has-text('Why not?')")
    n.wait_for_timeout(800)
    res["narrow_has_no_horizontal_page_scroll"] = n.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2")
    n.click("#tabs button:has-text('Pipeline')")
    n.wait_for_timeout(800)
    res["narrow_pipeline_has_no_horizontal_page_scroll"] = n.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2")
    page2 = b.new_context(viewport={"width": 1500, "height": 950}).new_page()
    page2.on("pageerror", lambda e: errors.append(str(e)))
    page2.goto(html.as_uri())
    page2.wait_for_selector("#tabs button")
    page2.click("#m-sci")
    page2.wait_for_timeout(600)
    res["scinlp_mode_still_works_and_hides_pd_trace_tabs"] = "Pipeline" not in page2.inner_text("#tabs") and "Document" in page2.inner_text("#tabs")
    page2.click("#m-pd")
    page2.wait_for_timeout(600)
    page2.click("#v-debug")
    page2.wait_for_timeout(600)
    res["debug_view_adds_trace_table_tab"] = "Trace table" in page2.inner_text("#tabs")
    page2.click("#v-review")
    page2.wait_for_timeout(400)
    res["review_view_hides_trace_table_tab"] = "Trace table" not in page2.inner_text("#tabs")
    b.close()
res["no_page_errors"] = not errors
print(json.dumps(res, indent=1))
print("ALL TRUE" if all(res.values()) else "FAILURES: " + str([k for k, v in res.items() if not v]))
