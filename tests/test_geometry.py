"""Unit tests for orva_geometry (no Klipper needed)."""
import math, os, random, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'klipper', 'extras'))
import orva_geometry as og

REACH = 25.
CFG = og.MotionConfig(reach=REACH)


def execute(state, p0, p1, steps):
    """Run plan_xy steps through decide(), the same rule the C code uses.
    Returns the list of executed XY segments and the final state; fails if
    any segment would need an instant turn or exceed the reach."""
    pos = tuple(p0)
    st = state.copy()
    segs = []
    for s in steps:
        if s[0] == 'pivot':
            assert og.hypot2(pos) < og.EPS_POINT, "pivot away from center"
            st = og.RepState(st.sign, st.hint + s[1])
            continue
        if s[0] == 'line':
            t = s[1]
            q = (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)
        elif s[0] == 'center':
            q = (0., 0.)
        else:
            q = s[1]
        if math.hypot(q[0] - pos[0], q[1] - pos[1]) > 1e-9:
            dec, st, ok = og.decide(st, pos, q, REACH)
            assert ok, "unexecutable segment %s -> %s" % (pos, q)
            segs.append((pos, q))
        pos = q
    assert math.hypot(pos[0] - p1[0], pos[1] - p1[1]) < 1e-9
    return segs, st


class TestDecide(unittest.TestCase):
    def test_radial_through_center(self):
        st = og.RepState(1, 0.)
        dec, new, ok = og.decide(st, (18., 0.), (-18., 0.), REACH)
        self.assertTrue(ok and dec.radial)
        self.assertEqual(new.sign, -1)
        self.assertAlmostEqual(dec.arm((-18., 0.)), -18.)

    def test_radial_beyond_reach_rejected(self):
        st = og.RepState(1, 0.)
        dec, new, ok = og.decide(st, (50., 0.), (-50., 0.), REACH)
        self.assertFalse(ok)

    def test_behind_center_leaving_reach_rejected(self):
        st = og.RepState(-1, 0.)
        dec, new, ok = og.decide(st, (-10., 0.), (60., 40.), REACH)
        self.assertFalse(ok)

    def test_start_at_center_prefers_no_turn(self):
        st = og.RepState(1, 0.)
        # heading to (-10, 0): behind-center keeps the bed at angle 0
        dec, new, ok = og.decide(st, (0., 0.), (-10., 0.), REACH)
        self.assertTrue(ok)
        self.assertAlmostEqual(og.wrap(dec.phi), 0.)
        self.assertEqual(new.sign, -1)


class TestPlan(unittest.TestCase):
    def test_full_diameter_line_pivots_at_center(self):
        st = og.RepState(1, 0.)
        steps, new = og.plan_xy(st, (80., 0.), (-80., 0.), CFG, True)
        kinds = [s[0] for s in steps]
        self.assertIn('center', kinds)
        self.assertIn('pivot', kinds)
        piv = [s[1] for s in steps if s[0] == 'pivot'][0]
        self.assertAlmostEqual(abs(piv), math.pi)
        execute(st, (80., 0.), (-80., 0.), steps)

    def test_near_center_line_is_snapped(self):
        st = og.RepState(1, 0.)
        steps, new = og.plan_xy(st, (60., 0.1), (-10., -0.05), CFG, True)
        self.assertEqual(steps[0][0], 'center')
        execute(st, (60., 0.1), (-10., -0.05), steps)

    def test_leaving_behind_center_while_printing(self):
        st = og.RepState(-1, 0.)          # arm at -10 on the bed's 0 line
        p0, p1 = (-10., 0.), (40., 50.)
        steps, new = og.plan_xy(st, p0, p1, CFG, True)
        segs, fin = execute(st, p0, p1, steps)
        self.assertEqual(fin.sign, 1)
        # the printed piece is still exactly p0 -> p1
        lines = [s for s in steps if s[0] == 'line']
        self.assertAlmostEqual(lines[-1][1], 1.)

    def test_random_moves_always_executable(self):
        rnd = random.Random(7)
        st = og.RepState(1, 0.)
        p = (50., 0.)
        for i in range(3000):
            if rnd.random() < 0.3:
                # aim at or near center to stress the special cases
                a = rnd.uniform(-math.pi, math.pi)
                r = rnd.choice([0., 0.05, 0.2, 5., 18., 24.])
                q = (r * math.cos(a), r * math.sin(a))
                if rnd.random() < 0.5:
                    q = (-p[0] * rnd.uniform(0.1, 1.2),
                         -p[1] * rnd.uniform(0.1, 1.2))
            else:
                a = rnd.uniform(-math.pi, math.pi)
                r = rnd.uniform(0., 110.)
                q = (r * math.cos(a), r * math.sin(a))
            if math.hypot(q[0], q[1]) > 110.:
                continue
            steps, new = og.plan_xy(st, p, q, CFG, rnd.random() < 0.6)
            segs, fin = execute(st, p, q, steps)
            self.assertEqual(fin.sign, new.sign)
            self.assertAlmostEqual(og.wrap(fin.hint - new.hint), 0., places=6)
            st, p = new, q

    def test_split_near_center(self):
        pts = og.split_points((60., 1.), (-60., 1.), CFG)
        self.assertGreater(len(pts), 10)
        self.assertAlmostEqual(pts[-1], 1.)
        self.assertEqual(og.split_points((90., 0.), (0., 90.), CFG), [1.])


class TestSpeedLimit(unittest.TestCase):
    def test_radial_no_limit(self):
        self.assertIsNone(og.center_speed_limit((50., 0.), (-10., 0.), 6., 60.))

    def test_limit_grows_with_distance(self):
        v_close, _ = og.center_speed_limit((5., 1.), (-5., 1.), 6., 60.)
        v_far, _ = og.center_speed_limit((50., 1.), (40., 1.), 6., 60.)
        # line 1 mm from center: at its closest point the bed turns at
        # v * d / r^2 = v, so the cap (6 rad/s) allows 6 mm/s there
        self.assertAlmostEqual(v_close, 6.)
        self.assertGreater(v_far, 1000.)


class TestLevelFit(unittest.TestCase):
    def bed(self, x, y):
        return (0.06 * x / 100 - 0.045 * y / 100
                + 0.05 * (1 - (x * x + y * y) / 10000) - 0.02)

    def test_pattern(self):
        pts = og.probe_pattern(0.3)
        self.assertEqual(len(pts), 9)
        # center point 1 on the last edge point's line, point 2 behind it
        e5, c1, c2 = pts[5], pts[6], pts[7]
        self.assertAlmostEqual(math.atan2(e5[1], e5[0]),
                               math.atan2(c1[1], c1[0]))
        self.assertAlmostEqual(c1[0], -c2[0])
        self.assertAlmostEqual(c1[1], -c2[1])

    def test_fit_recovers_surface(self):
        P = [(x, y, self.bed(x, y)) for (x, y) in og.probe_pattern(0.)]
        s = og.Surface.fit(P)
        self.assertEqual(len(s.coeffs), 4)
        for (x, y) in [(0, 0), (50, -30), (-70, 20)]:
            self.assertAlmostEqual(s.z(x, y), self.bed(x, y), places=9)

    def test_memory_adds_terms(self):
        def bed2(x, y):
            return self.bed(x, y) + 0.03 * x * y / 10000
        P = []
        for a0 in (0., 0.5):
            P += [(x, y, bed2(x, y)) for (x, y) in og.probe_pattern(a0)]
        s = og.Surface.fit(P)
        self.assertEqual(len(s.coeffs), 6)
        self.assertAlmostEqual(s.z(40, 40), bed2(40, 40), places=9)


class TestOutline(unittest.TestCase):
    def test_offset_outline(self):
        sq = [(70, -10), (90, -10), (90, 10), (70, 10)]
        path = og.offset_outline(sq, 3.5, max_radius=96.8)
        self.assertEqual(path[0], path[-1])
        for (x, y) in path:
            self.assertLessEqual(math.hypot(x, y), 96.8 + 1e-9)
        # everything at least ~3.5 mm outside the square, except where the
        # bed edge clamps it
        for (x, y) in path:
            dx = max(70 - x, 0, x - 90)
            dy = max(-10 - y, 0, y - 10)
            if math.hypot(x, y) < 96.7:
                self.assertGreater(math.hypot(dx, dy), 3.4)


class TestWipe(unittest.TestCase):
    def test_clear_angle(self):
        # an overhanging part centered at angle 0
        poly = [(95, -10), (110, -10), (110, 10), (95, 10)]
        a = og.clear_wipe_angle(0., [poly], 98., math.radians(5))
        self.assertIsNotNone(a)
        self.assertGreater(abs(og.wrap(a)), math.radians(5))
        self.assertEqual(og.clear_wipe_angle(2.0, [poly], 98., 0.1), 2.0)


if __name__ == '__main__':
    unittest.main()
