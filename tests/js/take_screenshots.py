"""CR-013 STOP 3: screenshots of the P&D explorer in a real headless Chromium (not part of the pytest suite; playwright is NOT a project dependency).

    uv run --no-project --with playwright python tests/js/take_screenshots.py reports/kg_explorer/index.html reports/cr013/screenshots
Prints console errors and page errors (there must be none)."""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

html = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
errors: list[str] = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 950}, color_scheme="light")
    page = ctx.new_page()
    page.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.goto(html.as_uri())
    page.wait_for_selector("#tabs button")

    def shot(name: str, wait: int = 700) -> None:
        page.wait_for_timeout(wait)
        page.screenshot(path=str(out / f"{name}.png"))

    def tab(label: str) -> None:
        page.click(f"#tabs button:has-text('{label}')")
        page.wait_for_timeout(900)

    shot("01_graph_review")
    tab("Pipeline")
    page.click("#ribbon button[data-st='pair_selection']")
    shot("02_pipeline_pair_selection")
    tab("Explain a section")
    page.select_option("#v-section .tsec", "3.3")
    page.click("#stepper button[data-i='6']")
    shot("03_section_budget_boundary")
    page.click("#stepper button[data-i='7']")
    shot("04_section_relation_decision")
    page.click("#stepper button[data-i='9']")
    shot("05_section_local_graph")
    tab("Why not?")
    link = page.locator("a[data-why]").first
    link.click()
    shot("06_why_not_pair_not_delivered")
    tab("Rejected / lost")
    page.select_option("#v-lost .tsec", "3.3")
    shot("07_rejected_lost_items")
    tab("Stage snapshots")
    page.select_option("#v-snap .tsec", "3.3")
    page.evaluate("document.querySelector('#snapr').value=3; document.querySelector('#snapr').dispatchEvent(new Event('input'))")
    shot("08_stage_snapshot_classification")
    tab("Graph")
    page.fill("#f-q", "bandwidth")
    page.wait_for_timeout(600)
    page.evaluate("S.sel=null")
    # open an edge journey: select the first committed edge through the page API
    page.evaluate("selectEdge(S.G.edges.find(e=>e.id.startsWith('RP-')))")
    page.wait_for_timeout(1200)
    shot("09_edge_journey_review", 900)
    page.evaluate("selectNode(S.G.nodes.find(n=>n.linked&&n.n_mentions>6).id)")
    page.wait_for_timeout(1200)
    shot("10_node_journey_review", 900)
    page.click("#v-debug")
    page.wait_for_timeout(900)
    page.evaluate("selectEdge(S.G.edges.find(e=>e.id.startsWith('RP-')))")
    page.wait_for_timeout(1200)
    shot("11_edge_journey_debug", 900)
    tab("Trace table")
    shot("12_debug_trace_table")
    page.click("#v-review")
    page.click("#m-sci")
    page.wait_for_timeout(900)
    page.screenshot(path=str(out / "_scinlp_local_only.png"))  # contains SciNLP text: local only, gitignored
    page.click("#m-pd")
    page.wait_for_timeout(600)
    n = ctx.new_page()
    n.on("pageerror", lambda e: errors.append(f"narrow pageerror: {e}"))
    n.set_viewport_size({"width": 390, "height": 844})
    n.goto(html.as_uri())
    n.wait_for_selector("#tabs button")
    n.click("#tabs button:has-text('Pipeline')")
    n.wait_for_timeout(1200)
    n.screenshot(path=str(out / "13_narrow_pipeline.png"))
    dark = b.new_context(viewport={"width": 1500, "height": 950}, color_scheme="dark").new_page()
    dark.goto(html.as_uri())
    dark.wait_for_selector("#tabs button")
    dark.click("#tabs button:has-text('Pipeline')")
    dark.wait_for_timeout(1000)
    dark.screenshot(path=str(out / "14_dark_pipeline.png"))
    b.close()
print("errors:", errors if errors else "none")
