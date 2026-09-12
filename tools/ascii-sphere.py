#!/usr/bin/env python3
"""Ray-march a lit sphere onto a character grid.

Emits two versions: on paper, ink density means shadow; on a dark ground,
density means light. Rendering both keeps the key light in the same corner
whichever theme the reader is in.

    python3 tools/ascii-sphere.py > /tmp/art.txt
"""
import math

W, H = 26, 13
RAMP = " .:-=+*#%@"
LIGHT = (-0.55, -0.75, 0.45)   # upper-left key


def norm(v):
    m = math.sqrt(sum(c * c for c in v))
    return tuple(c / m for c in v)


def render(invert):
    lx, ly, lz = norm(LIGHT)
    rows = []
    for y in range(H):
        line = []
        for x in range(W):
            nx = (x - W / 2 + 0.5) / (W / 2.35)   # cells are ~2:1
            ny = (y - H / 2 + 0.5) / (H / 2.1)
            r2 = nx * nx + ny * ny
            if r2 > 1.0:
                line.append(" ")
                continue
            nz = math.sqrt(1.0 - r2)
            lam = max(nx * lx + ny * ly + nz * lz, 0.0)
            i = 0.12 + 0.88 * lam ** 0.8
            if invert:
                i = 1.0 - i
            idx = min(int(i * len(RAMP)), len(RAMP) - 1)
            line.append(RAMP[max(idx, 1)])  # never blank inside the disc
        rows.append("".join(line).rstrip())
    return "\n".join(rows)


def write_partial():
    import html
    out = ('<div class="ascii" aria-hidden="true">\n'
           '<pre class="ascii-paper">%s</pre>\n'
           '<pre class="ascii-ink">%s</pre>\n'
           '</div>\n') % (html.escape(render(invert=True)),
                          html.escape(render(invert=False)))
    open("templates/partials/ascii.html", "w").write(out)


if __name__ == "__main__":
    import sys
    if "--html" in sys.argv:
        write_partial()
        sys.stderr.write("wrote templates/partials/ascii.html\n")
    print("--- on paper (ink = shadow) ---")
    print(render(invert=True))
    print()
    print("--- on ink (density = light) ---")
    print(render(invert=False))
