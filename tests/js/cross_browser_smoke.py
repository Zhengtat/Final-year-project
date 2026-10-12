"""CR-013 STOP 5: smoke test of the explorer in non-Chromium engines (Playwright Firefox and WebKit builds; not part of pytest, playwright is NOT a project dependency).
This is a smoke test only: it shows that these engine builds load the page and run the main flows. It is not a compatibility guarantee for Safari or Firefox releases.

    uv run --no-project --with playwright python tests/js/cross_browser_smoke.py reports/kg_explorer/index.html out.json [screenshot_dir]"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

html = Path(sys.argv[1]).resolve()
shots = Path(sys.argv[3]) if len(sys.argv) > 3 else None
res: dict = {}
with sync_playwright() as p:
    for name in ("firefox", "webkit"):
        r: dict = {}
        errors: list[str] = []
        try:
            b = getattr(p, name).launch()
            ctx = b.new_context(viewport={"width": 1400, "height": 900})
            page = ctx.new_page()
            page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
            r["engine_version"] = b.version
            page.goto(html.as_uri())
            page.wait_for_selector("#tabs button", timeout=20000)
            r["has_DecompressionStream"] = page.evaluate("typeof DecompressionStream === 'function'")
            r["page_loads_and_graph_tab_present"] = True
            page.click("#tabs button:has-text('Pipeline')")
            page.wait_for_selector("#ribbon button", timeout=20000)
            r["trace_decodes_and_pipeline_renders"] = page.evaluate("TR !== null && TR.events.length > 19000")
            page.click("#ribbon button[data-st='pair_selection']")
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(300)
            r["ribbon_keyboard_navigation"] = page.get_attribute("#ribbon button.on", "data-st") == "relation_classification"
            page.click("#tabs button:has-text('Explain a section')")
            page.wait_for_selector("#stepper button")
            page.click("#stepper button[data-i='7']")
            r["section_walkthrough_step_renders"] = "pair" in page.inner_text("#stepbody").lower()
            page.click("#tabs button:has-text('Why not?')")
            page.locator("a[data-why]").first.click()
            page.wait_for_selector(".fail")
            r["why_not_answers"] = "Earliest observable failure" in page.inner_text("#v-why")
            page.click("#tabs button:has-text('Graph')")
            page.evaluate("selectEdge(S.G.edges.find(e=>e.id.startsWith('RP-')))")
            page.wait_for_timeout(1200)
            r["edge_journey_renders"] = "Edge journey" in page.inner_text("#detail") and "REPLAYED" in page.inner_text("#detail")
            r["canvas_has_drawn_pixels"] = page.evaluate("(()=>{const c=document.getElementById('cv');const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4*97){if(d[i]>0)n++;}return n>200})()")
            if shots:
                page.screenshot(path=str(shots / f"cross_browser_{name}_edge_journey.png"))
            page.click("#m-ev")
            page.wait_for_selector("#v-evmap .evmatrix", timeout=20000)
            r["evaluation_overlay_opens"] = "EVALUATION OUTPUT" in page.inner_text("#banner")
            page.click("#m-sci")
            page.wait_for_timeout(800)
            r["scinlp_mode_works"] = "Document" in page.inner_text("#tabs")
            r["no_page_errors"] = not errors
            r["page_errors"] = errors[:3]
            b.close()
        except Exception as e:  # noqa: BLE001
            r["EXCEPTION"] = f"{type(e).__name__}: {str(e)[:300]}"
        res[name] = r
print(json.dumps(res, indent=1))
Path(sys.argv[2]).write_text(json.dumps(res, indent=1))
