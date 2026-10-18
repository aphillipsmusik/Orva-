#!/usr/bin/env python3
"""Generate Orva's laser-cut internal bed ring gear (DXF for cutting, SVG to
look at) and check that it meshes with its pinion.

    python3 make_ring_gear.py              # writes orva_ring_gear.dxf / .svg
    python3 make_ring_gear.py --check      # also runs the mesh check (needs shapely)

Default: module 2, 120 teeth, 20 deg pressure angle -> 240 mm pitch circle,
fitting under the 266 mm bed plate (256 mm print surface) with a bolt band,
driven by a stock module 2, 16 tooth steel pinion (centre distance 104 mm).
A 20T -> 60T GT2 belt stage between the motor and the pinion makes the total
reduction 120:16 x 60:20 = 22.5:1.

Why module 2: a laser can't cut a slot narrower than about half the plate
thickness.  An internal gear's narrowest cut is at the bottom of each tooth
space; at module 1 that is ~0.6 mm, too fine for any useful steel plate.
At module 2, ending each space in a full-radius root keeps every cut at least
`min_gap` wide (1.6 mm), which suits 3 mm (0.120") steel.

Only the standard library is needed to generate the files.
"""
import argparse, math

def inv(a):
    return math.tan(a) - a


class RingGear:
    def __init__(self, module=2.0, teeth=120, pressure_deg=20., backlash=0.20,
                 min_gap=1.6, outer_dia=262., bolt_circle_dia=254.,
                 bolt_holes=8, bolt_dia=3.4, pinion_teeth=16, flank_pts=12):
        self.m, self.z = module, teeth
        self.a = math.radians(pressure_deg)
        self.rp = module * teeth / 2.
        self.rb = self.rp * math.cos(self.a)
        self.r_tip = self.rp - module                 # internal: tips inward
        self.backlash = backlash
        self.min_gap = min_gap
        self.outer_r = outer_dia / 2.
        self.bolt_r = bolt_circle_dia / 2.
        self.bolt_holes, self.bolt_dia = bolt_holes, bolt_dia
        self.zp = pinion_teeth
        self.center_dist = module * (teeth - pinion_teeth) / 2.
        self.flank_pts = flank_pts
        # pinion tip must clear the root: need root >= c + rp_pinion + m + 0.25m
        self.root_needed = self.center_dist + module * pinion_teeth / 2. \
            + module * 1.25
        if self.r_tip <= self.rb:
            raise ValueError("tip circle inside base circle")

    def half_angle(self, r):
        """Angular half-width of a tooth SPACE at radius r (involute flanks)."""
        s_p = math.pi * self.m / 2. + self.backlash     # space at pitch circle
        ar = math.acos(self.rb / r)
        return s_p / (2. * self.rp) + inv(self.a) - inv(ar)

    def flank_end_radius(self):
        """Radius where the space has narrowed to min_gap."""
        lo, hi = self.rp, self.rp + 2. * self.m
        for _ in range(60):
            mid = (lo + hi) / 2.
            if 2. * mid * math.sin(self.half_angle(mid)) > self.min_gap:
                lo = mid
            else:
                hi = mid
        return lo

    def space(self, k):
        """Closed outline of tooth space k (points, counter-clockwise)."""
        th = 2. * math.pi * k / self.z
        r1 = self.flank_end_radius()
        rs = [self.r_tip + (r1 - self.r_tip) * i / self.flank_pts
              for i in range(self.flank_pts + 1)]
        right = [(r * math.cos(th - self.half_angle(r)),
                  r * math.sin(th - self.half_angle(r))) for r in rs]
        left = [(r * math.cos(th + self.half_angle(r)),
                 r * math.sin(th + self.half_angle(r))) for r in rs]
        # full-radius root joining the flank ends, bulging outward
        (x1, y1), (x2, y2) = right[-1], left[-1]
        cx, cy = (x1 + x2) / 2., (y1 + y2) / 2.
        rr = math.hypot(x2 - x1, y2 - y1) / 2.
        a0 = math.atan2(y1 - cy, x1 - cx)
        root = []
        for i in range(1, 12):
            a = a0 + math.pi * i / 12.
            root.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        # check the bulge goes outward (away from the centre)
        if math.hypot(*root[5]) < math.hypot(cx, cy):
            root = [(2 * cx - x, 2 * cy - y) for (x, y) in root]
        # tip land: arc on the tip circle back to the start
        return right + root + list(reversed(left))

    def inner_outline(self):
        """The ring's inner boundary: tooth tips and spaces, one closed loop."""
        pts = []
        for k in range(self.z):
            sp = self.space(k)
            pts.extend(sp)
            # tip land arc to the next space
            th = 2. * math.pi * k / self.z
            a0 = th + self.half_angle(self.r_tip)
            a1 = 2. * math.pi * (k + 1) / self.z - self.half_angle(self.r_tip)
            for i in range(1, 4):
                a = a0 + (a1 - a0) * i / 4.
                pts.append((self.r_tip * math.cos(a), self.r_tip * math.sin(a)))
        return pts

    def max_root_radius(self):
        return max(math.hypot(*p) for p in self.space(0))

    def holes(self):
        return [(self.bolt_r * math.cos(2 * math.pi * i / self.bolt_holes
                                        + math.pi / self.bolt_holes),
                 self.bolt_r * math.sin(2 * math.pi * i / self.bolt_holes
                                        + math.pi / self.bolt_holes))
                for i in range(self.bolt_holes)]

    def report(self):
        r1 = self.flank_end_radius()
        web_in = self.bolt_r - self.bolt_dia / 2. - self.max_root_radius()
        web_out = self.outer_r - self.bolt_r - self.bolt_dia / 2.
        return "\n".join([
            "Orva bed ring gear",
            "  module %.2f, %d teeth, %.0f deg pressure angle"
            % (self.m, self.z, math.degrees(self.a)),
            "  pitch dia %.1f mm, tip (inner) dia %.1f mm, root dia %.2f mm"
            % (2 * self.rp, 2 * self.r_tip, 2 * self.max_root_radius()),
            "  root needed for pinion tip clearance: dia %.2f mm (%s)"
            % (2 * self.root_needed, "ok" if self.max_root_radius()
               >= self.root_needed - 1e-6 else "TOO SHALLOW"),
            "  narrowest cut %.2f mm (laser: plate up to %.1f mm thick)"
            % (self.min_gap, 2 * self.min_gap),
            "  outer dia %.1f mm, %d x %.1f mm holes on %.1f mm circle"
            % (2 * self.outer_r, self.bolt_holes, self.bolt_dia,
               2 * self.bolt_r),
            "  webs around holes: %.2f mm inside, %.2f mm outside"
            % (web_in, web_out),
            "  pinion: module %.2f, %d teeth, centre distance %.2f mm, "
            "ratio %d:%d = %.3f:1" % (self.m, self.zp, self.center_dist,
                                      self.z, self.zp, self.z / self.zp),
        ])


# ---------------------------------------------------------------- output

def write_dxf(g, path):
    """AutoCAD R12 DXF: closed POLYLINEs and CIRCLEs, millimetres."""
    out = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4",
           "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]

    def poly(pts):
        out.extend(["0", "POLYLINE", "8", "CUT", "66", "1", "70", "1"])
        for (x, y) in pts:
            out.extend(["0", "VERTEX", "8", "CUT", "10", "%.4f" % x,
                        "20", "%.4f" % y])
        out.extend(["0", "SEQEND", "8", "CUT"])

    def circle(x, y, r):
        out.extend(["0", "CIRCLE", "8", "CUT", "10", "%.4f" % x,
                    "20", "%.4f" % y, "40", "%.4f" % r])
    circle(0., 0., g.outer_r)
    poly(g.inner_outline())
    for (x, y) in g.holes():
        circle(x, y, g.bolt_dia / 2.)
    out.extend(["0", "ENDSEC", "0", "EOF"])
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")


def write_svg(g, path):
    R = g.outer_r + 2
    pts = " ".join("%.3f,%.3f" % (x, -y) for (x, y) in g.inner_outline())
    holes = "".join('<circle cx="%.3f" cy="%.3f" r="%.3f"/>' % (x, -y,
                                                               g.bolt_dia / 2)
                    for (x, y) in g.holes())
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.1f %.1f %.1f '
           '%.1f" width="%.0fmm" height="%.0fmm"><g fill="#9aa3ab" '
           'fill-rule="evenodd" stroke="#333" stroke-width="0.1"><path d="'
           % (-R, -R, 2 * R, 2 * R, 2 * R, 2 * R))
    # outer circle + inner tooth outline as one even-odd path
    svg += "M %.3f 0 A %.3f %.3f 0 1 0 %.3f 0 A %.3f %.3f 0 1 0 %.3f 0 Z " % (
        g.outer_r, g.outer_r, g.outer_r, -g.outer_r, g.outer_r, g.outer_r,
        g.outer_r)
    svg += "M " + pts.replace(" ", " L ") + ' Z"/></g><g fill="white" ' \
        'stroke="#333" stroke-width="0.1">' + holes + "</g></svg>\n"
    with open(path, "w") as f:
        f.write(svg)


# ---------------------------------------------------------------- mesh check

def pinion_outline(g, n=10):
    """Standard external involute pinion (module m, zp teeth), with radial
    flanks below the base circle and a root arc."""
    m, zp, a = g.m, g.zp, g.a
    rp = m * zp / 2.
    rb = rp * math.cos(a)
    ra = rp + m
    rf = rp - 1.25 * m
    t_p = math.pi * m / 2.

    def half(r):
        r = max(r, rb)
        return t_p / (2 * rp) + inv(a) - inv(math.acos(rb / r))
    pts = []
    for k in range(zp):
        th = 2 * math.pi * k / zp
        r_start = max(rb, rf)
        rs = [r_start + (ra - r_start) * i / n for i in range(n + 1)]
        # root arc from the previous tooth's left flank to this right flank
        a_prev = th - 2 * math.pi / zp + half(r_start)
        a_this = th - half(r_start)
        for i in range(6):
            t = a_prev + (a_this - a_prev) * i / 5.
            pts.append((rf * math.cos(t), rf * math.sin(t)))
        right = [(r * math.cos(th - half(r)), r * math.sin(th - half(r)))
                 for r in rs]
        left = [(r * math.cos(th + half(r)), r * math.sin(th + half(r)))
                for r in reversed(rs)]
        pts.extend(right + left)
        # radial flank down to the root circle
        pts.append((rf * math.cos(th + half(r_start)),
                    rf * math.sin(th + half(r_start))))
    return pts


def mesh_check(g, steps=400):
    from shapely.geometry import Polygon, Point
    from shapely import affinity
    ring = Point(0, 0).buffer(g.outer_r, 256).difference(
        Polygon(g.inner_outline()))
    pin = Polygon(pinion_outline(g))
    worst = 0.
    clear = 1e9
    pitch = 2 * math.pi / g.z
    for i in range(steps):
        th = pitch * i / steps          # one tooth pitch of ring rotation
        ring_r = affinity.rotate(ring, th, origin=(0, 0), use_radians=True)
        # internal gearing: both turn the same way, pinion faster by z/zp
        pin_r = affinity.rotate(pin, th * g.z / g.zp, origin=(0, 0),
                                use_radians=True)
        pin_r = affinity.translate(pin_r, xoff=g.center_dist)
        overlap = ring_r.intersection(pin_r).area
        worst = max(worst, overlap)
        clear = min(clear, ring_r.distance(pin_r) if overlap == 0 else 0.)
    return worst, clear


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--module", type=float, default=2.0)
    ap.add_argument("--teeth", type=int, default=120)
    ap.add_argument("--pinion-teeth", type=int, default=16)
    ap.add_argument("--min-gap", type=float, default=1.6)
    ap.add_argument("--backlash", type=float, default=0.20)
    ap.add_argument("--outer-dia", type=float, default=262.)
    ap.add_argument("--bolt-circle-dia", type=float, default=254.)
    ap.add_argument("--out", default="orva_ring_gear")
    ap.add_argument("--check", action="store_true",
                    help="simulate meshing with the pinion (needs shapely)")
    a = ap.parse_args()
    g = RingGear(a.module, a.teeth, backlash=a.backlash, min_gap=a.min_gap,
                 outer_dia=a.outer_dia, bolt_circle_dia=a.bolt_circle_dia,
                 pinion_teeth=a.pinion_teeth)
    write_dxf(g, a.out + ".dxf")
    write_svg(g, a.out + ".svg")
    print(g.report())
    print("  wrote %s.dxf and %s.svg" % (a.out, a.out))
    if a.check:
        worst, clear = mesh_check(g)
        print("  mesh check: max overlap %.4f mm^2, min clearance %.3f mm (%s)"
              % (worst, clear, "ok" if worst < 1e-3 else "INTERFERENCE"))


if __name__ == "__main__":
    main()
