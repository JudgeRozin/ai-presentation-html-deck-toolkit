#!/usr/bin/env python3
"""check_features.py - drive the deck in a real browser and assert the three
features behave, not merely that their code is present.

check_deck.py proves the picker is WIRED (ids, handlers, guards present in the
source). This script proves it WORKS: it presses the keys, clicks real elements
and inspects what the deck produced.

Covered:
  element picker   P toggles pick mode, hovering marks, clicking copies a ref
                   with slide number + css path, and leaves pick mode
  guards           P is ignored while typing in an input, and Cmd/Ctrl+P is left
                   to the browser; the picker's own chrome is never pickable
  multi-picker     M shows the panel and the per-slide badges, clicks accumulate,
                   a badge selects a whole section, Copy refs emits a DOM-ordered
                   batch with a count header, Clear empties it, Esc exits
  PDF export       the button calls window.print(), the section dropdown marks
                   .print-keep/.print-last correctly and cleans up on afterprint

The copied payload is captured by stubbing navigator.clipboard.writeText, so the
assertions are deterministic; a real OS-clipboard read is attempted afterwards
and reported as a warning if the headless environment refuses it.

Run:  python3 tools/check_features.py deck.html
Needs: pip install playwright && playwright install chromium
Exit 1 if any assertion fails.
"""
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

DEFAULT_CHROME = (
    pathlib.Path.home() / "Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/"
    "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
)
CHROME = pathlib.Path(os.environ.get("PLAYWRIGHT_CHROME") or DEFAULT_CHROME)

# installed before the deck's own scripts run
INIT = """
window.__copied = [];
window.__printed = 0;
window.__printStub = true;
window.print = () => { window.__printed++; };
try {
  Object.defineProperty(navigator.clipboard, 'writeText', {
    configurable: true,
    value: t => { window.__copied.push(t); return Promise.resolve(); }
  });
} catch (e) { /* leave the real clipboard in place */ }
"""

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print("  %-6s %s%s" % ("PASS" if ok else "FAIL", name, (" — " + detail) if detail and not ok else ""))


def main():
    deck = sys.argv[1] if len(sys.argv) > 1 else "deck.html"
    if not CHROME.exists():
        sys.exit("ERROR: Chromium not found at %s\n"
                 "       set PLAYWRIGHT_CHROME or run: playwright install chromium" % CHROME)

    url = "file://" + str(pathlib.Path(deck).resolve())

    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROME))
        ctx = b.new_context(viewport={"width": 1500, "height": 900})
        try:
            ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        except Exception as e:
            print("note: clipboard permission not grantable here (%s)" % e)
        pg = ctx.new_page()
        pg.add_init_script(INIT)
        pg.goto(url)
        pg.wait_for_timeout(400)
        pg.evaluate("() => document.fonts.ready")

        copied = lambda: pg.evaluate("() => window.__copied")
        clear_copied = lambda: pg.evaluate("() => { window.__copied.length = 0; }")

        print("baseline")
        check("6 slides present", pg.evaluate("() => document.querySelectorAll('.slide').length") == 6)
        check("slide 1 active",
              pg.evaluate("() => document.querySelector('.slide.active').id") == "slide-1")
        check("picker bar visible", pg.is_visible("#pickBar"))
        check("multi panel hidden at rest", not pg.is_visible("#pickPanel"))

        # ---------------- element picker ------------------------------------
        print("element picker")
        pg.keyboard.press("p")
        check("P enters pick mode", pg.evaluate("() => document.body.classList.contains('pick-mode')"))
        check("banner visible in pick mode", pg.is_visible("#pickBanner"))

        clear_copied()
        pg.click(".chips span")            # a real content element on slide 1
        pg.wait_for_timeout(150)
        refs = copied()
        ref = refs[0] if refs else ""
        check("click copies exactly one reference", len(refs) == 1, "got %d" % len(refs))
        check("reference carries the deck tag", ref.startswith("[DECK-KIT] slide 1"), ref[:60])
        check("reference carries a resolvable css path",
              ref.split("css: ")[-1].startswith("section#slide-1"), ref[:140])
        check("reference carries a text snippet", 'text: "' in ref, ref[:120])
        check("pick mode exits after copying",
              not pg.evaluate("() => document.body.classList.contains('pick-mode')"))

        # picker chrome must not be pickable
        pg.keyboard.press("p")
        clear_copied()
        pg.click("#hint")
        pg.wait_for_timeout(120)
        check("picker chrome is not pickable (UI_SEL guard)", len(copied()) == 0)
        check("clicking chrome does not exit pick mode",
              pg.evaluate("() => document.body.classList.contains('pick-mode')"))
        pg.keyboard.press("Escape")
        check("Esc leaves pick mode",
              not pg.evaluate("() => document.body.classList.contains('pick-mode')"))

        # typing guard: inject a real input, focus it, press P
        pg.evaluate("""() => {
          const i = document.createElement('input'); i.id = '__probe';
          document.body.appendChild(i); i.focus();
        }""")
        pg.keyboard.press("p")
        check("P is ignored while typing in an input",
              not pg.evaluate("() => document.body.classList.contains('pick-mode')"))
        pg.evaluate("() => document.getElementById('__probe').remove()")
        pg.evaluate("() => document.body.focus()")

        # Cmd/Ctrl+P belongs to the browser
        pg.keyboard.down("Control")
        pg.keyboard.press("p")
        pg.keyboard.up("Control")
        check("Ctrl+P is not hijacked",
              not pg.evaluate("() => document.body.classList.contains('pick-mode')"))

        # ---------------- multi-picker --------------------------------------
        print("multi-picker")
        pg.keyboard.press("m")
        check("M enters multi-pick", pg.is_visible("#pickPanel"))
        check("one section badge per slide",
              pg.evaluate("() => document.querySelectorAll('.slide-pick').length") == 6)
        check("badges are shown in multi-pick",
              pg.evaluate("() => [...document.querySelectorAll('.slide-pick')]"
                          ".every(b => getComputedStyle(b).display !== 'none')"))

        pg.keyboard.press("ArrowRight")     # slide 2
        pg.click("#slide-2 .quote")
        pg.click("#slide-2 .ul li")
        pg.wait_for_timeout(120)
        check("clicks accumulate (2 selected)",
              pg.inner_text("#pickCount").strip().startswith("2"), pg.inner_text("#pickCount"))

        # a badge on the ACTIVE slide (badges live on every slide but only the
        # active one is visible, so clicking a hidden one is not a user action)
        pg.keyboard.press("ArrowRight")     # slide 3
        pg.click("#slide-3 .slide-pick")
        pg.wait_for_timeout(120)
        check("section badge adds a selection (3 selected)",
              pg.inner_text("#pickCount").strip().startswith("3"), pg.inner_text("#pickCount"))
        # badge toggles off again
        pg.click("#slide-3 .slide-pick")
        pg.wait_for_timeout(120)
        check("section badge toggles off (2 selected)",
              pg.inner_text("#pickCount").strip().startswith("2"), pg.inner_text("#pickCount"))
        pg.click("#slide-3 .slide-pick")
        pg.wait_for_timeout(120)

        clear_copied()
        pg.click("#pickCopy")
        pg.wait_for_timeout(150)
        batch = copied()[0] if copied() else ""
        lines = batch.splitlines()
        check("batch header states the count", lines and lines[0] == "# DECK-KIT multi-selection (3 refs)", lines[:1])
        check("batch has 3 references", len(lines) == 4, "lines=%d" % len(lines))
        check("whole-section ref points at the slide id", any("SELURUH SECTION" in l and "css: #slide-3" in l for l in lines))
        check("batch is in DOM order, not click order",
              [l.split(" slide ")[1].split()[0] for l in lines[1:]] == ["2", "2", "3"],
              str([l[:34] for l in lines[1:]]))

        pg.click("#pickClear")
        pg.wait_for_timeout(120)
        check("Clear empties the selection",
              pg.inner_text("#pickCount").strip().startswith("0"), pg.inner_text("#pickCount"))

        pg.keyboard.press("Escape")
        pg.wait_for_timeout(120)
        check("Esc exits multi-pick", not pg.is_visible("#pickPanel"))
        check("badges hidden again",
              pg.evaluate("() => [...document.querySelectorAll('.slide-pick')]"
                          ".every(b => getComputedStyle(b).display === 'none')"))

        # ---------------- PDF export ----------------------------------------
        print("PDF export")
        pg.evaluate("() => { window.__printed = 0; }")
        pg.click("#pdfBtn")
        pg.wait_for_timeout(400)
        check("PDF button calls window.print()", pg.evaluate("() => window.__printed") == 1,
              "calls=%s" % pg.evaluate("() => window.__printed"))
        check("PDF toast is shown", pg.is_visible("#pdfToast"))

        # PARTS[1] is "Fitur picker (3-4)"; the option value is the PARTS index,
        # so select by value (the first <option> is the empty placeholder)
        pg.select_option("#partDl", value="1")
        pg.wait_for_timeout(450)
        check("subset mode marks the body",
              pg.evaluate("() => document.body.classList.contains('print-subset')"))
        check("only slides 3-4 are kept",
              pg.evaluate("() => [...document.querySelectorAll('.slide')]"
                          ".filter(s => s.classList.contains('print-keep')).map(s => s.id)"
                          ".join(',')") == "slide-3,slide-4",
              pg.evaluate("() => [...document.querySelectorAll('.slide.print-keep')].map(s=>s.id).join(',')"))
        check("last kept slide is marked .print-last",
              pg.evaluate("() => document.getElementById('slide-4').classList.contains('print-last')"))
        check("subset triggers window.print()", pg.evaluate("() => window.__printed") >= 2,
              "calls=%s" % pg.evaluate("() => window.__printed"))

        pg.evaluate("() => window.dispatchEvent(new Event('afterprint'))")
        pg.wait_for_timeout(150)
        check("afterprint cleans the subset state",
              pg.evaluate("() => !document.body.classList.contains('print-subset')"
                          " && !document.querySelector('.slide.print-keep, .slide.print-last')"))

        # real clipboard, best effort (headless file:// often refuses)
        print("real clipboard (best effort)")
        try:
            pg.keyboard.press("Home")          # back to slide 1 where the chip lives
            pg.wait_for_timeout(150)
            pg.keyboard.press("p")
            pg.click(".chips span", timeout=3000)
            pg.wait_for_timeout(250)
            os_clip = pg.evaluate("() => navigator.clipboard.readText()")
            ok = isinstance(os_clip, str) and os_clip.startswith("[DECK-KIT]")
            print("  %-6s OS clipboard round-trip%s"
                  % ("PASS" if ok else "warn", "" if ok else " (refused in this environment; stub capture above is authoritative)"))
        except Exception as e:
            print("  warn   OS clipboard round-trip unavailable (%s)" % str(e).splitlines()[0][:80])

        b.close()

    failed = [n for n, ok, _ in results if not ok]
    print()
    print("%d checks, %d failed" % (len(results), len(failed)))
    if failed:
        for n in failed:
            print("  FAIL  %s" % n)
        return 1
    print("=> ALL FEATURE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
