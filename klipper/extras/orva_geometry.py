# Orva geometry: pure math shared by the kinematics, the motion transform,
# leveling, flow test and wiper modules.  No Klipper imports, so it can be
# unit tested on any machine.
#
# Coordinates are the BED frame (x, y in mm), the frame the slicer uses.
# The nozzle always sits on the arm's line; a point (x, y) is printed by
# turning the bed to angle phi and moving the arm to signed distance r:
#
#     (x, y) = r * (cos(phi), sin(phi))
#
# Every point has two representations: (phi, +h) and (phi + pi, -h), where
# h = |(x, y)|.  The second ("behind center") is only possible while
# h <= reach, the distance the arm can travel past center.
#
# Copyright (C) 2026  Orva contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import math

EPS_POINT = 1e-3    # mm: a point this close to center counts as center
EPS_LINE = 1e-4     # mm: a move whose line passes this close is "radial"
# Bed angle changes at center smaller than this are absorbed instead of
# pivoting (well under half a bed microstep, so no step is generated)
PIVOT_MIN = 5e-5    # rad
TWO_PI = 2. * math.pi


def wrap(a):
    """Wrap an angle to (-pi, pi]."""
    a = math.fmod(a, TWO_PI)
    if a > math.pi:
        a -= TWO_PI
    elif a <= -math.pi:
        a += TWO_PI
    return a


def hypot2(p):
    return math.hypot(p[0], p[1])


def line_distance(p0, p1):
    """Distance from center to the infinite line through p0, p1."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    if L < 1e-12:
        return hypot2(p0)
    return abs(p0[0] * dy - p0[1] * dx) / L


def closest_param(p0, p1):
    """Parameter t (0..1, unclamped) of the point on p0->p1 closest to
    center."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-24:
        return 0.
    return -(p0[0] * dx + p0[1] * dy) / L2


def segment_min_distance(p0, p1):
    """Closest distance from center to the segment p0..p1."""
    t = min(1., max(0., closest_param(p0, p1)))
    return math.hypot(p0[0] + (p1[0] - p0[0]) * t,
                      p0[1] + (p1[1] - p0[1]) * t)


######################################################################
# Representation state (mirrors kin_orva_polar.c exactly)
######################################################################

class RepState:
    """Which way the arm is reaching (sign) and the bed angle (hint).

    sign = +1: normal, the arm reaches out on its own side of center.
    sign = -1: the arm has passed center and points 'behind' it.
    hint: the current bed angle; only used to resolve the angle when the
    nozzle is exactly at center, where any bed angle is valid."""
    __slots__ = ('sign', 'hint')

    def __init__(self, sign=1, hint=0.):
        self.sign = 1 if sign >= 0 else -1
        self.hint = hint

    def copy(self):
        return RepState(self.sign, self.hint)

    def angle_of(self, p):
        """Bed angle that puts point p under the nozzle in this state."""
        if hypot2(p) < EPS_POINT:
            return self.hint
        return math.atan2(self.sign * p[1], self.sign * p[0])

    def arm_of(self, p):
        return self.sign * hypot2(p)

    def __repr__(self):
        return "RepState(sign=%d, hint=%.4f)" % (self.sign, self.hint)


class Decision:
    """How one straight XY move is executed.

    radial=True: the bed angle stays fixed at phi and the arm slides along
    u = (cos phi, sin phi) (possibly through center); arm r = p . u.
    radial=False: general move, angle = atan2(sign*y, sign*x), r = sign*h."""
    __slots__ = ('radial', 'phi', 'sign')

    def __init__(self, radial, phi, sign):
        self.radial, self.phi, self.sign = radial, phi, sign

    def arm(self, p):
        if self.radial:
            return p[0] * math.cos(self.phi) + p[1] * math.sin(self.phi)
        return self.sign * hypot2(p)

    def angle(self, p):
        if self.radial:
            return self.phi
        return math.atan2(self.sign * p[1], self.sign * p[0])


def decide(state, p0, p1, reach):
    """Decide the representation of the move p0->p1 given the state at its
    start.  Returns (Decision, new_state, ok) where ok=False means the move
    cannot be executed continuously (the caller must route around it).
    This is the same rule as orva_decide() in kin_orva_polar.c."""
    h0 = hypot2(p0)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    if L < 1e-12:
        return Decision(False, state.hint, state.sign), state.copy(), True
    wx, wy = dx / L, dy / L
    h1 = hypot2(p1)
    ok = True
    if h0 < EPS_POINT:
        # Starting at center: any bed angle is valid.  Pick the one closest
        # to the current bed angle; behind-center only within reach.
        ang_pos = math.atan2(wy, wx)
        ang_neg = ang_pos + math.pi
        can_neg = h1 <= reach + EPS_POINT
        if can_neg and abs(wrap(ang_neg - state.hint)) < abs(
                wrap(ang_pos - state.hint)):
            phi = ang_neg
        else:
            phi = ang_pos
        if abs(wrap(phi - state.hint)) > PIVOT_MIN:
            ok = False      # would need an instant bed turn at center
        dec = Decision(True, phi, 1)
    elif abs(p0[0] * wy - p0[1] * wx) < EPS_LINE:
        # Radial move along the arm's line (may pass through center)
        s = state.sign
        phi = math.atan2(s * p0[1], s * p0[0])
        dec = Decision(True, phi, s)
    else:
        dec = Decision(False, 0., state.sign)
        if state.sign < 0 and h1 > reach + EPS_POINT:
            ok = False      # behind center but leaving the reach window
    # End state
    if dec.radial:
        r_end = dec.arm(p1)
        if r_end < -(reach + EPS_POINT):
            ok = False
        if abs(r_end) < EPS_POINT:
            new = RepState(1, dec.phi)
        else:
            new = RepState(1 if r_end > 0. else -1, dec.phi)
    else:
        new = RepState(state.sign,
                       math.atan2(state.sign * p1[1], state.sign * p1[0]))
    return dec, new, ok


######################################################################
# Speed limit near center
######################################################################

def center_speed_limit(p0, p1, omega_max, alpha_max):
    """Max speed / accel for a straight move so the bed's turn rate stays
    under omega_max (rad/s) and its angular accel under alpha_max.

    For a straight line passing d from center, at distance r the bed turns
    at  omega = v * d / r^2.  It peaks at the segment's closest point, so a
    short segment only has to slow for its own closest point.  Radial moves
    (d ~ 0) need no slowing at all.  Returns None when no limit applies."""
    d = line_distance(p0, p1)
    if d < EPS_LINE:
        return None
    rmin = max(segment_min_distance(p0, p1), d, 1e-6)
    v = omega_max * rmin * rmin / d
    a = alpha_max * rmin * rmin / d
    return v, a


######################################################################
# Motion planning for the G-code transform
######################################################################

class MotionConfig:
    def __init__(self, reach=25., snap=0.3, split_radius=30.,
                 split_len=2., min_split=0.2):
        self.reach = reach              # arm travel past center (mm)
        self.snap = snap                # lines passing closer than this
                                        # are routed exactly through center
        self.split_radius = split_radius
        self.split_len = split_len
        self.min_split = min_split


def _lerp(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(len(a))]


def split_points(p0, p1, cfg):
    """Fractions (0..1] to split p0->p1 at so each piece near center is
    short.  The speed limit is applied per piece, so only pieces right at
    the closest point slow down."""
    if segment_min_distance(p0, p1) >= cfg.split_radius:
        return [1.]
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if L <= cfg.min_split:
        return [1.]
    out, t = [], 0.
    while t < 1. - 1e-9:
        p = _lerp(p0, p1, t)
        r = hypot2(p)
        step = cfg.split_len if r >= cfg.split_radius else max(
            cfg.min_split, min(cfg.split_len, 0.25 * r))
        t = min(1., t + step / L)
        out.append(t)
    return out


def plan_xy(state, p0, p1, cfg, extruding):
    """Turn one G-code XY move into executable steps.

    Returns (steps, new_state).  Steps, executed in order:
      ('line', t)        go to the point at fraction t of the original move
                         (E and Z interpolate by t)
      ('center', t)      go to exact center, with E and Z at fraction t
      ('to', (x, y))     travel-only detour point (E unchanged, Z unchanged)
      ('pivot', dphi)    turn the bed by dphi with the nozzle at center
    Every resulting move can be run by the C kinematics without an instant
    bed turn."""
    reach = cfg.reach
    st = state.copy()
    steps = []
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if L < 1e-9:
        return [('line', 1.)], st

    def leave_center(target, t, travel, allow_neg=True):
        # Nozzle is at center: pick the bed angle for heading to target,
        # pivoting first if it isn't the current one.
        nonlocal st
        ang_pos = math.atan2(target[1], target[0])
        ang_neg = ang_pos + math.pi
        can_neg = allow_neg and hypot2(target) <= reach + EPS_POINT
        dpos = wrap(ang_pos - st.hint)
        dneg = wrap(ang_neg - st.hint)
        if can_neg and abs(dneg) < abs(dpos):
            phi, dphi, sign = ang_neg, dneg, -1
        else:
            phi, dphi, sign = ang_pos, dpos, 1
        if abs(dphi) > PIVOT_MIN:
            steps.append(('pivot', dphi))
        st = RepState(sign, phi)
        steps.append(('to', tuple(target)) if travel else ('line', t))

    # 1) Starting at center
    if hypot2(p0) < EPS_POINT:
        leave_center(p1, 1., False)
        return steps, st

    d = line_distance(p0, p1)
    tc = closest_param(p0, p1)
    passes_center = d < cfg.snap and 0. < tc < 1.

    # 2) Behind center and heading out of reach: come back to center along
    #    the arm's own line (no bed turn needed), then carry on normally.
    if st.sign < 0 and hypot2(p1) > reach + EPS_POINT and not passes_center:
        steps.append(('to', (0., 0.)))
        st = RepState(1, st.hint)
        if not extruding:
            leave_center(p1, 1., False)
            return steps, st
        # Printing: go back out to the start point on the normal side,
        # then print the line from there.
        leave_center(p0, 0., True, allow_neg=False)

    # 3) Line passes (almost) through center: route exactly through it
    if passes_center:
        st = RepState(1, st.angle_of(p0))
        steps.append(('center', tc))
        leave_center(p1, 1., False)
        return steps, st

    # 4) General move, split into short pieces near center
    dec, new, ok = decide(st, p0, p1, reach)
    if not ok:
        raise ValueError("Orva: move %s -> %s can't be executed" % (
            tuple(p0), tuple(p1)))
    for t in split_points(p0, p1, cfg):
        steps.append(('line', t))
    return steps, new


######################################################################
# Leveling: probe pattern and surface fit
######################################################################

EDGE_ANGLES = [k * 60. for k in range(6)]
# Center points in probe order: on the last edge point's line (arm just
# moves in), directly behind it past center (no bed turn), then a quarter
# turn for the third.
CENTER_ANGLES = [300., 120., 210.]


def probe_pattern(a0, edge_r=86., center_r=18.):
    """9 probe points starting at bed angle a0 (radians), in probe order."""
    pts = []
    for d in EDGE_ANGLES:
        a = a0 + math.radians(d)
        pts.append((edge_r * math.cos(a), edge_r * math.sin(a)))
    for d in CENTER_ANGLES:
        a = a0 + math.radians(d)
        pts.append((center_r * math.cos(a), center_r * math.sin(a)))
    return pts


def surface_basis(x, y, n, scale=100.):
    u, v = x / scale, y / scale
    b = [1., u, v, u * u + v * v]
    if n > 4:
        b += [u * u - v * v, u * v]
    return b


def solve_linear(A, y):
    n = len(y)
    A = [row[:] for row in A]
    y = y[:]
    for i in range(n):
        pv = max(range(i, n), key=lambda r: abs(A[r][i]))
        if abs(A[pv][i]) < 1e-12:
            raise ValueError("singular fit")
        A[i], A[pv] = A[pv], A[i]
        y[i], y[pv] = y[pv], y[i]
        for r in range(i + 1, n):
            f = A[r][i] / A[i][i]
            for c in range(i, n):
                A[r][c] -= f * A[i][c]
            y[r] -= f * y[i]
    x = [0.] * n
    for i in range(n - 1, -1, -1):
        t = y[i] - sum(A[i][c] * x[c] for c in range(i + 1, n))
        x[i] = t / A[i][i]
    return x


class Surface:
    """Least-squares bed surface: tilt + dome, plus saddle + twist once there
    are 12 or more points."""
    def __init__(self, coeffs, scale=100.):
        self.coeffs = list(coeffs)
        self.scale = scale

    @classmethod
    def fit(cls, points, scale=100.):
        n = 6 if len(points) >= 12 else 4
        if len(points) < n:
            raise ValueError("need at least %d points" % n)
        A = [[0.] * n for _ in range(n)]
        y = [0.] * n
        for (px, py, pz) in points:
            b = surface_basis(px, py, n, scale)
            for r in range(n):
                y[r] += b[r] * pz
                for c in range(n):
                    A[r][c] += b[r] * b[c]
        return cls(solve_linear(A, y), scale)

    def z(self, x, y):
        b = surface_basis(x, y, len(self.coeffs), self.scale)
        return sum(bi * ci for bi, ci in zip(b, self.coeffs))

    def residuals(self, points):
        return [pz - self.z(px, py) for (px, py, pz) in points]


######################################################################
# Flow test outline
######################################################################

def convex_hull(points):
    pts = sorted(set((float(p[0]), float(p[1])) for p in points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]     # counter-clockwise


def offset_outline(points, offset, max_radius=None, corner_step_deg=12.,
                   seg_len=2.):
    """Closed path `offset` mm outside the convex hull of points, with
    rounded corners, resampled to <= seg_len, clamped inside max_radius.
    Returns a list of (x, y) with the first point repeated at the end."""
    H = convex_hull(points)
    if len(H) < 3:
        raise ValueError("outline needs at least 3 distinct points")
    n = len(H)
    ring = []
    for i in range(n):
        p, a, b = H[i], H[i - 1], H[(i + 1) % n]
        t0 = math.atan2(p[1] - a[1], p[0] - a[0]) - math.pi / 2.
        t1 = math.atan2(b[1] - p[1], b[0] - p[0]) - math.pi / 2.
        dt = (t1 - t0) % TWO_PI
        k = max(1, int(math.ceil(math.degrees(dt) / corner_step_deg)))
        for q in range(k + 1):
            t = t0 + dt * q / k
            ring.append((p[0] + offset * math.cos(t),
                         p[1] + offset * math.sin(t)))
    path = [ring[0]]
    for A in ring[1:] + [ring[0]]:
        B = path[-1]
        Ld = math.hypot(A[0] - B[0], A[1] - B[1])
        m = int(math.ceil(Ld / seg_len))
        for q in range(1, m):
            path.append((B[0] + (A[0] - B[0]) * q / m,
                         B[1] + (A[1] - B[1]) * q / m))
        path.append(A)
    if max_radius is not None:
        out = []
        for (x, y) in path:
            r = math.hypot(x, y)
            if r > max_radius:
                x, y = x * max_radius / r, y * max_radius / r
            out.append((x, y))
        path = out
    return path


def path_length(path):
    return sum(math.hypot(path[i + 1][0] - path[i][0],
                          path[i + 1][1] - path[i][1])
               for i in range(len(path) - 1))


######################################################################
# Wiper: find a bed angle where the brush can rise safely
######################################################################

def polygon_angle_span(poly, min_radius):
    """Angular intervals (start, width) in radians covered by the parts of
    a polygon that reach beyond min_radius.  Conservative: uses the angle
    range of all vertices beyond min_radius plus their neighbors."""
    pts = [p for p in poly if hypot2(p) > min_radius]
    if not pts:
        return None
    angs = sorted(math.atan2(p[1], p[0]) % TWO_PI for p in pts)
    # largest gap between consecutive angles marks the outside of the span
    gaps = [(angs[(i + 1) % len(angs)] - angs[i]) % TWO_PI
            for i in range(len(angs))]
    if len(angs) == 1:
        return (angs[0], 0.)
    i = max(range(len(gaps)), key=lambda k: gaps[k])
    start = angs[(i + 1) % len(angs)]
    width = TWO_PI - gaps[i]
    return (start, width)


def clear_wipe_angle(current, polygons, min_radius, margin):
    """Bed angle closest to `current` at which no polygon that overhangs
    past min_radius is under the arm (within `margin` radians)."""
    spans = []
    for poly in polygons:
        s = polygon_angle_span(poly, min_radius)
        if s is not None:
            spans.append(((s[0] - margin) % TWO_PI, s[1] + 2. * margin))

    def blocked(a):
        for (st, w) in spans:
            if (a - st) % TWO_PI <= w:
                return True
        return False
    if not blocked(current):
        return current
    for k in range(1, 361):
        for sgn in (1, -1):
            a = current + sgn * math.radians(k)
            if not blocked(a % TWO_PI):
                return a
    return None
