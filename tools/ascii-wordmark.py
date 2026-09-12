#!/usr/bin/env python3
"""Rasterise a word with a real typeface, then trace it in ASCII.

Solid letterforms wrapped in a single contour that closes around the whole
word — the sticker-outline move scene zines use for their mastheads. The
two layers are emitted as separate spans so CSS can colour them apart.

    python3 tools/ascii-wordmark.py fiss
    python3 tools/ascii-wordmark.py fiss --html
"""
import sys

from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
ROWS = 16            # cap height in character rows; below ~12 counters fill in
CELL_ASPECT = 1.9    # a mono cell is ~1 wide : 1.9 tall
TRACK = 0.0          # tight: the contours merge into one shape around the word
HALO_R, HALO_C = 1, 2   # contour reach: 1 row, 2 cols (cells are narrow)
BODY, EDGE = "#", "#"


def _mask(word, rows):
    px = rows * 12
    font = ImageFont.truetype(FONT, px)
    pad = px
    img = Image.new("L", (px * (len(word) + 2) * 2, px * 3), 0)
    draw = ImageDraw.Draw(img)
    x = pad
    for ch in word:                         # draw per glyph to add tracking
        draw.text((x, pad), ch, fill=255, font=font)
        x += draw.textlength(ch, font=font) + px * TRACK
    img = img.crop(img.getbbox())

    cols = max(1, round(img.width / img.height * rows * CELL_ASPECT))
    img = img.resize((cols, rows), Image.LANCZOS)
    return [[img.getpixel((c, r)) > 110 for c in range(cols)] for r in range(rows)], cols


def render(word, rows=ROWS):
    on, cols = _mask(word, rows)
    H, W = rows + 2 * HALO_R, cols + 2 * HALO_C

    def at(r, c):
        r, c = r - HALO_R, c - HALO_C
        return 0 <= r < rows and 0 <= c < cols and on[r][c]

    grid = [[" "] * W for _ in range(H)]
    for r in range(H):
        for c in range(W):
            if at(r, c):
                grid[r][c] = BODY
                continue
            # contour where a letter falls inside an ellipse around the cell
            hit = False
            for dr in range(-HALO_R, HALO_R + 1):
                for dc in range(-HALO_C, HALO_C + 1):
                    if (dr / HALO_R) ** 2 + (dc / HALO_C) ** 2 > 1.0:
                        continue
                    if at(r + dr, c + dc):
                        hit = True
                        break
                if hit:
                    break
            if hit:
                grid[r][c] = EDGE

    body = [[at(r, c) for c in range(W)] for r in range(H)]
    return grid, body


def to_html(grid, body):
    out = []
    for r, row in enumerate(grid):
        line, run, cls = [], [], None
        for c, ch in enumerate(row):
            k = None if ch == " " else ("b" if body[r][c] else "o")
            if k != cls:
                if run:
                    line.append("".join(run) if cls is None
                                else '<span class="%s">%s</span>' % (cls, "".join(run)))
                run, cls = [], k
            run.append(ch)
        if run:
            line.append("".join(run) if cls is None
                        else '<span class="%s">%s</span>' % (cls, "".join(run)))
        out.append("".join(line).rstrip())
    return "\n".join(out).strip("\n")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    word = args[0] if args else "fiss"
    grid, body = render(word)
    if "--html" in sys.argv:
        open("templates/partials/wordmark.html", "w").write(
            '<pre class="wordmark" aria-hidden="true">%s</pre>\n' % to_html(grid, body))
        sys.stderr.write("wrote templates/partials/wordmark.html\n")
    # preview: body solid, contour dotted
    for r, row in enumerate(grid):
        print("".join(ch if body[r][c] else (":" if ch != " " else " ")
                      for c, ch in enumerate(row)).rstrip())
