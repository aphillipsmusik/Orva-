"""Drive the C kinematics with real Klipper trapq moves.

Needs a Klipper checkout: set KLIPPER_DIR (default ~/klipper).
Checks, for move sequences through and around center:
  * bed angle + arm position reproduce the commanded XY point everywhere
  * the bed angle never jumps (no instant turns)
  * the arm stays within [-reach, max]
  * results don't depend on which stepper evaluates first, or in what order
"""
import math, os, random, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'klipper', 'extras'))
import orva_geometry as og

KLIPPER = os.environ.get('KLIPPER_DIR', os.path.expanduser('~/klipper'))
CHELPER = os.path.join(KLIPPER, 'klippy', 'chelper')
REACH = 25.

def build():
    import cffi
    out = os.path.join(tempfile.mkdtemp(), 'h.so')
    srcs = [os.path.join(ROOT, 'klipper', 'chelper', 'kin_orva_polar.c'),
            os.path.join(HERE, 'c', 'harness.c'),
            os.path.join(CHELPER, 'trapq.c')]
    subprocess.check_call(['gcc', '-O2', '-shared', '-fPIC', '-I' + CHELPER,
                           '-o', out] + srcs + ['-lm'])
    ffi = cffi.FFI()
    ffi.cdef("""
        void *orva_polar_shared_alloc(double reach);
        void orva_polar_reset(void *sh, int sign, double hint);
        void *orva_polar_stepper_alloc(void *sh, char type);
        double orva_polar_test_calc(void *sk, void *m, double t);
        void *h_tq_new(void);
        void h_append(void *tq, double pt, double at, double ct, double dt,
                      double sx, double sy, double sz, double rx, double ry,
                      double rz, double sv, double cv, double acc);
        int h_moves(void *tq, void **out, int max);
        void h_move_info(void *m, double *o);
        void h_coord(void *m, double t, double *o);
        void h_set_tq(void *sk, void *tq);
        void h_set_cmd(void *sk, double v);
    """)
    return ffi, ffi.dlopen(out)

class Sim:
    def __init__(self, ffi, lib, start=(50., 0.)):
        self.ffi, self.lib = ffi, lib
        self.sh = lib.orva_polar_shared_alloc(REACH)
        self.bed = lib.orva_polar_stepper_alloc(self.sh, b'a')
        self.arm = lib.orva_polar_stepper_alloc(self.sh, b'r')
        self.tq = lib.h_tq_new()
        lib.h_set_tq(self.bed, self.tq)
        lib.h_set_tq(self.arm, self.tq)
        lib.orva_polar_reset(self.sh, 1, math.atan2(start[1], start[0]))
        self.start_angle = math.atan2(start[1], start[0])
        lib.h_set_cmd(self.bed, self.start_angle)
        self.pos = start
        self.t = 1.
    def line(self, x, y, v=100., a=2000.):
        dx, dy = x - self.pos[0], y - self.pos[1]
        L = math.hypot(dx, dy)
        # trapezoid: accel / cruise / decel phases (3 trapq moves)
        ta = v / a
        da = .5 * a * ta * ta
        if 2 * da > L:
            ta = math.sqrt(L / a); v = a * ta; da = L / 2.
        tc = (L - 2 * da) / v
        self.lib.h_append(self.tq, self.t, ta, tc, ta, self.pos[0],
                          self.pos[1], 0., dx / L, dy / L, 0., 0., v, a)
        self.t += 2 * ta + tc
        self.pos = (x, y)
    def moves(self):
        buf = self.ffi.new('void *[4096]')
        n = self.lib.h_moves(self.tq, buf, 4096)
        return [buf[i] for i in range(n)]
    def samples(self, order='forward', per_move=25):
        info = self.ffi.new('double[4]')
        pts = []
        for m in self.moves():
            self.lib.h_move_info(m, info)
            mt = info[1]
            for k in range(per_move + 1):
                pts.append((m, info[0] + mt * k / per_move, mt * k / per_move))
        return pts

def evaluate(sim, order):
    """Evaluate both steppers at every sample.  'order' controls which
    stepper/time is asked first, to prove decisions are order independent."""
    lib, ffi = sim.lib, sim.ffi
    pts = sim.samples()
    lib.h_set_cmd(sim.bed, sim.start_angle)
    res = {}
    seq = list(range(len(pts)))
    if order == 'arm_first_reversed':
        for i in reversed(seq):
            m, T, t = pts[i]
            res.setdefault(i, {})['arm'] = lib.orva_polar_test_calc(sim.arm, m, t)
        cmd = None
        for i in seq:
            m, T, t = pts[i]
            res[i]['bed'] = lib.orva_polar_test_calc(sim.bed, m, t)
            lib.h_set_cmd(sim.bed, res[i]['bed'])
    elif order == 'random':
        random.seed(5)
        sh = seq[:]; random.shuffle(sh)
        for i in sh:
            m, T, t = pts[i]
            res.setdefault(i, {})['arm'] = lib.orva_polar_test_calc(sim.arm, m, t)
        for i in seq:
            m, T, t = pts[i]
            res[i]['bed'] = lib.orva_polar_test_calc(sim.bed, m, t)
            lib.h_set_cmd(sim.bed, res[i]['bed'])
    else:
        for i in seq:
            m, T, t = pts[i]
            b = lib.orva_polar_test_calc(sim.bed, m, t)
            lib.h_set_cmd(sim.bed, b)
            a = lib.orva_polar_test_calc(sim.arm, m, t)
            res[i] = {'bed': b, 'arm': a}
    c = ffi.new('double[2]')
    out = []
    for i in seq:
        m, T, t = pts[i]
        lib.h_coord(m, t, c)
        out.append((T, c[0], c[1], res[i]['bed'], res[i]['arm']))
    return out

class TestCKinematics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(os.path.join(CHELPER, 'trapq.c')):
            raise unittest.SkipTest("set KLIPPER_DIR to a Klipper checkout")
        cls.ffi, cls.lib = build()

    def check(self, sim, max_jump=0.35):
        outs = [evaluate(sim, o) for o in ('forward', 'arm_first_reversed',
                                          'random')]
        for out in outs[1:]:
            for a, b in zip(outs[0], out):
                self.assertAlmostEqual(og.wrap(a[3] - b[3]), 0., places=9)
                self.assertAlmostEqual(a[4], b[4], places=9)
        prev = None
        for (T, x, y, phi, r) in outs[0]:
            self.assertAlmostEqual(r * math.cos(phi), x, places=6)
            self.assertAlmostEqual(r * math.sin(phi), y, places=6)
            self.assertGreaterEqual(r, -REACH - 1e-3)
            if prev is not None:
                self.assertLess(abs(phi - prev), max_jump,
                                "bed angle jump at t=%.4f" % T)
            prev = phi
        return outs[0]

    def test_radial_through_center_within_reach(self):
        # The leveling 'back point': in to 18 mm, straight through center to
        # 18 mm behind it.  The bed must not turn at all.
        sim = Sim(self.ffi, self.lib, start=(80., 0.))
        sim.line(18., 0.)
        sim.line(-18., 0.)
        out = self.check(sim)
        self.assertTrue(all(abs(o[3]) < 1e-9 for o in out))
        self.assertAlmostEqual(out[-1][4], -18., places=6)

    def test_behind_center_then_general_within_reach(self):
        sim = Sim(self.ffi, self.lib, start=(18., 0.))
        sim.line(-18., 0.)
        sim.line(0., -18.)      # stays behind center (|p| <= reach)
        sim.line(-10., 12.)
        out = self.check(sim)
        self.assertTrue(all(o[4] < 1e-6 for o in out[-60:]))

    def test_general_moves_around(self):
        sim = Sim(self.ffi, self.lib, start=(50., 0.))
        for (x, y) in [(40, 40), (-40, 40), (-40, -40), (40, -40), (60, 5),
                       (5, 60), (-70, 3)]:
            sim.line(float(x), float(y))
        self.check(sim)

    def test_matches_python_rule(self):
        # Python decide() must agree with C about the end state of each move
        sim = Sim(self.ffi, self.lib, start=(18., 0.))
        path = [(-18., 0.), (0., -18.), (0., 10.), (0., 50.), (30., 30.)]
        st = og.RepState(1, 0.)
        p = (18., 0.)
        for q in path:
            dec, st2, ok = og.decide(st, p, q, REACH)
            if not ok:
                break
            sim.line(*q)
            st, p = st2, q
        out = self.check(sim)
        T, x, y, phi, r = out[-1]
        self.assertEqual(st.sign, 1 if r > 0 else -1)

if __name__ == '__main__':
    unittest.main()
