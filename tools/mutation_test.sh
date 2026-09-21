#!/usr/bin/env bash
# mutation_test.sh — prove the verifiers can actually FAIL.
#
# A verifier that is always green is worse than no verifier: it certifies nothing.
# This script breaks a healthy deck on purpose, one defect at a time, and asserts
# that the matching tool reports failure. Any "NOT CAUGHT" line is a hole in the
# tooling, not a passing test.
#
# Usage:  bash tools/mutation_test.sh [deck.html]
set -u

DECK="${1:-deck.html}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0

check() { # check <name> <expected-exit> <actual-exit>
  if [ "$2" = "$3" ]; then echo "  caught   $1"; pass=$((pass+1));
  else echo "  NOT CAUGHT  $1 (expected exit $2, got $3)"; fail=$((fail+1)); fi
}

echo "mutation testing against $DECK"
echo

# ---- M1: two text blocks forced to overlap (real ink collision) --------------
cp "$DECK" "$TMP/m1.html"
python3 - "$TMP/m1.html" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); t = p.read_text()
t = t.replace('.shead h2{margin:0;', '.shead h2{margin:-30px 0 0;')
p.write_text(t)
PY
python3 tools/fit_check.py "$TMP/m1.html" --quiet-benign >/dev/null 2>&1
check "M1 overlapping headings -> fit_check INK-COLLIDE" 1 $?

# ---- M2: a card too short for its content (real overflow) --------------------
cp "$DECK" "$TMP/m2.html"
python3 - "$TMP/m2.html" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); t = p.read_text()
t = t.replace('.card{background:var(--card);', '.card{height:120px;overflow:hidden;background:var(--card);')
p.write_text(t)
PY
python3 tools/fit_check.py "$TMP/m2.html" --quiet-benign >/dev/null 2>&1
check "M2 card forced to 120px -> fit_check OVERFLOW" 1 $?

# ---- M3: text pushed outside the slide canvas --------------------------------
cp "$DECK" "$TMP/m3.html"
python3 - "$TMP/m3.html" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); t = p.read_text()
t = t.replace('.cover-foot{position:absolute;left:64px;right:64px;bottom:34px;',
              '.cover-foot{position:absolute;left:-90px;right:64px;bottom:-40px;')
p.write_text(t)
PY
python3 tools/fit_check.py "$TMP/m3.html" --quiet-benign >/dev/null 2>&1
check "M3 footer pushed off-canvas -> fit_check OUTSIDE-CANVAS" 1 $?

# ---- M4: picker wiring removed (no capture-phase click) ----------------------
cp "$DECK" "$TMP/m4.html"
python3 - "$TMP/m4.html" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); t = p.read_text()
t = t.replace('}, true);', '});')
p.write_text(t)
PY
python3 tools/check_deck.py "$TMP/m4.html" --tag DECK-KIT >/dev/null 2>&1
check "M4 capture-phase click removed -> check_deck FAIL" 1 $?

# ---- M5: a picker DOM id deleted (silent JS crash) ---------------------------
cp "$DECK" "$TMP/m5.html"
python3 - "$TMP/m5.html" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); t = p.read_text()
t = t.replace('<div id="pickPanel">', '<div id="pickPanel-renamed">')
p.write_text(t)
PY
python3 tools/check_deck.py "$TMP/m5.html" --tag DECK-KIT >/dev/null 2>&1
check "M5 picker id renamed -> check_deck FAIL" 1 $?

# ---- M6: print page size wrong (A4 instead of 1280x720) ----------------------
cp "$DECK" "$TMP/m6.html"
python3 - "$TMP/m6.html" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); t = p.read_text()
t = t.replace('@page{size:1280px 720px;margin:0}', '@page{size:A4 landscape;margin:0}')
p.write_text(t)
PY
if command -v pdfinfo >/dev/null 2>&1; then
  python3 tools/check_pdf_export.py "$TMP/m6.html" --expect 6 >/dev/null 2>&1
  check "M6 @page A4 -> check_pdf_export FAIL" 1 $?
else
  echo "  skipped  M6 (poppler/pdfinfo not installed)"
fi

# ---- M7: subset export loses its last-slide exemption -> blank page ----------
# The subset path is JS-driven (dropdown -> window.print()), so the CLI verifier
# can't click it. Harness instead: bake the exact DOM state the JS produces
# (body.print-subset + .print-keep/.print-last) into a copy and print that.
mk_subset() { # mk_subset <out.html> <keep-csv> <last-slide>
  python3 - "$DECK" "$1" "$2" "$3" <<'PY'
import pathlib, sys
src, dst, keep, last = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
t = pathlib.Path(src).read_text()
t = t.replace('<body>', '<body class="print-subset">', 1)
keep = {int(x) for x in keep.split(',')}
last = int(last)
# split on the marker and put it back with the state classes appended, otherwise
# the marker is consumed and nothing can be injected
parts = t.split('<section class="slide')
out = [parts[0]]
for i, chunk in enumerate(parts[1:], start=1):
    cls = []
    if i in keep:
        cls.append('print-keep')
        if i == last:
            cls.append('print-last')
    out.append('<section class="slide' + ((' ' + ' '.join(cls)) if cls else '') + chunk)
pathlib.Path(dst).write_text(''.join(out))
PY
}

if command -v pdfinfo >/dev/null 2>&1; then
  mk_subset "$TMP/subset.html" 3,4 4
  python3 tools/check_pdf_export.py "$TMP/subset.html" --expect 2 >/dev/null 2>&1
  check "control subset harness (slides 3-4) -> exactly 2 pages" 0 $?

  mk_subset "$TMP/m7.html" 3,4 4
  python3 - "$TMP/m7.html" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); t = p.read_text()
# subset mode no longer hides the unkept slides -> every slide prints
t = t.replace('body.print-subset .slide{display:none !important}', '')
p.write_text(t)
PY
  python3 tools/check_pdf_export.py "$TMP/m7.html" --expect 2 >/dev/null 2>&1
  check "M7 subset stops hiding unkept slides -> page count caught" 1 $?
  # NOTE: the trailing-blank-page variant of this bug (dropping the .print-last
  # exemption) did NOT reproduce under Chrome's CLI print in this deck, so it is
  # deliberately not claimed here.
else
  echo "  skipped  M7 (poppler/pdfinfo not installed)"
fi

# ---- M8: the whole print block disabled -> export falls back to screen layout -
# Note: with a fixed 720px slide and a 720px page, removing page-break-after is
# NOT a defect (each slide exactly fills a page anyway) — tested, and it stayed
# green. So this mutation attacks the thing that really matters: the print rules.
cp "$DECK" "$TMP/m8.html"
python3 - "$TMP/m8.html" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); t = p.read_text()
t = t.replace('@media print{', '@media print-disabled{', 1)
p.write_text(t)
PY
if command -v pdfinfo >/dev/null 2>&1; then
  python3 tools/check_pdf_export.py "$TMP/m8.html" --expect 6 >/dev/null 2>&1
  check "M8 print rules disabled -> wrong page size/count caught" 1 $?
else
  echo "  skipped  M8 (poppler/pdfinfo not installed)"
fi

# ---- M9: batch loses its DOM ordering -> feature test must notice -------------
cp "$DECK" "$TMP/m9.html"
python3 - "$TMP/m9.html" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); t = p.read_text()
t = t.replace('  items.sort((a, b) => domCmp(a.node, b.node));', '')
p.write_text(t)
PY
python3 tools/check_features.py "$TMP/m9.html" >/dev/null 2>&1
check "M9 DOM ordering removed -> check_features FAIL" 1 $?

# ---- M10: UI_SEL guard removed -> picker chrome becomes pickable -------------
cp "$DECK" "$TMP/m10.html"
python3 - "$TMP/m10.html" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); t = p.read_text()
t = t.replace('if (!pickMode || e.target.closest(UI_SEL)) return;', 'if (!pickMode) return;')
p.write_text(t)
PY
python3 tools/check_features.py "$TMP/m10.html" >/dev/null 2>&1
check "M10 UI_SEL guard removed -> check_features FAIL" 1 $?

# ---- control: the untouched deck must PASS every verifier --------------------
echo
python3 tools/check_deck.py "$DECK" --tag DECK-KIT >/dev/null 2>&1
check "control check_deck on clean deck -> PASS" 0 $?
python3 tools/fit_check.py "$DECK" --quiet-benign >/dev/null 2>&1
check "control fit_check on clean deck -> PASS" 0 $?
python3 tools/check_features.py "$DECK" >/dev/null 2>&1
check "control check_features on clean deck -> PASS" 0 $?

echo
echo "caught $pass, missed $fail"
[ "$fail" -eq 0 ] || exit 1
