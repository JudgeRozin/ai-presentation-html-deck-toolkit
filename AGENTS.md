---
name: implement-slide-tools
description: Use when an HTML slide deck needs an element picker, a multi-picker, or PDF export (1 slide = 1 page) — building a new deck or adding the features to an existing one. Trigger on "/implement-slide-tools".
license: MIT
metadata:
  version: "1.0"
---

# Implement Slide Tools

Give an HTML deck three features that make it correctable: an **element picker**, a
**multi-picker**, and **PDF export at 1 slide = 1 page**.

One HTML file. No dependencies, no build step, no libraries.

| Feature | Trigger | What it does |
|---|---|---|
| Element picker | <kbd>P</kbd> | Hover + click an element → copies a precise reference string |
| Multi-picker | <kbd>M</kbd> | Select many elements, or a whole slide → copies one batch |
| PDF export | nav button | `window.print()` → 1 slide = 1 page, 1280×720, backgrounds intact |

The user points at an element; the deck copies a reference an agent can resolve exactly.
That loop — point, paste, fix — is the whole product.

---

## 0. Before you paste — read the deck

**Do not paste blind.** Open the target deck's HTML and establish three facts. A paste
that assumes the wrong structure fails silently: the picker loads, does nothing, and
logs nothing.

| Fact | Why it matters | Assumed default |
|---|---|---|
| Slide container | Bounds the readable path; yields the slide number | `<section class="slide" id="slide-N">` |
| Canvas element | Where the readable path stops | `.canvas` |
| Deck chrome | Everything that must never be pickable | `#nav`, `.nav-dots`, `#hint`, `#progress`, buttons |

Two structural traps:

- **Slide ids must be `slide-N`.** The slide number comes from
  `slide.id.replace('slide-','')`. A deck using `id="s1"` needs either that line changed to
  `id.replace(/^s/,'')` or the ids renamed — renaming is usually cleaner.
- **`.slide` and `.canvas` may be named something else.** If so, change the two references in
  the picker JS (`el.closest('.slide')`, `cur.classList.contains('canvas')`). With no canvas
  wrapper at all, point it at the slide container itself.

---

## 1. Philosophy

**A correction is only as precise as the reference you can give.**

The user reviews a rendered deck with their eyes and corrects it by pointing. Without a picker
every correction is a guess at a DOM path — *"the blue box, bottom right"* — and a wrong guess
costs a full render-and-review round. The picker converts a vague instruction into a reference
that resolves to exactly one element.

Install it **before** handing a deck over, not after the first misunderstanding.

**The reference must survive a reload.** A path that only resolves while the element is still
highlighted is not a reference. That single constraint drives most of the rules in §7.

---

## 2. When to use — and when not to

**Use for:**

- A new HTML deck or presentation, before it goes to a reviewer.
- An existing deck that keeps coming back with vague change requests.
- A pasted `[DECK-TAG] slide N · …` reference — that is the picker's output, and §12 is the
  contract for handling it.

**Don't use for:**

- A deck nobody will revise → the picker earns nothing.
- A PDF or PPTX deliverable with no HTML source → there is nothing to pick from.
- A one-off diagram or static image → see a diagram skill instead.
- Replacing a review conversation → the picker sharpens a request, it does not make one.

Before installing, ask: *will this deck be revised by someone pointing at it?* If no, stop.

---

## 3. What you're adding

Three independent features. Install all three unless the user asked for one.

| Feature | Needs | Skip when |
|---|---|---|
| Element picker | CSS + DOM + JS (§5) | never — it is the reason this skill exists |
| Multi-picker | the same blocks; it ships with the picker | the deck is one slide |
| PDF export | print CSS + a small JS block (§8) | the deck is never printed or shared as PDF |

---

## 4. Anti-patterns

Every row below is a defect seen in a real deck. Grouped by where it bites.

**Picker**

| Anti-pattern | Why it fails |
|---|---|
| Copying the highlight classes into the reference | `.pick-hover` / `.pick-selected` / `.pick-sel` are on the element at copy time; unfiltered, every reference carries class names that mean nothing on the next load |
| Click handler on the bubble phase | The deck's own navigation also fires, so a pick changes the slide |
| Hotkey with no typing guard | `P` hijacks text entry; `Cmd/Ctrl+P` gets stolen from the browser |
| A second global named `slides` | One clobbers the other. A block outside the deck's nav IIFE cannot see a `slides` declared inside it — `ReferenceError` |
| `nth-of-type` counting all previous siblings | Count only siblings of the same tag, or the CSS path resolves to the wrong element |
| A missing picker id | Silent crash: eleven ids are read with `getElementById`, and some browsers log nothing when one is absent |
| The ⊕ badge without `position:relative` on the slide | The badge escapes the slide and lands wherever the page puts it |

**Print**

| Anti-pattern | Why it fails |
|---|---|
| `#deck{height:auto}` | Flex-based slides shrink their cards and text spills outside them |
| Trusting `font-size × line-height` in print | Chrome sizes lines from font ascent+descent: a 52px title measured **71.6px of ink per line** and overlapped the block below |
| `:last-of-type` for the last slide of a subset | In a subset the last printed slide is not the last in the document → a blank trailing page |
| Omitting `print-color-adjust:exact` | A user who does not tick "Background graphics" gets a white PDF with pale text |
| A second `function toast()` | Hoisting makes the later one win, and the picker's toast stops appearing |
| Judging subset export through CDP `Page.printToPDF` | With a non-standard `@page{size:…px}` it can return a single page. Check with the CLI or the browser's own print menu before "fixing" a correct deck |
| Assuming a `<select>` is hidden by a `button` rule | It is not. `#partDl` must be listed explicitly or the dropdown prints on every page |

**Contrast — the failure a layout audit never sees**

| Anti-pattern | Why it fails |
|---|---|
| A dark-card text override that lists only some classes | `.card.tray .ul li b` did not cover `<ul class="locs">`; that list fell through to the light-card rule and measured **1.12:1** — present, positioned, unreadable |
| Reading the background from `getComputedStyle` | Over a gradient it returns transparent; the walk up the ancestors lands on the wrong colour |
| Auditing by tag + class + colour only | `<b>` in a white card and `<b>` in a dark tray collapse into one row, and whichever is failing disappears |

---

## 5. The blocks

Three blocks, pasted in three places. **All eleven picker ids are required** — a missing one is
a silent crash, not an error.

### 5a. CSS — inside the deck's last `<style>`

```css

/* ============================================================================
   FEATURE 1 + 2 — ELEMENT PICKER / MULTI-PICKER (CSS)
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

The slide container needs `position:relative` (the ⊕ badge is absolutely positioned inside it).
The badge itself is created in JS, so adding or removing slides needs no markup change.

### 5b. DOM — immediately after `<body>`

```html

<div id="pickBar">
  <button id="pickBtn" title="Element Picker (P)">🎯 Pick element</button>
  <button id="pickMultiBtn" title="Multi-picker (M)">🔲 Multi-pick</button>
</div>
<div id="pickBanner">PICK MODE — click an element to copy its reference · Esc to exit</div>
<div id="pickTip"></div>
<div id="pickToast"></div>
<div id="pickPanel">
  <span id="pickCount">0 selected</span>
  <button id="pickCopy">Copy refs</button>
  <button id="pickClear" class="danger">Clear</button>
  <button id="pickExit" class="danger">Exit</button>
</div>
```

### 5c. JS — the LAST script block in the document

Last, so the deck's own functions already exist when a pick suppresses a click.

```js

/* ============================================================================
   FEATURE 1 + 2 — ELEMENT PICKER / MULTI-PICKER (JS)
   Keep this block LAST so the deck's own functions already exist.
   [ADAPT] DECK_TAG : uppercase deck name, e.g. 'Q3-REVIEW'. Prefixes every reference.
   [ADAPT] UI_SEL   : add every piece of this deck's chrome that must not be pickable.
   ========================================================================== */
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
  pickCount.textContent = n + ' selected';
  pickCopy.textContent = 'Copy refs (' + n + ')';
  pickCopy.disabled = n === 0;
  pickCopy.style.opacity = pickCopy.disabled ? '.4' : '1';
}
function buildMultiRefs(){
  const items = [];
  for (const s of selSlides){
    const no = s.id.replace('slide-','');                   // [ADAPT] id pattern
    const h = s.querySelector('h1, h2, .kicker');
    items.push({ node: s, line: '[' + DECK_TAG + '] slide ' + no + ' — WHOLE SECTION' +
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
  pickBanner.textContent = 'PICK MODE — click an element to copy its reference · Esc to exit';
  pickBtn.textContent = on ? '✕ Exit pick (Esc)' : '🎯 Pick element';
  if (!on && pickHover){ pickHover.classList.remove('pick-hover'); pickHover = null; pickTip.style.display = 'none'; }
}
function setMulti(on){
  if (on && pickMode && !multiMode) setPick(false);
  multiMode = on; pickMode = on;
  document.body.classList.toggle('pick-mode', on);
  pickBanner.style.display = on ? 'block' : 'none';
  pickBanner.textContent = 'MULTI-PICK — click as many elements as you want (⊕ in a slide corner selects the whole section) · Copy refs for the batch · Esc to exit';
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
  toast('✓ Copied ' + (sel.size + selSlides.size) + ' refs — paste into your agent chat');
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
  b.title = 'Select this whole slide';
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
  toast('✓ Copied — paste into your agent chat: ' + ref);
  setPick(false);
}, true);
```

---

## 6. Adapt — four things, then you're done

The code carries `[ADAPT]` markers at each of these lines.

| Marker | What to change | Default |
|---|---|---|
| `DECK_TAG` | Uppercase deck name; prefixes every reference so a paste is traceable | `'DECK'` |
| `UI_SEL` | Every piece of this deck's chrome. Without it, clicking the nav returns a reference to the nav | picker UI only |
| `.slide` / `canvas` | Only if the deck names them differently | `.slide` / `.canvas` |
| slide id pattern | Only if ids are not `slide-N` | `slide-` |

---

## 7. Rules that never relax

These are invariants, not preferences. Each one exists because breaking it produced a bug
listed in §4.

| # | Rule |
|---|---|
| 1 | The click handler is registered in the **capture phase** (`addEventListener('click', fn, true)`) with `preventDefault()` + `stopPropagation()`. |
| 2 | `UI_SEL` lists **every** piece of chrome, and a `<select>` is never assumed to be covered by a `button` rule. |
| 3 | The highlight classes are filtered out of **both** path builders — the readable path and the CSS path. |
| 4 | Slide ids are **never renumbered**. Delete a slide and leave the gap: people and notes remember slide numbers. |
| 5 | The picker block is the **last** script, and it declares no global the deck already owns. |
| 6 | Reference caps: readable path ≤ 4 levels stopping at the canvas, ≤ 2 class names per node, text snippet ≤ 90 chars, CSS path ≤ 6 levels stopping at the first id. |
| 7 | In print, `.slide` gets a **rigid** `width`/`height` with `!important`, and large type gets an **absolute** `line-height` in px. |
| 8 | The last printed slide of a subset is marked explicitly (`.print-last`) and the classes are cleaned on `afterprint`, with a timeout as a failsafe. |

---

## 8. PDF export — 1 slide = 1 page

Add this **inside the same `<style>`**, after the picker CSS:

```css

/* ============================================================================
   FEATURE 3 — PDF EXPORT: 1 slide = 1 page (CSS)
   ========================================================================== */
@media print{
  @page{size:1280px 720px;margin:0}
  html,body{background:#fff;overflow:visible !important;height:auto;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  #stage{position:static;display:block;inset:auto}
  #deck{width:1280px;height:auto;transform:none !important;box-shadow:none;border-radius:0}
  /* fixed box per slide: stops flex children collapsing and text spilling out */
  .slide{position:relative;inset:auto;width:1280px !important;height:720px !important;
    opacity:1 !important;visibility:visible !important;transform:none !important;
    border-radius:0;page-break-after:always;break-after:page;
    page-break-inside:avoid;break-inside:avoid}
  .slide:last-child,.slide.print-last{page-break-after:auto;break-after:auto}
  /* Chrome print uses font ascent+descent, not font-size*line-height:
     big type inflates and overlaps the block below. Pin absolute px. */
  .cover-title{font-size:52px !important;line-height:62px !important}
  .cover-sub{font-size:17px !important;line-height:27px !important}
  .shead h2{font-size:33px !important;line-height:40px !important}
  .quote{font-size:19px !important;line-height:26px !important}
  .ul li,.steps li{line-height:21px !important}
  pre{line-height:20px !important}
  .tbl td{line-height:18px !important}
  /* chrome never prints */
  #nav,#progress,#hint,#pickBar,#pickBtn,#pickMultiBtn,#pickTip,#pickBanner,
  #pickPanel,#pickToast,#pdfToast,#partDl,#pdfBtn,.slide-pick,.nav-dots,
  .spacer,button{display:none !important;visibility:hidden !important}
  /* subset mode: only .print-keep slides print */
  body.print-subset .slide{display:none !important}
  body.print-subset .slide.print-keep{display:block !important}
  /* last slide of a subset is NOT :last-of-type -> needs an explicit class */
  body.print-subset .slide.print-keep.print-last,
  body.print-subset .slide.print-keep:last-of-type{page-break-after:auto !important;break-after:auto !important}
}
```

Then, as the **last** script block:

```js

/* ============================================================================
   FEATURE 3 — PDF EXPORT: 1 slide = 1 page (JS)
   ========================================================================== */
(function(){
  // Take the slide list from the deck, NOT from a local variable: a block outside the
  // deck's nav IIFE cannot see a `slides` declared inside it (ReferenceError).
  const deck = window.__deck;                    // [ADAPT] or document.querySelectorAll('.slide')
  const slides = deck ? deck.slides : Array.from(document.querySelectorAll('.slide'));

  const PARTS = [
    { label: 'All slides', from: 1, to: slides.length }   // [ADAPT] your section ranges
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
    pdfToast('Preparing PDF — choose "Save as PDF" in the print dialog');
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
    pdfToast('Printing ' + p.label + '…');
    setTimeout(() => window.print(), 150);
    setTimeout(clean, 60000);   // failsafe when afterprint never fires
  });
})();
```

Plus three pieces of markup in the deck's nav:

```html

<select id="partDl" aria-label="Export a section as PDF"><option value="">Export a section…</option></select>
<button id="pdfBtn" title="Print / save as PDF — 1 slide = 1 page, 1280x720">⤓ PDF</button>
<div id="pdfToast" role="status" aria-live="polite"></div>
```

**Page size is a decision to put to the user, not make yourself.** `@page{size:1280px 720px}`
gives a full 16:9 page with no margins. A4 landscape is only right when the deck will be
*physically printed* — at the cost of white bars on the sides. State the trade-off.

---

## 9. Adding this to a deck that already exists

This is the common case, and it is the same three blocks — the work is in §0, not in the paste.

1. Read the deck and resolve the three facts from §0. If the slide container or ids do not match
   the defaults, fix the references **before** pasting, not after something silently fails.
2. Back the file up.
3. Paste CSS, DOM, JS in the three places named in §5. Then the print CSS and PDF JS from §8 if
   the deck is shared as PDF.
4. Extend `UI_SEL` with this deck's chrome. Walk the nav and the fixed-position elements; each
   one you miss becomes a pickable element.
5. Open the deck and press <kbd>P</kbd>, then <kbd>M</kbd>, then the PDF button. If the picker
   does nothing, an id is missing — check the console for a crash, then compare the eleven ids.

Do not restyle the deck while installing. Two changes at once make a silent failure
unattributable.

---

## 10. Worked example

`deck.html` in this repository is a working six-slide deck with all three features installed.
Its source is marked `FEATURE 1 + 2` and `FEATURE 3` at every insertion point, so the location of
each block is visible rather than described.

Use it when the target deck's structure differs from the defaults in §0, and to see what a
correctly wired picker looks like before debugging one.

---

## 11. Output

The deliverable is the deck itself — a single self-contained `.html` file:

- Embedded CSS, no external assets except web fonts
- No runtime dependencies, no build step, no package install
- Renders correctly opened directly from disk, and prints correctly from the browser

The picker's own UI is chrome: it must never appear in the PDF, and it must never be pickable.

---

## 12. Agent-side contract — when a reference arrives

A reference is the user pointing at something. Handle it as a location, not a description.

```

[DECK-TAG] slide 3 · div.pad > article.card · text: "Element Picker" · size 276x216 · css: #slide-3 > div.pad:nth-of-type(1) > article.card:nth-of-type(2)
```

A multi-pick batch starts with a count header, then one reference per line in **DOM order** —
so the paste reads like the deck rather than like the user's clicking history:

```

# DECK-TAG multi-selection (3 refs)
[DECK-TAG] slide 2 — WHOLE SECTION · Corrections fail in language · css: #slide-2
[DECK-TAG] slide 3 · ol.steps > li · text: "Hover: cyan outline…" · size 512x42 · css: #slide-3 > … > li:nth-of-type(2)
```

When one arrives:

1. **Resolve the `css:` path and verify the element still exists and matches the text snippet.**
   Do not trust the path blindly — the deck may have changed since the reference was copied.
2. **Apply the change to the deck source.** If a generator script exists, change the generator and
   regenerate; a hand edit to generated output is wiped on the next run.
3. **Re-check the affected slide** before reporting back.
4. **For a `multi-selection (N refs)` batch:** apply all N, then confirm the count so nothing is
   silently dropped.
