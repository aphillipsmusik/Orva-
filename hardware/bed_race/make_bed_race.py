#!/usr/bin/env python3
"""Orva bed ball race: loose steel balls running in a channel cut into the
underside of the hot plate and a channel cut into the base.

    python3 make_bed_race.py            # writes the DXFs, the cross-section
                                        # SVG, and prints the machining table

Layout (all at the plate's outer edge, outside the heater and ring gear):

  * Hot plate underside: a gothic-arch groove (two arcs slightly larger than
    the ball) on the ball circle.  It locates the balls radially.
  * Base: a flat-bottomed channel holding a laser-cut stainless race ring.
    The balls can roll a little in and out on it, so when the hot plate grows
    with heat (aluminium, ~0.2 mm on the radius at 100 C) nothing binds.
  * A laser-cut stainless cage keeps the balls evenly spaced.
  * Radial location comes from one small bearing at the hub (around the slip
    ring); a spring stack under the hub pulls the plate down onto the balls,
    so the race carries the plate's weight and the nozzle's push with very
    little friction.

Only the standard library is needed.
"""
import argparse, math


class BedRace:
    def __init__(self, ball=4.0, ball_circle=271., plate_dia=280.,
                 plate_thk=6., groove_conformity=0.53, groove_depth=1.6,
                 race_thk=1.5, race_width=8., cage_thk=1.2, cage_width=5.,
                 pocket_clear=0.3, pitch_factor=2.1):
        self.d = ball
        self.Rb = ball_circle / 2.
        self.plate_r = plate_dia / 2.
        self.plate_thk = plate_thk
        self.conf = groove_conformity            # groove radius / ball dia
        self.groove_depth = groove_depth
        self.race_thk = race_thk
        self.race_w = race_width
        self.cage_thk = cage_thk
        self.cage_w = cage_width
        self.pocket = ball + pocket_clear
        # ball count: spacing about pitch_factor x ball diameter
        self.n = int(2 * math.pi * self.Rb / (pitch_factor * ball))
        self.gap = ball - groove_depth          # plate underside -> race top

    def groove(self):
        """Gothic arch: two arcs of radius conf*d whose centres are offset so
        the ball touches each at 45 deg (2 contact points)."""
        rg = self.conf * self.d
        rb = self.d / 2.
        off = (rg - rb) * math.sin(math.radians(45))
        return rg, off

    def report(self):
        rg, off = self.groove()
        circ = 2 * math.pi * self.Rb
        return "\n".join([
            "Orva bed ball race",
            "  balls: %d x %.1f mm chrome steel (G25 or better)" % (self.n,
                                                                    self.d),
            "  ball circle: dia %.1f mm (circumference %.1f mm, pitch %.2f mm)"
            % (2 * self.Rb, circ, circ / self.n),
            "  hot plate: dia %.0f mm x %.0f mm; groove in its underside on "
            "the ball circle:" % (2 * self.plate_r, self.plate_thk),
            "     gothic arch, two R%.2f mm arcs, centres %.3f mm either side "
            "of the ball centreline, %.2f mm deep" % (rg, off,
                                                      self.groove_depth),
            "  base: flat-bottom channel %.1f mm wide x %.2f mm deep on the "
            "ball circle, holding the %.1f mm stainless race ring"
            % (self.race_w + 0.4, self.race_thk, self.race_thk),
            "  plate underside sits %.2f mm above the race ring (and the "
            "base ledge, if flush)" % self.gap,
            "  race ring: ID %.1f / OD %.1f mm, %.1f mm 304 stainless"
            % (2 * self.Rb - self.race_w, 2 * self.Rb + self.race_w,
               self.race_thk),
            "  cage: ID %.1f / OD %.1f mm, %.1f mm stainless, %d pockets "
            "dia %.1f" % (2 * self.Rb - self.cage_w, 2 * self.Rb + self.cage_w,
                          self.cage_thk, self.n, self.pocket),
            "  hub: 6806-2RS bearing (30 x 42 x 7) around the slip ring for "
            "radial location; wave-spring stack under the hub nut for preload",
        ])


# ---------------------------------------------------------------- files

def dxf(path, circles, polys=()):
    out = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4",
           "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for (x, y, r) in circles:
        out += ["0", "CIRCLE", "8", "CUT", "10", "%.4f" % x, "20", "%.4f" % y,
                "40", "%.4f" % r]
    for pts in polys:
        out += ["0", "POLYLINE", "8", "CUT", "66", "1", "70", "1"]
        for (x, y) in pts:
            out += ["0", "VERTEX", "8", "CUT", "10", "%.4f" % x,
                    "20", "%.4f" % y]
        out += ["0", "SEQEND", "8", "CUT"]
    out += ["0", "ENDSEC", "0", "EOF"]
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")


def write_race_ring(r, path):
    dxf(path, [(0, 0, r.Rb + r.race_w / 2.), (0, 0, r.Rb - r.race_w / 2.)])


def write_cage(r, path):
    circles = [(0, 0, r.Rb + r.cage_w / 2.), (0, 0, r.Rb - r.cage_w / 2.)]
    for i in range(r.n):
        a = 2 * math.pi * i / r.n
        circles.append((r.Rb * math.cos(a), r.Rb * math.sin(a),
                        r.pocket / 2.))
    dxf(path, circles)


def write_section_svg(r, path):
    """Cross-section through the race at 10 px/mm, for the machinist."""
    S = 10.
    rg, off = r.groove()
    w, h = 40., 20.
    cx, cy = w / 2., 8.                       # ball centre (mm, y down)
    under = cy - r.d / 2. + r.groove_depth    # plate underside
    top = under - r.plate_thk
    base_top = cy + r.d / 2.                  # race ring top = ball bottom
    def P(x, y): return "%.1f,%.1f" % (x * S, y * S)
    parts = []
    # hot plate
    parts.append('<rect x="0" y="%.1f" width="%.1f" height="%.1f" '
                 'fill="#b8c0c8" stroke="#333"/>' % (top * S, w * S,
                                                    r.plate_thk * S))
    # gothic-arch groove: the left half is an arc centred right of the ball
    # centre and vice versa, meeting in a slight point at the top
    pts = []
    for k in range(-200, 201):
        x = cx + k * (rg + off) / 200.
        ccx = cx + off if x <= cx else cx - off
        dx = x - ccx
        if abs(dx) > rg:
            continue
        y = (cy - off) - math.sqrt(rg * rg - dx * dx)
        if y <= under:
            pts.append((x, y))
    groove = [(pts[0][0], under)] + pts + [(pts[-1][0], under)]
    parts.append('<polygon points="%s" fill="white" stroke="#333"/>'
                 % " ".join(P(x, y) for x, y in groove))
    # base, channel and race ring
    parts.append('<rect x="0" y="%.1f" width="%.1f" height="%.1f" '
                 'fill="#d8dde2" stroke="#333"/>' % (base_top * S, w * S,
                                                    (h - base_top) * S))
    ch = r.race_w + 0.4
    parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                 'fill="white" stroke="#333"/>' % ((cx - ch / 2) * S,
                                                  base_top * S, ch * S,
                                                  r.race_thk * S))
    parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                 'fill="#8fa9c4" stroke="#333"/>' % ((cx - r.race_w / 2) * S,
                                                    base_top * S,
                                                    r.race_w * S,
                                                    r.race_thk * S))
    parts.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#6b7480" '
                 'stroke="#222"/>' % (cx * S, cy * S, r.d / 2 * S))
    for (x, y, t) in [(1, top + 2.2, "hot plate underside: gothic-arch "
                       "groove, %.1f mm deep" % r.groove_depth),
                      (1, base_top + r.race_thk + 3.5, "base: flat channel "
                       "+ %.1f mm stainless race ring" % r.race_thk),
                      (cx + r.d / 2 + 1, cy + 0.5, "%.0f mm ball" % r.d),
                      (1, under + 1.6, "gap %.1f mm" % r.gap)]:
        parts.append('<text x="%.1f" y="%.1f" font-family="sans-serif" '
                     'font-size="13">%s</text>' % (x * S, y * S, t))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" '
           'height="%.0f" viewBox="0 0 %.0f %.0f"><rect width="100%%" '
           'height="100%%" fill="white"/>%s</svg>\n'
           % (w * S, h * S, w * S, h * S, "".join(parts)))
    with open(path, "w") as f:
        f.write(svg)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--ball", type=float, default=4.0)
    ap.add_argument("--ball-circle", type=float, default=271.)
    ap.add_argument("--plate-dia", type=float, default=280.)
    a = ap.parse_args()
    r = BedRace(ball=a.ball, ball_circle=a.ball_circle, plate_dia=a.plate_dia)
    write_race_ring(r, "orva_race_ring.dxf")
    write_cage(r, "orva_race_cage.dxf")
    write_section_svg(r, "orva_race_section.svg")
    print(r.report())
    print("  wrote orva_race_ring.dxf, orva_race_cage.dxf, "
          "orva_race_section.svg")


if __name__ == "__main__":
    main()
