#!/usr/bin/env python3
"""check_pdf_export.py - verifikasi export PDF '1 slide = 1 halaman' untuk deck HTML.

Pakai:
    python3 check_pdf_export.py deck.html                  # cetak sendiri, lalu periksa
    python3 check_pdf_export.py deck.html --pdf out.pdf    # periksa PDF yang sudah ada
    python3 check_pdf_export.py deck.html --expect 10      # harapan jumlah halaman

Yang diperiksa:
  1. FAIL  jumlah halaman PDF == jumlah <section class="slide"> di deck
  2. FAIL  ukuran halaman == 1280x720 px (960x540 pts) - 16:9, bukan A4
  3. FAIL  ada kata keluar dari bidang halaman (teks terpotong / meluber)
  4. FAIL  dua kata di baris yang sama saling menimpa (teks nabrak teks)
  5. FAIL  halaman kosong (0 kata) - gejala klasik bug page-break subset
  6. WARN  kotak kata bertumpuk vertikal - bisa multi-kolom (normal) atau
           teks menimpa teks. Cetak koordinat, agent yang menilai.
  7. INFO  kata deck yang tidak muncul di halaman PDF-nya (coverage)

Kenapa script ini ada: bug cetak yang paling sering lolos itu BUKAN halaman
kurang, tapi teks yang hilang/tertumpuk DI DALAM halaman yang jumlahnya benar.
pdfinfo saja tidak cukup - harus per-kata (pdftotext -bbox).

Butuh: pdftotext + pdfinfo (poppler), dan Chrome untuk auto-cetak.
Exit 0 kalau semua FAIL lulus.
"""
import argparse
import html as htmllib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
]

NS = {"h": "http://www.w3.org/1999/xhtml"}


def find_chrome():
    for c in CHROME_CANDIDATES:
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            p = shutil.which(c)
            if p:
                return p
    return None


def need(binary):
    if not shutil.which(binary):
        sys.exit("ERROR: '%s' tidak ada di PATH (butuh poppler-utils)." % binary)


def slide_count(deck_html):
    pat = re.compile(r'<section[^>]*class="[^"]*\bslide\b[^"]*"', re.I)
    return len(pat.findall(deck_html))


def strip_tags(chunk):
    chunk = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", chunk,
                   flags=re.S | re.I)
    chunk = re.sub(r"<[^>]+>", " ", chunk)
    return htmllib.unescape(chunk)


def deck_slide_texts(deck_html):
    """Teks per slide, urut. Dipakai untuk cek coverage."""
    starts = [m.start() for m in
              re.finditer(r'<section[^>]*class="[^"]*\bslide\b[^"]*"', deck_html, re.I)]
    out = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(deck_html)
        out.append(strip_tags(deck_html[s:e]))
    return out


def words_of(text):
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'./%-]*", text.lower())


def pdfinfo(pdf):
    r = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True)
    info = {}
    for line in r.stdout.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip()] = v.strip()
    return info


def page_words(pdf, page):
    """[{'t':..,'x0':..,'y0':..,'x1':..,'y1':..}] untuk satu halaman."""
    r = subprocess.run(["pdftotext", "-f", str(page), "-l", str(page), "-bbox", pdf, "-"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, None
    try:
        root = ET.fromstring(r.stdout)
    except ET.ParseError as e:
        return None, "XML parse gagal: %s" % e
    pg = root.find(".//h:page", NS)
    if pg is None:
        return [], None
    box = (float(pg.get("width")), float(pg.get("height")))
    out = []
    for w in pg.findall("h:word", NS):
        out.append({
            "t": (w.text or "").strip(),
            "x0": float(w.get("xMin")), "y0": float(w.get("yMin")),
            "x1": float(w.get("xMax")), "y1": float(w.get("yMax")),
        })
    return out, box


def overlaps_same_line(ws, tol=1.0):
    """Kata di baseline sama yang kotaknya benar-benar beririsan horizontal."""
    groups = {}
    for w in ws:
        groups.setdefault(round(w["y0"]), []).append(w)
    hits = []
    for y, g in groups.items():
        g.sort(key=lambda w: w["x0"])
        for a, b in zip(g, g[1:]):
            if b["x0"] < a["x1"] - tol:
                hits.append((a, b))
    return hits


def overlaps_cross_line(ws):
    """Kotak bertumpuk di dua sumbu tapi baseline beda.
    Ambigu: bisa multi-kolom (normal) atau teks menimpa teks."""
    hits = []
    for i, a in enumerate(ws):
        for b in ws[i + 1:]:
            if abs(a["y0"] - b["y0"]) < 1.0:
                continue
            if (a["x0"] < b["x1"] and b["x0"] < a["x1"]
                    and a["y0"] < b["y1"] and b["y0"] < a["y1"]):
                hits.append((a, b))
    return hits


def print_pdf(deck, out, chrome):
    url = "file://" + os.path.abspath(deck)
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           "--print-to-pdf=" + out, "--virtual-time-budget=4000", url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(out):
        sys.exit("ERROR: Chrome gagal mencetak.\n" + (r.stderr or "")[-800:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--pdf")
    ap.add_argument("--expect", type=int)
    ap.add_argument("--page", default="1280x720",
                    help="ukuran halaman px yang diharapkan (default 1280x720)")
    a = ap.parse_args()

    need("pdfinfo")
    need("pdftotext")

    deck_html = open(a.deck, encoding="utf-8", errors="replace").read()
    n_slides = slide_count(deck_html)
    expect = a.expect or n_slides

    tmp = None
    pdf = a.pdf
    if not pdf:
        chrome = find_chrome()
        if not chrome:
            sys.exit("ERROR: Chrome tidak ditemukan; kasih --pdf <file> yang sudah ada.")
        fd, tmp = tempfile.mkstemp(suffix=".pdf"); os.close(fd)
        print_pdf(a.deck, tmp, chrome)
        pdf = tmp

    fails, warns = [], []
    info = pdfinfo(pdf)
    pages = int(info.get("Pages", "0"))
    size = info.get("Page size", "")
    m = re.match(r"([\d.]+)\s*x\s*([\d.]+)", size)
    pts = (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)
    px = (round(pts[0] / 0.75), round(pts[1] / 0.75))
    want = tuple(int(v) for v in a.page.lower().split("x"))

    print("deck      : %s" % a.deck)
    print("pdf       : %s" % pdf)
    print("halaman   : %d (harapan %d)" % (pages, expect))
    print("ukuran    : %s pts = %sx%s px (harapan %sx%s)"
          % (size, px[0], px[1], want[0], want[1]))
    print()

    if pages != expect:
        fails.append("jumlah halaman %d != harapan %d" % (pages, expect))
    if px != want:
        fails.append("ukuran halaman %sx%s px != %sx%s - cek @page{size:...px}"
                     % (px[0], px[1], want[0], want[1]))

    texts = deck_slide_texts(deck_html)
    print("%-4s %-6s %-6s %-7s %-7s %s"
          % ("hal", "kata", "luar", "nabrak", "tumpuk", "coverage"))
    for p in range(1, pages + 1):
        ws, box = page_words(pdf, p)
        if ws is None:
            fails.append("halaman %d: %s" % (p, box))
            print("%-4d GAGAL baca bbox: %s" % (p, box))
            continue
        if box is None:
            fails.append("halaman %d tidak ada di PDF" % p)
            continue
        W, H = box
        out_of = [w for w in ws if w["x0"] < -0.5 or w["y0"] < -0.5
                  or w["x1"] > W + 0.5 or w["y1"] > H + 0.5]
        same = overlaps_same_line(ws)
        cross = overlaps_cross_line(ws)
        if not ws:
            fails.append("halaman %d kosong (0 kata)" % p)
        if out_of:
            fails.append("halaman %d: %d kata keluar bidang" % (p, len(out_of)))
        if same:
            fails.append("halaman %d: %d pasang kata nabrak di baris sama" % (p, len(same)))
        if cross:
            warns.append("halaman %d: %d kotak tumpuk vertikal "
                         "(cek: multi-kolom atau tabrakan?)" % (p, len(cross)))

        cov = "-"
        if p <= len(texts):
            want_w = {w for w in words_of(texts[p - 1]) if len(w) >= 6}
            have = set(words_of(" ".join(w["t"] for w in ws)))
            miss = want_w - have
            if want_w:
                cov = "%d/%d" % (len(want_w) - len(miss), len(want_w))
        print("%-4d %-6d %-6d %-7d %-7d %s"
              % (p, len(ws), len(out_of), len(same), len(cross), cov))

        for w1 in out_of[:4]:
            print("        LUAR   %-22s x0=%.1f y0=%.1f x1=%.1f y1=%.1f"
                  % (w1["t"][:22], w1["x0"], w1["y0"], w1["x1"], w1["y1"]))
        for a1, b1 in same[:3]:
            print("        NABRAK %-16s vs %-16s y=%.0f"
                  % (a1["t"][:16], b1["t"][:16], a1["y0"]))
        for a1, b1 in cross[:2]:
            print("        TUMPUK %-16s(y%.0f-%.0f) x %-16s(y%.0f-%.0f)"
                  % (a1["t"][:16], a1["y0"], a1["y1"], b1["t"][:16], b1["y0"], b1["y1"]))

    print()
    print("CATATAN: coverage < 100% sering NORMAL - teks chrome deck (nav, hint,")
    print("tombol, picker) memang tidak tercetak. Cek daftar katanya, jangan panik.")
    print("CATATAN: baris 'luar'/'nabrak' WAJIB 0. Baris 'tumpuk' perlu dinilai manual.")
    print()
    for w in warns:
        print("WARN  " + w)
    if fails:
        print()
        for f in fails:
            print("FAIL  " + f)
        print("\n=> GAGAL (%d)" % len(fails))
        if tmp:
            print("(pdf sementara: %s)" % pdf)
        return 1
    print("=> LULUS: %d halaman, %sx%s px, tanpa teks keluar/nabrak/kosong"
          % (pages, px[0], px[1]))
    if tmp:
        print("(pdf sementara: %s)" % pdf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
