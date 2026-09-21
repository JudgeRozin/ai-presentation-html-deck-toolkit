#!/usr/bin/env python3
"""Verify a deck's baseline health + that the MANDATORY element picker is wired up.

Run this right after building a new deck, and as part of PRE-FLIGHT on any deck
you are about to edit. Exit code 1 if anything required is missing.

Usage
-----
  python3 check_deck.py <deck.html> [--tag PADI-DECK]

Checks
------
  picker   all required DOM ids, the DECK_TAG ref string, P/M/Esc key handlers,
           per-slide badge creation, UI_SEL guard, clipboard + fallback
  slides   <section class="slide"> count == </section> count, section ids listed
  svg      every <svg> parses as XML (catches unclosed tags / stray quotes)
  fonts    every font-size in content >= 12px (footer/chrome exempt)
"""
import argparse
import re
import sys
from xml.dom import minidom

# ids the picker's JS grabs with getElementById — missing one = silent JS crash
REQUIRED_IDS = [
    "pickBar", "pickBtn", "pickMultiBtn", "pickTip", "pickBanner",
    "pickToast", "pickPanel", "pickCount", "pickCopy", "pickClear", "pickExit",
]

# behavioural bits that must survive any refactor of the picker block
REQUIRED_JS = {
    "ref string with deck tag": r"\[\s*'?\s*\+?\s*(?:DECK_TAG|'?[A-Z][A-Z0-9-]{2,})'?\s*\]\s*'?\s*\+?\s*'?\s*slide\s|'\s*\+\s*DECK_TAG\s*\+\s*'",
    "single-pick hotkey P": r"e\.key\s*===\s*'p'\s*\|\|\s*e\.key\s*===\s*'P'",
    "multi-pick hotkey M": r"e\.key\s*===\s*'m'\s*\|\|\s*e\.key\s*===\s*'M'",
    "Esc exits pick": r"e\.key\s*===\s*'Escape'",
    "UI_SEL guard": r"closest\(UI_SEL\)",
    "css path builder": r"function\s+cssPath\s*\(",
    "per-slide badge": r"className\s*=\s*'slide-pick'",
    "clipboard + fallback": r"navigator\.clipboard.*\n?.*fallbackCopy|fallbackCopy",
    "capture-phase click": r"\}\s*,\s*true\s*\)\s*;",
}

FONT_FLOOR = 12.0
# chrome/footer/nav may legitimately sit below the floor
CHROME_HINT = re.compile(r"(footer|chrome|nav-dots|#progress|\.hint|\.kicker)", re.I)


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def check_picker(t: str, tag: str, fails: list, warns: list) -> None:
    print("picker")
    missing = [i for i in REQUIRED_IDS if f'id="{i}"' not in t]
    if missing:
        fails.append(f"missing DOM ids: {', '.join(missing)}")
        print(f"  FAIL  missing ids -> {', '.join(missing)}")
    else:
        print(f"  ok    all {len(REQUIRED_IDS)} DOM ids present")

    for label, pat in REQUIRED_JS.items():
        if re.search(pat, t, re.S):
            print(f"  ok    {label}")
        else:
            fails.append(f"picker JS missing: {label}")
            print(f"  FAIL  {label}")

    if tag and f"'{tag}'" not in t and f'"{tag}"' not in t:
        warns.append(f"DECK_TAG '{tag}' not found — refs will carry a different tag")
        print(f"  warn  DECK_TAG '{tag}' not literal in file")
    else:
        print(f"  ok    DECK_TAG = {tag}")


# <svg …> … </svg>; non-greedy, decks keep one svg per element
SVG_RE = re.compile(r"<svg\b[^>]*>.*?</svg>", re.S)


def check_svg(t: str, fails: list) -> None:
    print("svg")
    svgs = SVG_RE.findall(t)
    bad = []
    for i, s in enumerate(svgs):
        try:
            minidom.parseString(s)
        except Exception as e:
            bad.append((i, str(e).split("\n")[0][:90]))
    if bad:
        for i, e in bad:
            fails.append(f"svg #{i} invalid XML: {e}")
            print(f"  FAIL  svg #{i}: {e}")
    else:
        print(f"  ok    {len(svgs)} svg parsed")


def check_slides(t: str, fails: list) -> None:
    print("slides")
    ids = re.findall(r'<section[^>]*\bid="(slide-[\w-]+)"', t)
    opens = len(re.findall(r"<section\b", t))
    closes = t.count("</section>")
    print(f"  {'ok   ' if opens == closes else 'FAIL '} {len(ids)} slide(s) · <section> {opens} open / {closes} close")
    if opens != closes:
        fails.append(f"<section> unbalanced: {opens} open vs {closes} close")
    if ids:
        nums = [int(re.sub(r"\D", "", i) or 0) for i in ids]
        gaps = [n for n in range(min(nums), max(nums) + 1) if n not in nums]
        note = f" · gaps at {gaps} (fine if slides were deleted)" if gaps else ""
        print(f"  ok    ids: {', '.join(ids)}{note}")
    else:
        fails.append("no <section id=\"slide-N\"> found")


FONT_RE = re.compile(r"font-size\s*[:=]\s*[\"']?([0-9.]+)px", re.I)


def check_fonts(t: str, fails: list) -> None:
    print("fonts")
    small = []
    for m in FONT_RE.finditer(t):
        px = float(m.group(1))
        if px >= FONT_FLOOR:
            continue
        ctx = t[max(0, m.start() - 220):m.start()]
        if CHROME_HINT.search(ctx):
            continue
        small.append(px)
    if small:
        uniq = sorted(set(small))
        fails.append(f"{len(small)} font-size below {FONT_FLOOR}px in content: {uniq}")
        print(f"  FAIL  {len(small)} below floor -> {uniq}")
    else:
        print(f"  ok    no content font below {FONT_FLOOR}px")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--tag", default="PADI-DECK", help="expected DECK_TAG (default PADI-DECK)")
    a = ap.parse_args()

    try:
        t = open(a.deck, encoding="utf-8", errors="replace").read()
    except OSError as e:
        print(f"cannot read {a.deck}: {e}", file=sys.stderr)
        return 2

    fails, warns = [], []
    print(f"deck: {a.deck}  ({len(t):,} bytes)\n")
    check_picker(t, a.tag, fails, warns)
    print()
    check_slides(t, fails)
    print()
    check_svg(t, fails)
    print()
    check_fonts(t, fails)

    print("\n" + "=" * 64)
    for w in warns:
        print(f"WARN  {w}")
    if fails:
        for f in fails:
            print(f"FAIL  {f}")
        print(f"\n{len(fails)} problem(s) — fix before shipping.")
        return 1
    print("PASS  deck baseline + picker wiring all good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
