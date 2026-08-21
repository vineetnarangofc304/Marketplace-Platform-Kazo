"""Iteration 34 visual check: page-5 overflow + CTA/footer/stat-grid overlap geometry."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

SRC = Path("/app/marketing_assets/brochure.html").resolve()
OUT = Path("/app/test_reports/ui_iteration_34")
OUT.mkdir(parents=True, exist_ok=True)


def overlaps(a, b):
    return not (a["bottom"] <= b["top"] + 1 or b["bottom"] <= a["top"] + 1)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={"width": 1240, "height": 1754})
        await page.goto(f"file://{SRC}", wait_until="networkidle")
        pages = page.locator(".page")
        n = await pages.count()
        print("page elements:", n)

        overflow = await page.evaluate(
            """() => Array.from(document.querySelectorAll('.page')).map((el, i) => ({
                i: i+1, sh: el.scrollHeight, ch: el.clientHeight, diff: el.scrollHeight - el.clientHeight
            }))"""
        )
        for o in overflow:
            flag = "OVERFLOW" if o["diff"] > 4 else "ok"
            print(f"page {o['i']}: scrollH={o['sh']} clientH={o['ch']} diff={o['diff']} -> {flag}")

        # Page 5 geometry
        geo = await page.evaluate(
            """() => {
                const pg = document.querySelectorAll('.page')[4];
                if (!pg) return null;
                const pr = pg.getBoundingClientRect();
                const grab = (sel) => Array.from(pg.querySelectorAll(sel)).map(el => {
                    const r = el.getBoundingClientRect();
                    return {sel, top: r.top - pr.top, bottom: r.bottom - pr.top,
                            left: r.left - pr.left, right: r.right - pr.left,
                            text: (el.innerText||'').slice(0,60).replace(/\\n/g,' | ')};
                });
                return {
                    page: {h: pr.height, w: pr.width},
                    stats: grab('.stat, .stat-card, .stat-grid, .roi, .roi-grid'),
                    cta: grab('.cta'),
                    footer: grab('.footer'),
                    all_children: Array.from(pg.children).map(el => {
                        const r = el.getBoundingClientRect();
                        return {cls: el.className, tag: el.tagName,
                                top: Math.round(r.top - pr.top), bottom: Math.round(r.bottom - pr.top)};
                    })
                };
            }"""
        )
        print("\n--- page 5 geometry ---")
        print("page box:", geo["page"])
        print("\ndirect children:")
        for c in geo["all_children"]:
            over = "  <-- EXCEEDS PAGE" if c["bottom"] > geo["page"]["h"] + 1 else ""
            print(f"  {c['tag']}.{c['cls']}: top={c['top']} bottom={c['bottom']}{over}")

        for grp in ("stats", "cta", "footer"):
            print(f"\n{grp}:")
            for e in geo[grp]:
                print(f"  {e['sel']} top={e['top']:.1f} bottom={e['bottom']:.1f} :: {e['text']}")

        # overlap checks
        print("\n--- overlap checks (page 5) ---")
        problems = []
        for c in geo["cta"]:
            for f in geo["footer"]:
                if overlaps(c, f):
                    problems.append(f"CTA overlaps FOOTER: cta[{c['top']:.0f}-{c['bottom']:.0f}] footer[{f['top']:.0f}-{f['bottom']:.0f}]")
            for s in geo["stats"]:
                if s["sel"] in (".stat-grid", ".roi-grid") and overlaps(c, s):
                    problems.append(f"CTA overlaps STAT GRID: cta[{c['top']:.0f}-{c['bottom']:.0f}] grid[{s['top']:.0f}-{s['bottom']:.0f}]")
        for s in geo["stats"]:
            for f in geo["footer"]:
                if overlaps(s, f):
                    problems.append(f"{s['sel']} overlaps FOOTER: [{s['top']:.0f}-{s['bottom']:.0f}] vs [{f['top']:.0f}-{f['bottom']:.0f}]")
        for e in geo["stats"] + geo["cta"] + geo["footer"]:
            if e["bottom"] > geo["page"]["h"] + 1:
                problems.append(f"{e['sel']} bottom={e['bottom']:.0f} exceeds page height {geo['page']['h']:.0f}")
        if problems:
            for pr in set(problems):
                print("  FAIL:", pr)
        else:
            print("  PASS: no overlaps, nothing exceeds the A4 box on page 5")

        for i in range(n):
            await pages.nth(i).screenshot(
                path=str(OUT / f"brochure_p{i+1}.jpeg"), quality=45, type="jpeg"
            )
        print("\nscreenshots ->", OUT)
        await b.close()


asyncio.run(main())
