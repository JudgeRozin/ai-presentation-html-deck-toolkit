# PDF export from an HTML deck — 1 slide = 1 page, clean

The whole feature is a `@media print` block plus a button that calls `window.print()`. No PDF library,
no headless renderer, no generator: an existing deck gets print rules and the browser produces the
file. Verified in a real project with 10 slides on a 1280×720 canvas scaled to 0.94.

## The recipe

```css
@media print{
  @page{size:1280px 720px;margin:0}                 /* px, not A4: exact 16:9, no white bars */
  html,body{background:#fff;overflow:visible!important;height:auto;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  #stage{position:static;display:block;inset:auto}   /* un-fix the scaling wrapper */
  #deck{width:1280px;height:auto;transform:none!important;box-shadow:none}

  /* fixed page box per slide: without it, flex children shrink and text spills out */
  .slide{position:relative;inset:auto;width:1280px!important;height:720px!important;
    opacity:1!important;visibility:visible!important;transform:none!important;
    page-break-after:always;break-after:page;
    page-break-inside:avoid;break-inside:avoid}
  .slide:last-child,.slide.print-last{page-break-after:auto;break-after:auto}

  /* large type: pin absolute line-height in px (see pitfall 2) */
  .cover-title{font-size:52px!important;line-height:62px!important}

  /* deck chrome must never print */
  #nav,#progress,#hint,#pickBar,#pickPanel,#pickToast,#pdfToast,button{display:none!important}
}

/* subset export: only the marked slides print */
body.print-subset .slide{display:none!important}
body.print-subset .slide.print-keep{display:block!important}
body.print-subset .slide.print-keep.print-last{page-break-after:auto!important;break-after:auto!important}
```

`print-color-adjust:exact` is what makes dark backgrounds survive without the user having to tick
"Background graphics" in the print dialog — the difference between a designed deck and a white PDF
with pale text.

### Subset export ("Export a section…")

```js
document.body.classList.add('print-subset');
slides.forEach((s, i) => {
  s.classList.toggle('print-keep', i + 1 >= part.from && i + 1 <= part.to);
  s.classList.toggle('print-last', i + 1 === part.to);      // NOT :last-of-type
});
window.addEventListener('afterprint', clean);
setTimeout(() => window.print(), 150);
setTimeout(clean, 60000);                                 // failsafe: never get stuck
```

## Pitfalls that actually bite

1. **`#deck{height:auto}` collapses layout.** Slides laid out with flex shrink their cards and text
   overflows outside them. Keep `width`/`height` on `.slide` **rigid** with `!important`; never let
   the height follow content inside a print block.
2. **Chrome's print engine uses font metrics (ascent+descent), not `font-size × line-height`.**
   A 50px heading ballooned to 97pt (129px) of ink, so three title lines overlapped the block below.
   Measured here: a 52px Sora title has an ink height of **71.6px** per line with `line-height:60.32px`
   — adjacent lines of the *same* heading overlap by ~11px, which is expected and harmless. Fix big
   type by pinning `line-height` in **absolute px** inside the print block.
3. **Chrome CLI ≠ CDP `Page.printToPDF`.** `--print-to-pdf` and the browser's own print menu work
   perfectly; the CDP path with a non-standard `@page{size:…px}` sometimes returns a single page even
   though `getComputedStyle` in the browser is correct. Check with the CLI before "fixing" a deck that
   is already right.
4. **Do not rely on `:last-of-type` for the last slide of a subset.** In a subset the last printed
   slide is not the last in the document, so mark it explicitly (`.print-last`) and clean the class up
   on `afterprint`.
5. **`window.print()` blocks, and `afterprint` may not fire in every context.** Arm a timeout so the
   subset classes cannot be left behind and the next export does not silently print the wrong thing.

## Reference numbers

| Property | Correct value |
|---|---|
| `pdfinfo` page size | `960 x 540 pts` = 1280×720 px (16:9) |
| `pdftoppm -r 96` output | exactly 1280×720 px |
| `#deck` height in print mode | `720 × number of slides` px (10 slides → 7200) |
| Words per page | rises after the fix (one page went 97 → 160) |

## Verification — what to check

The failure mode that matters is not a wrong page count: it is text missing or overlapping *inside* a
page whose count is right. Two commands catch most of it:

```bash
pdfinfo out.pdf | grep -E 'Pages|Page size'   # Pages = slide count · Page size must be 960 x 540 pts
pdftoppm -png -r 96 out.pdf pg                # each page must come out exactly 1280x720 px
pdftotext -bbox out.pdf -                     # per-word boxes: anything outside 0,0..960,540 is a bug
```

Then look at the PDF yourself: no nav, hint or picker chrome printed, no blank trailing page, dark
backgrounds intact, and large headings not overlapping the block beneath them.

One limitation worth stating instead of hiding: the per-word boxes from `pdftotext -bbox` are font
**metric** boxes (~2.6em tall), so "boxes overlap vertically" noise is usually multi-column layout or
line boxes rather than real collisions. Treat words **outside the page** and words colliding **on the
same line** as hard failures, and review vertical stacking by hand. For an ink-level check of the deck
itself, measure rendered text boxes in the browser with `Range.getClientRects()` — element bounding
boxes can be 2–27px larger than the ink and produce false positives.

## A decision to put to the user, not make yourself

**Page size.** The default `@page{size:1280px 720px}` gives a full 16:9 page with no white margins.
A4 landscape is only right when the user wants to *physically print* the deck — at the cost of some
white space on the sides. Present the trade-off instead of choosing for them.
