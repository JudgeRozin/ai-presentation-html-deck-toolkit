#!/usr/bin/env python3
"""fit_check.py - measure a slide deck with TEXT INK boxes, not element boxes.

Why this exists: an element's getBoundingClientRect() says nothing about where the
glyphs actually land. A container can report "overflow" while nothing is clipped
(line-box overshoot), and a container can look perfectly sized while a title's ink
bleeds over the block below it. This tool measures Range.getClientRects() on every
text node, so the numbers describe rendered ink.

Per slide it reports:
  ink            number of ink boxes measured
  bottom/slack   lowest ink pixel and room left before the canvas bottom edge
  OVERFLOW       ink bleeds past its own container's padding box by > 1px (real)
  line-overshoot scrollHeight > clientHeight but ink stays inside (benign, reported)
  OUTSIDE        ink outside the slide canvas (clipped / spilling)
  COLLIDE        ink boxes of two different elements intersecting > 4px^2

Run:
    python3 tools/fit_check.py deck.html
    python3 tools/fit_check.py deck.html --ignore 'h1.cover-title x em'
    PLAYWRIGHT_CHROME=/path/to/chrome python3 tools/fit_check.py deck.html

--ignore takes '<element> x <element>' pairs whose overlap is intentional (for
example a heading and the <em> inside it that deliberately share a box).

Needs: pip install playwright && playwright install chromium
Exit 1 if any slide has an unignored problem.
"""
import argparse
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

DEFAULT_CHROME = (
    pathlib.Path.home() / "Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/"
    "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
)
CHROME = pathlib.Path(os.environ.get("PLAYWRIGHT_CHROME") or DEFAULT_CHROME)

MEASURE = r"""
(slideIdx) => {
  const slides = Array.from(document.querySelectorAll('.slide'));
  slides.forEach((s, n) => s.classList.toggle('active', n === slideIdx));
  const deck = document.getElementById('deck');
  deck.style.transform = 'none';
  ['nav', 'hint', 'pickBar', 'progress', 'pickPanel', 'pickTip', 'pickBanner', 'pickToast', 'dots']
    .forEach(id => { const e = document.getElementById(id); if (e) e.style.display = 'none'; });
  document.querySelectorAll('.slide-pick').forEach(b => b.style.display = 'none');

  const slide = slides[slideIdx];
  const canvas = slide.querySelector('.canvas');
  const cRect = canvas.getBoundingClientRect();

  const label = el => el.tagName.toLowerCase() +
    (el.className && typeof el.className === 'string' && el.className.trim()
      ? '.' + el.className.trim().split(/\s+/).join('.') : '');

  // ---- ink boxes: every rendered text node -----------------------------------
  // block = nearest block container, so "same heading / same list item" pairs can
  // be recognised (their lines legitimately share vertical space).
  const blockIds = new Map();
  const blockId = el => { if (!el) return 0; if (!blockIds.has(el)) blockIds.set(el, blockIds.size + 1); return blockIds.get(el); };
  const BLOCK_SEL = 'h1,h2,h3,h4,p,li,td,th,pre';
  const inks = [];
  const walker = document.createTreeWalker(slide, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.textContent.trim()) continue;
    const el = node.parentElement;
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const r of range.getClientRects()) {
      if (r.width < 1 || r.height < 1) continue;
      inks.push({
        t: node.textContent.trim().replace(/\s+/g, ' ').slice(0, 34),
        el: label(el),
        block: blockId(el.closest(BLOCK_SEL)),
        x: +r.left.toFixed(1), y: +r.top.toFixed(1),
        x2: +r.right.toFixed(1), y2: +r.bottom.toFixed(1)
      });
    }
  }

  // ---- containers reporting scroll overflow: real bleed or benign overshoot? --
  const overflow = [], benign = [];
  slide.querySelectorAll('*').forEach(el => {
    if (el.scrollHeight <= el.clientHeight + 1 && el.scrollWidth <= el.clientWidth + 1) return;
    const box = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const innerBottom = box.bottom - (parseFloat(cs.borderBottomWidth) || 0) - (parseFloat(cs.paddingBottom) || 0);
    const innerRight  = box.right  - (parseFloat(cs.borderRightWidth)  || 0) - (parseFloat(cs.paddingRight)  || 0);
    let maxB = -Infinity, maxR = -Infinity;
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) {
      if (!n.textContent.trim()) continue;
      const rng = document.createRange();
      rng.selectNodeContents(n);
      for (const q of rng.getClientRects()) {
        maxB = Math.max(maxB, q.bottom);
        maxR = Math.max(maxR, q.right);
      }
    }
    const rec = { el: label(el), clientH: el.clientHeight, scrollH: el.scrollHeight,
                  bleedY: +(maxB - innerBottom).toFixed(1), bleedX: +(maxR - innerRight).toFixed(1) };
    if (rec.bleedY > 1 || rec.bleedX > 1) overflow.push(rec);
    else benign.push(rec);
  });

  // ---- ink outside the canvas ------------------------------------------------
  const outside = inks.filter(r => r.x < cRect.left - 0.5 || r.x2 > cRect.right + 0.5 ||
                                   r.y < cRect.top - 0.5  || r.y2 > cRect.bottom + 0.5)
                      .map(r => ({ t: r.t, el: r.el, x: r.x, x2: r.x2, y: r.y, y2: r.y2 }));

  // ---- real ink-on-ink collisions -------------------------------------------
  // Two facts about text ink make a naive rect intersection lie:
  //  1. adjacent lines of ONE heading overlap by a few px, because the font's ink
  //     height (ascent+descent) exceeds the line-height the author set;
  //  2. an inline <em>/<b> always overlaps the line it sits on.
  // So: same block container -> not a collision, and require an overlap worth at
  // least 30% of the smaller box before calling it one.
  const collide = [];
  for (let i = 0; i < inks.length; i++) {
    for (let j = i + 1; j < inks.length; j++) {
      const a = inks[i], b = inks[j];
      if (a.el === b.el) continue;
      const ox = Math.min(a.x2, b.x2) - Math.max(a.x, b.x);
      const oy = Math.min(a.y2, b.y2) - Math.max(a.y, b.y);
      if (ox <= 1 || oy <= 1) continue;
      const area = ox * oy;
      const smaller = Math.min((a.x2 - a.x) * (a.y2 - a.y), (b.x2 - b.x) * (b.y2 - b.y));
      if (area <= 4 || area < smaller * 0.30) continue;   // grazing / line-box noise
      if (a.block === b.block && a.block) continue;        // same heading or list item
      collide.push({ a, b, area: +area.toFixed(1) });
    }
  }

  const maxBottom = inks.reduce((m, r) => Math.max(m, r.y2), cRect.top);
  return {
    slide: slide.id,
    canvas: { x: +cRect.left.toFixed(1), y: +cRect.top.toFixed(1),
              w: +cRect.width.toFixed(1), h: +cRect.height.toFixed(1) },
    inkCount: inks.length,
    maxBottom: +maxBottom.toFixed(1),
    slack: +(cRect.bottom - maxBottom).toFixed(1),
    overflow, benign, outside, collide, collideCount: collide.length
  };
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", nargs="?", default="deck.html")
    ap.add_argument("--ignore", action="append", default=[],
                    help="intentional overlap, e.g. 'h1.cover-title x em'")
    ap.add_argument("--quiet-benign", action="store_true",
                    help="do not list benign line-box overshoots")
    a = ap.parse_args()

    if not CHROME.exists():
        sys.exit("ERROR: Chromium not found at %s\n"
                 "       set PLAYWRIGHT_CHROME or run: playwright install chromium" % CHROME)

    url = "file://" + str(pathlib.Path(a.deck).resolve())
    fails = 0

    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROME))
        pg = b.new_page(viewport={"width": 1500, "height": 900})
        pg.goto(url)
        pg.evaluate("() => document.fonts.ready")
        fonts = pg.evaluate(
            "() => [document.fonts.status,"
            " document.fonts.check(\"700 33px 'Sora'\"),"
            " document.fonts.check(\"400 15px 'Inter'\"),"
            " document.fonts.check(\"400 12.5px 'JetBrains Mono'\")]"
        )
        print("deck   : %s" % a.deck)
        print("fonts  : status=%s sora=%s inter=%s mono=%s" % tuple(fonts))
        if not all(fonts[1:]):
            print("WARN   : a webfont did not load -> width measurements are unreliable")
        print()

        n = pg.evaluate("() => document.querySelectorAll('.slide').length")
        for i in range(n):
            r = pg.evaluate(MEASURE, i)
            real = [c for c in r["collide"]
                    if ("%s x %s" % (c["a"]["el"], c["b"]["el"])) not in a.ignore
                    and ("%s x %s" % (c["b"]["el"], c["a"]["el"])) not in a.ignore]
            bad = []
            if r["overflow"]:
                bad.append("OVERFLOW %d" % len(r["overflow"]))
            if r["outside"]:
                bad.append("OUTSIDE-CANVAS %d" % len(r["outside"]))
            if real:
                bad.append("INK-COLLIDE %d" % len(real))
            if r["slack"] < 0:
                bad.append("SPILLS-PAST-CANVAS")
            print("%-9s ink=%-4d bottom=%-7.1f slack=%-7.1f %s"
                  % (r["slide"], r["inkCount"], r["maxBottom"], r["slack"],
                     ("FAIL " + ", ".join(bad)) if bad else "ok"))
            for o in r["overflow"][:5]:
                print("        OVERFLOW %-24s ink bleeds y=%+.1f x=%+.1f px past its box "
                      "(clientH=%s scrollH=%s)" % (o["el"], o["bleedY"], o["bleedX"], o["clientH"], o["scrollH"]))
            for o in r["outside"][:5]:
                print("        OUTSIDE  %-24s \"%s\" x=%.0f..%.0f y=%.0f..%.0f"
                      % (o["el"], o["t"], o["x"], o["x2"], o["y"], o["y2"]))
            for c in real[:5]:
                print("        COLLIDE  %-22s(\"%s\") x %-22s(\"%s\") area=%.0f"
                      % (c["a"]["el"], c["a"]["t"], c["b"]["el"], c["b"]["t"], c["area"]))
            if r["benign"] and not a.quiet_benign:
                print("        (benign: %d container(s) scroll-overflow without ink bleed: %s)"
                      % (len(r["benign"]), ", ".join(sorted({o["el"] for o in r["benign"]})[:3])))
            if bad:
                fails += 1

        b.close()

    print()
    print("=> %s" % ("LAYOUT OK" if not fails else "LAYOUT PROBLEMS in %d slide(s)" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
