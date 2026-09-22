---
name: implement-slide-tools
description: Use when an HTML slide deck needs an element picker, a multi-picker, or PDF export (1 slide = 1 page) — building a new deck or adding the features to an existing one. Trigger on "/implement-slide-tools".
---

# Implement slide tools in an HTML deck

Three features, one HTML file, no dependencies, no build step, no libraries:

| Feature | Trigger | What it does |
|---|---|---|
| Element picker | <kbd>P</kbd> | Hover + click an element → copies a precise reference string |
| Multi-picker | <kbd>M</kbd> | Select many elements, or a whole slide → copies one batch |
| PDF export | nav button | `window.print()` → 1 slide = 1 page, 1280×720, backgrounds intact |

A working deck with all three installed is in `deck.html`. This document is the
implementation guide: read it, then paste the three blocks below into the target deck.

## When to use this

- The user asks for a new HTML deck / presentation ("bikin deck", "slide HTML", "presentasi").
- The user has an existing HTML deck and wants the picker or the PDF export added.
- The user pastes a `[DECK-TAG] slide N · …` reference — that is the picker's output, and the
  agent-side contract at the end of this file explains what to do with it.

## Why the picker is not optional

The user reviews a rendered deck with their eyes and corrects it by pointing at things. Without a
picker, every correction is a guess at a DOM path — *"the blue box, bottom right"* — and a wrong
guess costs a full render-and-review round. The picker turns a vague instruction into a reference
that a script can resolve exactly. Install it **before** handing a deck over, not after the first
misunderstanding.

## Step 0 — inspect the deck first

Do not paste blind. Read the deck's HTML and establish three facts:

| Fact | Why it matters | This toolkit's assumption |
|---|---|---|
| Slide container | Bounds the readable path and yields the slide number | `<section class="slide" id="slide-N">` |
| Canvas element | Where the readable path stops | `.canvas` |
| Deck chrome | What must never be pickable | `#nav`, `.nav-dots`, `#hint`, `#progress`, buttons |

Two structural traps:

- **Slide ids must be `slide-N`.** The picker derives the slide number with
  `slide.id.replace('slide-','')`. If the deck uses `id="s1"`, adapt that line to
  `id.replace(/^s/,'')` — or rename the ids, which is usually cleaner.
- **`.slide` and `.canvas` may not exist.** If the deck uses other names, change the two references
  in the picker JS (`el.closest('.slide')`, `cur.classList.contains('canvas')`). If there is no
  canvas wrapper at all, point it at the slide container itself.

## Step 1 — CSS: paste inside the deck's last `<style>`

```css
/* ============================================================================
   ELEMENT PICKER / MULTI-PICKER (CSS)
   ========================================================================== */
#pickBar{position:fixed;left:14px;bottom:12px;display:flex;align-items:center;gap:8px;z-index:9996}
#pickBtn,#pickMultiBtn{position:static;border-radius:999px;padding:7px 14px;
  font-family:inherit;font-size:12px;font-weight:600;cursor:pointer;backdrop-filter:blur(6px)}
#pickBtn{background:rgba(3,6,15,.85);color:#22D3EE;border:1px solid rgba(34,211,238,.45)}
#pickBtn:hover{background:rgba(34,211,238,.15)}
#pickMultiBtn{background:rgba(3,6,15,.85);color:#FFC000;border:1px solid rgba(255,192,0,.45)}
#pickMultiBtn:hover{background:rgba(255,192,0,.15)}
body.pick-mode,body.pick-mode *{cursor:crosshair !important}
.pick-hover{outline:2px solid #22D3EE !important;outline-offset:-2px !important}
.pick-selected{outline:2.5px solid #FFC000 !important;outline-offset:-2px !important}
.pick-sel{outline:2.5px solid #FFC000 !important;outline-offset:-2px !important;
  box-shadow:0 0 0 4px rgba(255,192,0,.16) !important}
#pickTip{position:fixed;z-index:9997;display:none;pointer-events:none;max-width:360px;
  background:rgba(3,6,15,.94);border:1px solid rgba(34,211,238,.45);color:#F4F7FF;
  font-family:inherit;font-size:12px;line-height:1.45;padding:7px 10px;border-radius:9px;
  box-shadow:0 8px 24px rgba(0,0,0,.5);word-break:break-all}
#pickBanner{position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:9997;display:none;
  background:rgba(34,211,238,.12);border:1px solid rgba(34,211,238,.5);color:#22D3EE;
  font-size:12px;font-weight:700;padding:8px 16px;border-radius:999px;letter-spacing:.04em}
#pickToast{position:fixed;bottom:52px;left:50%;transform:translateX(-50%);z-index:9997;display:none;
  max-width:70vw;background:rgba(255,192,0,.12);border:1px solid rgba(255,192,0,.5);color:#FFC000;
  font-size:12px;font-weight:600;line-height:1.5;padding:10px 16px;border-radius:10px;
  word-break:break-all}
#pickPanel{position:fixed;top:56px;left:50%;transform:translateX(-50%);z-index:9998;display:none;
  align-items:center;gap:10px;background:rgba(3,6,15,.95);border:1px solid rgba(255,192,0,.5);
  color:#FFC000;font-size:12px;font-weight:700;padding:8px 12px;border-radius:12px;
  box-shadow:0 10px 30px rgba(0,0,0,.5);white-space:nowrap}
#pickPanel button{background:rgba(255,192,0,.14);border:1px solid rgba(255,192,0,.5);color:#FFC000;
  border-radius:999px;padding:5px 12px;font-size:12px;font-weight:700;cursor:pointer}
#pickPanel button:hover{background:rgba(255,192,0,.32)}
#pickPanel .danger{color:#F4F7FF;border-color:rgba(255,255,255,.3);background:rgba(255,255,255,.08)}
.slide-pick{position:absolute;top:14px;right:14px;z-index:9990;display:none;width:28px;height:28px;
  border-radius:50%;background:rgba(3,6,15,.85);color:#FFC000;border:1px solid rgba(255,192,0,.5);
  font-size:16px;font-weight:800;line-height:1;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.35)}
.slide-pick.on{background:rgba(255,192,0,.95);color:#0B1A45}
```

Two requirements on the deck side: the slide container needs `position:relative` (the per-slide
badge is absolutely positioned inside it), and the badge is created in JS so it follows slides
being added or removed.

## Step 2 — DOM: paste immediately after `<body>`

```html
<div id="pickBar">
  <button id="pickBtn" title="Element Picker (P)">🎯 Pick element</button>
  <button id="pickMultiBtn" title="Multi-picker (M)">🔲 Multi-pick</button>
</div>
<div id="pickBanner">PICK MODE — klik elemen untuk copy referensi · Esc keluar</div>
<div id="pickTip"></div>
<div id="pickToast"></div>
<div id="pickPanel">
  <span id="pickCount">0 dipilih</span>
  <button id="pickCopy">Copy refs</button>
  <button id="pickClear" class="danger">Clear</button>
  <button id="pickExit" class="danger">Exit</button>
</div>
```

All eleven ids are required — the JS grabs each with `getElementById`, and a missing one is a silent
crash (the picker simply does nothing, with no console error on some browsers).

## Step 3 — JS: paste as the LAST script block in the document

```js
/* ===== element picker + multi-picker =====
   [ADAPT] DECK_TAG : uppercase deck name, e.g. 'Q3-REVIEW'. Prefixes every reference.
   [ADAPT] UI_SEL   : add every piece of this deck's chrome that must not be pickable.  */
const DECK_TAG = 'DECK';
const pickBtn = document.getElementById('pickBtn');
const pickMultiBtn = document.getElementById('pickMultiBtn');
const pickTip = document.getElementById('pickTip');
const pickBanner = document.getElementById('pickBanner');
const pickToast = document.getElementById('pickToast');
const pickPanel = document.getElementById('pickPanel');
const pickCount = document.getElementById('pickCount');
const pickCopy = document.getElementById('pickCopy');
const pickClear = document.getElementById('pickClear');
const pickExit = document.getElementById('pickExit');

const UI_SEL = '#pickBar,#pickBtn,#pickMultiBtn,#pickTip,#pickBanner,#pickToast,#pickPanel,.slide-pick';
// [ADAPT] add the deck's own chrome, e.g. '#nav,#progress,#hint,.nav-dots'

let pickMode = false, pickHover = null, multiMode = false;
const sel = new Set();         // individually picked elements
const selSlides = new Set();   // whole slides picked via the ⊕ badge

function elDesc(el){
  const slide = el.closest('.slide');                       // [ADAPT] slide container
  const slideNo = slide ? slide.id.replace('slide-','') : '?';   // [ADAPT] id pattern
  const parts = []; let cur = el, depth = 0;
  while (cur && !cur.classList.contains('canvas') && depth < 4){  // [ADAPT] canvas class
    let s = cur.tagName.toLowerCase();
    if (cur.id && !cur.id.startsWith('slide')) s += '#' + cur.id;
    else if (cur.className && typeof cur.className === 'string'){
      const cs = cur.className.trim().split(/\s+/)
        .filter(c => c !== 'pick-hover' && c !== 'pick-selected' && c !== 'pick-sel')
        .slice(0,2).join('.');
      if (cs) s += '.' + cs;
    }
    parts.unshift(s); cur = cur.parentElement; depth++;
  }
  const txt = (el.innerText || '').trim().replace(/\s+/g,' ').slice(0,90);
  const r = el.getBoundingClientRect();
  return { slideNo, path: parts.join(' > '), txt, size: Math.round(r.width)+'x'+Math.round(r.height) };
}

function cssPath(el){
  const path = []; let cur = el;
  while (cur && cur.nodeType === Node.ELEMENT_NODE && path.length < 6){
    let s = cur.nodeName.toLowerCase();
    if (cur.id){ s += '#' + cur.id; path.unshift(s); break; }
    const cls = (cur.className && typeof cur.className === 'string')
      ? cur.className.trim().split(/\s+/).filter(Boolean)
          .filter(c => c !== 'pick-hover' && c !== 'pick-selected' && c !== 'pick-sel')
      : [];
    if (cls.length) s += '.' + cls[0];
    let sib = cur, nth = 1;
    while ((sib = sib.previousElementSibling)) { if (sib.nodeName === cur.nodeName) nth++; }
    s += ':nth-of-type(' + nth + ')';
    path.unshift(s); cur = cur.parentElement;
  }
  return path.join(' > ');
}

function buildRef(el){
  const d = elDesc(el);
  return '[' + DECK_TAG + '] slide ' + d.slideNo + ' · ' + d.path +
    (d.txt ? ' · text: "' + d.txt + '"' : '') + ' · size ' + d.size + ' · css: ' + cssPath(el);
}

function fallbackCopy(text){
  const ta = document.createElement('textarea');
  ta.value = text; document.body.appendChild(ta); ta.select();
  document.execCommand('copy'); ta.remove();
}
function copyText(text){
  if (navigator.clipboard && navigator.clipboard.writeText)
    navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
  else fallbackCopy(text);
}
function toast(msg){
  pickToast.textContent = msg; pickToast.style.display = 'block';
  clearTimeout(pickToast._t);
  pickToast._t = setTimeout(() => { pickToast.style.display = 'none'; }, 4200);
}
function domCmp(a, b){
  if (a === b) return 0;
  return (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1;
}
function updatePickPanel(){
  const n = sel.size + selSlides.size;
  pickCount.textContent = n + ' dipilih';
  pickCopy.textContent = 'Copy refs (' + n + ')';
  pickCopy.disabled = n === 0;
  pickCopy.style.opacity = pickCopy.disabled ? '.4' : '1';
}
function buildMultiRefs(){
  const items = [];
  for (const s of selSlides){
    const no = s.id.replace('slide-','');                   // [ADAPT] id pattern
    const h = s.querySelector('h1, h2, .kicker');
    items.push({ node: s, line: '[' + DECK_TAG + '] slide ' + no + ' — SELURUH SECTION' +
      (h ? ' · ' + h.innerText.trim().replace(/\s+/g,' ') : '') + ' · css: #' + s.id });
  }
  for (const el of sel) items.push({ node: el, line: buildRef(el) });
  items.sort((a, b) => domCmp(a.node, b.node));   // DOM order, not click order
  return ['# ' + DECK_TAG + ' multi-selection (' + items.length + ' refs)',
          ...items.map(i => i.line)].join('\n');
}
function toggleSlideSel(slide){
  const b = slide.querySelector('.slide-pick');
  if (selSlides.has(slide)){ selSlides.delete(slide); if (b) b.classList.remove('on'); }
  else { selSlides.add(slide); if (b) b.classList.add('on'); }
  updatePickPanel();
}
function setPick(on){
  if (on && multiMode) setMulti(false);
  pickMode = on;
  document.body.classList.toggle('pick-mode', on);
  pickBanner.style.display = on ? 'block' : 'none';
  pickBanner.textContent = 'PICK MODE — klik elemen untuk copy referensi · Esc keluar';
  pickBtn.textContent = on ? '✕ Exit pick (Esc)' : '🎯 Pick element';
  if (!on && pickHover){ pickHover.classList.remove('pick-hover'); pickHover = null; pickTip.style.display = 'none'; }
}
function setMulti(on){
  if (on && pickMode && !multiMode) setPick(false);
  multiMode = on; pickMode = on;
  document.body.classList.toggle('pick-mode', on);
  pickBanner.style.display = on ? 'block' : 'none';
  pickBanner.textContent = 'MULTI-PICK — klik banyak elemen (⊕ pojok slide = seluruh section) · Copy refs buat batch · Esc keluar';
  pickMultiBtn.textContent = on ? '✕ Exit multi (Esc)' : '🔲 Multi-pick';
  pickBtn.textContent = on ? '✕ Exit (Esc)' : '🎯 Pick element';
  pickPanel.style.display = on ? 'flex' : 'none';
  document.querySelectorAll('.slide-pick').forEach(b => { b.style.display = on ? 'block' : 'none'; });
  if (!on && pickHover){ pickHover.classList.remove('pick-hover'); pickHover = null; pickTip.style.display = 'none'; }
}

pickBtn.addEventListener('click', () => { if (multiMode) setMulti(false); else setPick(!pickMode); pickBtn.blur(); });
pickMultiBtn.addEventListener('click', () => { setMulti(!multiMode); pickMultiBtn.blur(); });
pickCopy.addEventListener('click', () => {
  copyText(buildMultiRefs());
  toast('✓ Copied ' + (sel.size + selSlides.size) + ' refs — paste ke Hermes');
});
pickClear.addEventListener('click', () => {
  sel.forEach(el => el.classList.remove('pick-sel')); sel.clear();
  selSlides.forEach(s => { const b = s.querySelector('.slide-pick'); if (b) b.classList.remove('on'); }); selSlides.clear();
  updatePickPanel();
});
pickExit.addEventListener('click', () => setMulti(false));

// one ⊕ badge per slide, appended by JS so adding/removing slides needs no markup edit
document.querySelectorAll('.slide').forEach(s => {          // [ADAPT] slide container
  const b = document.createElement('button');
  b.className = 'slide-pick'; b.textContent = '+';
  b.title = 'Pilih seluruh section slide ini';
  b.addEventListener('click', ev => { ev.preventDefault(); ev.stopPropagation(); toggleSlideSel(s); b.blur(); });
  s.appendChild(b);
});

document.addEventListener('keydown', e => {
  const t = e.target;
  const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
  if (e.key === 'Escape'){ if (multiMode) setMulti(false); else if (pickMode) setPick(false); }
  if ((e.key === 'p' || e.key === 'P') && !multiMode && !e.metaKey && !e.ctrlKey && !e.altKey && !typing) setPick(!pickMode);
  if ((e.key === 'm' || e.key === 'M') && !e.metaKey && !e.ctrlKey && !e.altKey && !typing) setMulti(!multiMode);
});
document.addEventListener('mouseover', e => {
  if (!pickMode || e.target.closest(UI_SEL)) return;
  if (pickHover) pickHover.classList.remove('pick-hover');
  pickHover = e.target;
  pickHover.classList.add('pick-hover');
  const d = elDesc(e.target);
  pickTip.innerHTML = '<b>Slide ' + d.slideNo + '</b> · ' + d.path + (d.txt ? '<br>“' + d.txt + '”' : '');
  pickTip.style.display = 'block';
});
document.addEventListener('mousemove', e => {
  if (!pickMode) return;
  pickTip.style.left = Math.min(e.clientX + 14, window.innerWidth - 380) + 'px';
  pickTip.style.top = (e.clientY + 18) + 'px';
});
document.addEventListener('click', e => {
  if (!pickMode || e.target.closest(UI_SEL)) return;
  e.preventDefault(); e.stopPropagation();          // deck nav must not fire on a pick
  const el = e.target;
  el.classList.remove('pick-hover');
  if (multiMode){
    if (sel.has(el)){ sel.delete(el); el.classList.remove('pick-sel'); }
    else { sel.add(el); el.classList.add('pick-sel'); }
    updatePickPanel();
    return;
  }
  el.classList.add('pick-selected');
  setTimeout(() => el.classList.remove('pick-selected'), 1600);
  const ref = buildRef(el);
  copyText(ref);
  toast('✓ Copied — paste ke Hermes: ' + ref);
  setPick(false);
}, true);
```

## Step 4 — adapt exactly these things

| Marker | What to change | Default |
|---|---|---|
| `DECK_TAG` | Uppercase deck name. Appears in every reference. | `'DECK'` |
| `UI_SEL` | Add this deck's chrome selectors — anything that must never be pickable. Without it, clicking the nav or a button produces a reference to the nav or the button. | picker UI only |
| `.slide` / `canvas` | Only if the deck names them differently. | `.slide` / `.canvas` |
| slide id pattern | Only if ids are not `slide-N`. | `slide-` |

## Step 5 — PDF export (1 slide = 1 page)

Add this **inside the same `<style>`**, after the picker CSS:

```css
@media print{
  @page{size:1280px 720px;margin:0}                 /* px, not A4: exact 16:9, no white bars */
  html,body{background:#fff;overflow:visible!important;height:auto;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  #stage{position:static;display:block;inset:auto}   /* un-fix the scaling wrapper */
  #deck{width:1280px;height:auto;transform:none!important;box-shadow:none;border-radius:0}
  /* fixed page box per slide: without it, flex children shrink and text spills out */
  .slide{position:relative;inset:auto;width:1280px!important;height:720px!important;
    opacity:1!important;visibility:visible!important;transform:none!important;
    border-radius:0;page-break-after:always;break-after:page;
    page-break-inside:avoid;break-inside:avoid}
  .slide:last-child,.slide.print-last{page-break-after:auto;break-after:auto}
  /* Chrome's print engine sizes lines from font ascent+descent, not font-size*line-height.
     Large type inflates and overlaps the block below it: pin absolute px. */
  .cover-title{font-size:52px!important;line-height:62px!important}
  .shead h2{font-size:33px!important;line-height:40px!important}
  /* chrome must never print */
  #nav,#progress,#hint,#pickBar,#pickBtn,#pickMultiBtn,#pickTip,#pickBanner,
  #pickPanel,#pickToast,#pdfToast,.slide-pick,.nav-dots,button{
    display:none!important;visibility:hidden!important}
  /* subset export: only the marked slides print */
  body.print-subset .slide{display:none!important}
  body.print-subset .slide.print-keep{display:block!important}
  body.print-subset .slide.print-keep.print-last{page-break-after:auto!important;break-after:auto!important}
}
```

Then, as the **last** script block:

```js
/* ===== PDF export: 1 slide = 1 page ===== */
(function(){
  // Take the slide list from the deck, NOT from a local variable: a block outside the
  // deck's nav IIFE cannot see a `slides` declared inside it (ReferenceError).
  const deck = window.__deck;                    // [ADAPT] or document.querySelectorAll('.slide')
  const slides = deck ? deck.slides : Array.from(document.querySelectorAll('.slide'));

  const PARTS = [
    { label: 'Semua', from: 1, to: slides.length }        // [ADAPT] your section ranges
  ];
  const sel = document.getElementById('partDl');          // [ADAPT] dropdown id
  PARTS.forEach((p, i) => {
    const o = document.createElement('option');
    o.value = String(i); o.textContent = p.label;
    sel.appendChild(o);
  });

  // NOT named toast(): the picker already owns that name and hoisting would make
  // this one lose, so the message would never appear.
  function pdfToast(msg){
    const t = document.getElementById('pdfToast');
    t.textContent = msg; t.style.display = 'block';
    clearTimeout(pdfToast._t);
    pdfToast._t = setTimeout(() => { t.style.display = 'none'; }, 2600);
  }
  function downloadPdf(){
    pdfToast('Menyiapkan PDF — pilih "Save as PDF" di dialog cetak');
    setTimeout(() => window.print(), 120);
  }
  document.getElementById('pdfBtn').addEventListener('click', e => { e.preventDefault(); downloadPdf(); });

  sel.addEventListener('change', () => {
    if (sel.value === '') return;
    const p = PARTS[Number(sel.value)];
    if (!p) return;
    document.body.classList.add('print-subset');
    slides.forEach((s, i) => {
      const n = i + 1;
      s.classList.toggle('print-keep', n >= p.from && n <= p.to);
      // the last kept slide is NOT :last-of-type -> mark it explicitly or the
      // subset ends with a blank page
      s.classList.toggle('print-last', n === p.to);
    });
    function clean(){
      document.body.classList.remove('print-subset');
      slides.forEach(s => s.classList.remove('print-keep', 'print-last'));
      window.removeEventListener('afterprint', clean);
      sel.value = '';
    }
    window.addEventListener('afterprint', clean);
    pdfToast('Cetak ' + p.label + '…');
    setTimeout(() => window.print(), 150);
    setTimeout(clean, 60000);   // failsafe when afterprint never fires
  });
})();
```

Plus two small pieces of markup in the nav:

```html
<select id="partDl" aria-label="Export a section as PDF"><option value="">Unduh bagian…</option></select>
<button id="pdfBtn" title="Print / save as PDF — 1 slide = 1 page, 1280x720">⤓ PDF</button>
<div id="pdfToast" role="status" aria-live="polite"></div>
```

## Pitfalls — each of these cost a debugging round

**Picker**

1. **Filter the highlight classes out of the copied path.** When a reference is built, the element
   carries `.pick-hover` / `.pick-selected` / `.pick-sel`. Unfiltered, every reference contains
   classes that mean nothing on the next page load.
2. **The click handler must be in the capture phase** (`addEventListener('click', fn, true)`) with
   `preventDefault()` + `stopPropagation()`, or the deck's own navigation also fires on a pick.
3. **The hotkey guard must skip typing contexts** (`INPUT` / `TEXTAREA` / `contentEditable`) and
   modifier combinations, or the picker hijacks typing and the browser's own `Cmd/Ctrl+P`.
4. **Do not re-declare a global the deck already owns.** If the deck has `const slides` and the
   picker block has its own, one clobbers the other. `deck.html` shares state through
   `window.__deck`.
5. **`nth-of-type` counts siblings of the same tag**, not all previous siblings.
6. **A missing picker id is a silent crash** — the JS grabs eleven of them; check they all exist.
7. **The badge needs `position:relative` on the slide container**, otherwise it escapes the slide.

**Print**

8. **`#deck{height:auto}` collapses the layout.** Flex-based slides shrink their cards and text
   spills out. Pin `width`/`height` on `.slide` with `!important`.
9. **Chrome's print engine uses font ascent+descent, not `font-size × line-height`.** A 52px title
   measured 71.6px of ink per line; three lines then overlap the block below. Pin absolute
   `line-height` in px inside the print block.
10. **Do not rely on `:last-of-type` for the last slide of a subset.** In a subset the last printed
    slide is not the last in the document. Mark it explicitly with `.print-last`.
11. **`print-color-adjust:exact` is mandatory**, or a user who forgets to tick "Background graphics"
    gets a white PDF with pale text.
12. **Never give the PDF code a second `function toast()`.** Hoisting makes the later one win, and
    the picker's toast stops appearing.
13. **Chrome CLI ≠ CDP `Page.printToPDF`.** `--print-to-pdf` and the browser's print menu work; the
    CDP path can return a single page with a non-standard `@page{size:…px}`. Check with the CLI
    before "fixing" a deck that is already correct.

**Working on decks generally**

14. **Never renumber slide ids.** Delete a slide and leave the gap (`slide-6…13` stays); people and
    notes remember slide numbers.
15. **Edit the deck HTML directly.** If a generator script exists, edit the generator and regenerate —
    otherwise the next run wipes hand edits.
16. **Reference strings must survive a reload**: cap the readable path at ~4 levels, stop at the
    canvas, keep two class names per node, cap the text snippet at 90 chars.

## Reference format

```
[DECK-TAG] slide 3 · div.pad > article.card · text: "Element Picker" · size 276x216 · css: #slide-3 > div.pad:nth-of-type(1) > article.card:nth-of-type(2)
```

Multi-select batches start with a count header, then one reference per line in DOM order:

```
# DECK-TAG multi-selection (3 refs)
[DECK-TAG] slide 2 — SELURUH SECTION · Corrections fail in language · css: #slide-2
[DECK-TAG] slide 3 · ol.steps > li · text: "Hover: cyan outline…" · size 512x42 · css: #slide-3 > … > li:nth-of-type(2)
```

## Agent-side contract — what to do when a reference arrives

1. **Resolve the `css:` path and verify the element still exists and matches the text snippet.**
   Do not trust the path blindly: the deck may have changed since the reference was copied.
2. **Apply the change to the deck source**, not to a generated output if a generator exists.
3. **Re-check the affected slide** before reporting back.
4. **For a `multi-selection (N refs)` batch:** apply all N, then confirm the count so nothing is
   silently dropped.

## Before you hand the deck over

- [ ] <kbd>P</kbd> enters pick mode; hovering shows the cyan outline and the tooltip; a click copies
      a reference and exits pick mode.
- [ ] <kbd>M</kbd> shows the panel and one ⊕ badge per slide; picking two elements plus one whole
      slide then **Copy refs** emits a `(3 refs)` header and three lines in DOM order.
- [ ] The picker's own buttons and the deck's nav **cannot** be picked.
- [ ] <kbd>⤓ PDF</kbd> → page count equals slide count, every page 1280×720, no nav or hint printed,
      no blank trailing page.
- [ ] Nothing on the deck broke: navigation, dots and keyboard still work with the picker installed.

## Reference decks

`deck.html` in this repository is a working 6-slide deck with all three features installed, and its
source is marked `FEATURE 1 + 2` / `FEATURE 3` at each insertion point. Use it as the worked example
when the target deck's structure differs.
