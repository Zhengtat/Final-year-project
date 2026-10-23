"""CR-013 STOP 5: automated accessibility (axe-core) and performance measurements of the explorer in headless Chromium (not part of pytest; playwright and
axe-playwright-python are NOT project dependencies).

    uv run --no-project --with playwright --with axe-playwright-python python tests/js/a11y_perf_checks.py reports/kg_explorer/index.html out.json
These are automated checks only: they find a subset of accessibility problems and are not a manual screen-reader audit."""

import json
import sys
import time
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

html = Path(sys.argv[1]).resolve()
res: dict = {"axe": {}, "perf": {}, "manual": {}}
axe = Axe()
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 950})
    page = ctx.new_page()
    t0 = time.time()
    page.goto(html.as_uri(), wait_until="load")
    page.wait_for_selector("#tabs button")
    res["perf"]["load_to_interactive_ms"] = round((time.time() - t0) * 1000)
    res["perf"]["file_mb"] = round(html.stat().st_size / 1e6, 2)
    res["perf"]["navigation"] = page.evaluate("(()=>{const n=performance.getEntriesByType('navigation')[0];return {domContentLoaded:Math.round(n.domContentLoadedEventEnd),load:Math.round(n.loadEventEnd)}})()")
    res["perf"]["js_heap_mb_after_load"] = round(page.evaluate("performance.memory.usedJSHeapSize") / 1e6, 1)

    def run_axe(name: str) -> None:
        r = axe.run(page, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa"]}})
        res["axe"][name] = {"violations": [{"id": v["id"], "impact": v["impact"], "nodes": len(v["nodes"]), "help": v["help"]} for v in r.response["violations"]], "passes": len(r.response["passes"])}

    page.wait_for_timeout(900)
    run_axe("graph_review")
    t1 = time.time()
    page.click("#tabs button:has-text('Pipeline')")
    page.wait_for_selector("#ribbon button")
    res["perf"]["first_trace_tab_incl_decode_ms"] = round((time.time() - t1) * 1000)
    res["perf"]["trace_decoded_events"] = page.evaluate("TR.events.length")
    for name, tab in (("pipeline", None), ("section", "Explain a section"), ("why", "Why not?"), ("lost", "Rejected / lost"), ("snap", "Stage snapshots")):
        if tab:
            t = time.time()
            page.click(f"#tabs button:has-text('{tab}')")
            page.wait_for_selector(f"#v-{name} h2")
            res["perf"][f"tab_{name}_render_ms"] = round((time.time() - t) * 1000)
            page.wait_for_timeout(800)  # let entry animations finish so contrast is measured on settled colours
        page.wait_for_timeout(800)
        run_axe(f"{name}_review")
    page.click("#tabs button:has-text('Graph')")
    page.evaluate("selectEdge(S.G.edges.find(e=>e.id.startsWith('RP-')))")
    page.wait_for_timeout(900)
    run_axe("edge_journey_review")
    t2 = time.time()
    page.evaluate("for(let i=0;i<5;i++){ view.x+=20; draw(); }")
    page.wait_for_timeout(100)
    res["perf"]["five_redraws_ms"] = round((time.time() - t2) * 1000)
    page.click("#v-debug")
    page.wait_for_timeout(1000)
    run_axe("graph_debug")
    page.click("#tabs button:has-text('Trace table')")
    page.wait_for_timeout(900)
    run_axe("trace_table_debug")
    page.click("#v-review")
    page.click("#m-ev")
    page.wait_for_selector("#v-evmap .evmatrix")
    run_axe("evaluation_map")
    res["perf"]["js_heap_mb_after_everything"] = round(page.evaluate("performance.memory.usedJSHeapSize") / 1e6, 1)
    # manual-style checks
    z = b.new_context(viewport={"width": 750, "height": 475}).new_page()  # 200% zoom equivalent of a 1500 x 950 window
    z.goto(html.as_uri())
    z.wait_for_selector("#tabs button")
    res["manual"]["zoom_200_no_horizontal_page_scroll"] = z.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2")
    page2 = b.new_context(viewport={"width": 1500, "height": 950}).new_page()
    page2.goto(html.as_uri())
    page2.wait_for_selector("#tabs button")
    res["manual"]["landmarks"] = page2.evaluate("({header:!!document.querySelector('header'),main:!!document.querySelector('main'),aside:document.querySelectorAll('aside').length})")
    res["manual"]["buttons_without_accessible_name"] = page2.evaluate("[...document.querySelectorAll('button')].filter(b=>!(b.innerText||'').trim()&&!b.getAttribute('aria-label')&&!b.title).length")
    res["manual"]["inputs_without_label"] = page2.evaluate("[...document.querySelectorAll('input,select')].filter(i=>!i.closest('label')&&!i.getAttribute('aria-label')&&!i.title&&!i.placeholder).map(i=>i.id)")
    res["manual"]["canvas_has_text_alternative_nearby"] = page2.evaluate("!!document.getElementById('status')")
    page2.keyboard.press("Tab")
    res["manual"]["first_tab_reaches_an_interactive_element"] = page2.evaluate("['BUTTON','A','INPUT','SELECT'].includes(document.activeElement.tagName)")
    b.close()
print(json.dumps(res, indent=1))
Path(sys.argv[2]).write_text(json.dumps(res, indent=1))
