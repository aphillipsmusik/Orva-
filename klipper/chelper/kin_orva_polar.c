// Orva polar kinematics: rotating bed + linear arm that can reach past
// the bed's center.
//
// Based on Klipper's kin_polar.c (Copyright (C) 2018-2019 Kevin O'Connor).
// Copyright (C) 2026  Orva contributors
//
// This file may be distributed under the terms of the GNU GPLv3 license.
//
// A point (x, y) in the bed frame is printed with the bed at angle phi and
// the arm at signed distance r:  (x, y) = r * (cos phi, sin phi).
// Every point has two solutions, (phi, +h) and (phi + pi, -h).  The second
// is only physically possible while h <= reach (the arm's travel past
// center).  Switching between them can only happen at center, so the
// choice must be carried from move to move.
//
// Both steppers (bed angle and arm) must make the SAME choice for each
// move, even though Klipper evaluates them independently, in any order and
// in separate threads.
// So the choice is a pure function of the move and of the choice made for
// the previous XY move on the trapq; it is computed once and cached in a
// structure the two steppers share (struct orva_shared).
//
// Built as a separate shared library by orva_polar.py so Klipper itself is
// not modified.  It only needs Klipper's chelper headers.

#include <math.h>   // sqrt, atan2
#include <pthread.h> // pthread_mutex_lock
#include <stddef.h> // offsetof
#include <stdint.h> // uintptr_t
#include <stdlib.h> // malloc
#include <string.h> // memset
#include "compiler.h" // __visible
#include "itersolve.h" // struct stepper_kinematics
#include "list.h" // list_prev_entry
#include "trapq.h" // struct move

#define EPS_POINT 1e-3  // mm: closer than this counts as center
#define EPS_LINE 1e-4   // mm: a line this close to center is radial
#define CACHE_SIZE 65536
#define CACHE_PROBES 8

struct orva_state {
    int sign;       // +1 normal, -1 arm reaching behind center
    double hint;    // bed angle (used when the nozzle is at center)
};

struct orva_decision {
    int radial;     // 1: bed angle fixed at phi, arm slides along its line
    int sign;       // general moves: which solution
    double phi, ux, uy;
    struct orva_state out;   // state after this move
};

struct orva_cache_entry {
    struct move *m;
    double print_time;
    uint32_t gen;
    struct orva_decision dec;
};

struct orva_shared {
    // Klipper generates each stepper's steps in its own thread, so the bed
    // and arm threads share this structure: everything below is protected
    // by the lock.
    pthread_mutex_t lock;
    double reach;
    uint32_t gen;
    struct orva_state frontier;     // state after the latest decided move
    double frontier_time;
    struct orva_cache_entry cache[CACHE_SIZE];
};

struct orva_sk {
    struct stepper_kinematics sk;   // must be first (freed with free())
    struct orva_shared *sh;
    struct move *last_m;
    double last_pt;
    uint32_t last_gen;
    struct orva_decision last_dec;
};

static inline double
wrap_angle(double a)
{
    a = fmod(a, 2. * M_PI);
    if (a > M_PI)
        a -= 2. * M_PI;
    else if (a <= -M_PI)
        a += 2. * M_PI;
    return a;
}

// Local copies of trapq.c helpers (this library doesn't link against it)
static inline double
orva_move_dist(struct move *m, double t)
{
    return (m->start_v + m->half_accel * t) * t;
}

static inline struct coord
orva_move_coord(struct move *m, double t)
{
    double d = orva_move_dist(m, t);
    return (struct coord) {
        .x = m->start_pos.x + m->axes_r.x * d,
        .y = m->start_pos.y + m->axes_r.y * d,
        .z = m->start_pos.z + m->axes_r.z * d };
}

static inline int
is_xy_move(struct move *m)
{
    return m->axes_r.x != 0. || m->axes_r.y != 0.;
}

// The rule. Must match decide() in orva_geometry.py.
static void
orva_decide(struct orva_shared *sh, struct orva_state in, struct move *m
            , struct orva_decision *dec)
{
    double x0 = m->start_pos.x, y0 = m->start_pos.y;
    double h0 = sqrt(x0*x0 + y0*y0);
    double wl = sqrt(m->axes_r.x*m->axes_r.x + m->axes_r.y*m->axes_r.y);
    double wx = m->axes_r.x / wl, wy = m->axes_r.y / wl;
    struct coord e = orva_move_coord(m, m->move_t);
    double h1 = sqrt(e.x*e.x + e.y*e.y);
    memset(dec, 0, sizeof(*dec));
    if (h0 < EPS_POINT) {
        // Starting at center: choose the bed angle closest to the current
        // one; behind-center only if the end stays within reach.
        double ang_pos = atan2(wy, wx), ang_neg = ang_pos + M_PI;
        int can_neg = h1 <= sh->reach + EPS_POINT;
        if (can_neg && fabs(wrap_angle(ang_neg - in.hint))
            < fabs(wrap_angle(ang_pos - in.hint)))
            dec->phi = ang_neg;
        else
            dec->phi = ang_pos;
        dec->radial = 1;
        dec->sign = 1;
    } else if (fabs(x0 * wy - y0 * wx) < EPS_LINE) {
        // Radial: along the arm's line, possibly through center
        dec->radial = 1;
        dec->sign = in.sign;
        dec->phi = atan2(in.sign * y0, in.sign * x0);
    } else {
        dec->radial = 0;
        dec->sign = in.sign;
    }
    if (dec->radial) {
        dec->ux = cos(dec->phi);
        dec->uy = sin(dec->phi);
        double r_end = e.x * dec->ux + e.y * dec->uy;
        dec->out.hint = dec->phi;
        dec->out.sign = (fabs(r_end) < EPS_POINT || r_end > 0.) ? 1 : -1;
    } else {
        dec->out.sign = in.sign;
        dec->out.hint = atan2(in.sign * e.y, in.sign * e.x);
    }
}

static struct orva_cache_entry *
cache_find(struct orva_shared *sh, struct move *m)
{
    uintptr_t hsh = ((uintptr_t)m >> 4) * 2654435761u;
    for (int i = 0; i < CACHE_PROBES; i++) {
        struct orva_cache_entry *ce = &sh->cache[(hsh + i) % CACHE_SIZE];
        if (ce->m == m && ce->gen == sh->gen
            && ce->print_time == m->print_time)
            return ce;
    }
    return NULL;
}

static struct orva_cache_entry *
cache_slot(struct orva_shared *sh, struct move *m)
{
    uintptr_t hsh = ((uintptr_t)m >> 4) * 2654435761u;
    struct orva_cache_entry *best = NULL;
    for (int i = 0; i < CACHE_PROBES; i++) {
        struct orva_cache_entry *ce = &sh->cache[(hsh + i) % CACHE_SIZE];
        if (!ce->m || ce->gen != sh->gen)
            return ce;
        if (!best || ce->print_time < best->print_time)
            best = ce;
    }
    return best;
}

// Get (computing if needed) the decision for move m.  Walks back along the
// trapq to the last decided XY move so decisions are always made in order,
// no matter which stepper (or which time) asks first.
static struct orva_decision *
get_decision(struct orva_sk *osk, struct move *m)
{
    struct orva_shared *sh = osk->sh;
    struct orva_cache_entry *ce = cache_find(sh, m);
    if (ce)
        return &ce->dec;
    struct trapq *tq = osk->sk.tq;
    struct move *local[64], **chain = local;
    int n = 0, cap = 64;
    struct orva_state in = sh->frontier;
    struct move *p = m;
    for (;;) {
        if (n == cap) {
            struct move **nc = malloc(sizeof(*nc) * cap * 2);
            memcpy(nc, chain, sizeof(*nc) * n);
            if (chain != local)
                free(chain);
            chain = nc;
            cap *= 2;
        }
        chain[n++] = p;
        if (!tq)
            break;
        // Previous XY move on the queue (sentinels and null moves have no
        // XY motion, so they are skipped)
        struct move *q = list_prev_entry(p, node);
        while (&q->node != &tq->moves.root && !is_xy_move(q))
            q = list_prev_entry(q, node);
        if (&q->node == &tq->moves.root)
            break;      // nothing earlier on the queue: use the frontier
        struct orva_cache_entry *qe = cache_find(sh, q);
        if (qe) {
            in = qe->dec.out;
            break;
        }
        p = q;
    }
    // Decide forward, oldest first
    struct orva_decision *last = NULL;
    for (int i = n - 1; i >= 0; i--) {
        struct move *cm = chain[i];
        struct orva_cache_entry *slot = cache_slot(sh, cm);
        orva_decide(sh, in, cm, &slot->dec);
        slot->m = cm;
        slot->print_time = cm->print_time;
        slot->gen = sh->gen;
        in = slot->dec.out;
        last = &slot->dec;
        if (cm->print_time >= sh->frontier_time) {
            sh->frontier = slot->dec.out;
            sh->frontier_time = cm->print_time;
        }
    }
    if (chain != local)
        free(chain);
    return last;
}

static struct orva_decision *
lookup(struct orva_sk *osk, struct move *m, struct orva_decision *tmp)
{
    if (!is_xy_move(m)) {
        // No XY motion (position queries, Z-only moves): use the frontier
        pthread_mutex_lock(&osk->sh->lock);
        struct orva_state st = osk->sh->frontier;
        pthread_mutex_unlock(&osk->sh->lock);
        double x = m->start_pos.x, y = m->start_pos.y;
        memset(tmp, 0, sizeof(*tmp));
        if (sqrt(x*x + y*y) < EPS_POINT) {
            tmp->radial = 1;
            tmp->phi = st.hint;
            tmp->ux = cos(st.hint);
            tmp->uy = sin(st.hint);
        } else {
            tmp->radial = 0;
            tmp->sign = st.sign;
        }
        return tmp;
    }
    // Per-stepper copy of the last decision (only this stepper's thread
    // touches it).  gen is read without the lock: a stale read just means
    // one extra trip through the locked path.
    if (osk->last_m == m && osk->last_pt == m->print_time
        && osk->last_gen == __atomic_load_n(&osk->sh->gen, __ATOMIC_ACQUIRE))
        return &osk->last_dec;
    pthread_mutex_lock(&osk->sh->lock);
    struct orva_decision *d = get_decision(osk, m);
    osk->last_dec = *d;     // copy while holding the lock
    osk->last_gen = osk->sh->gen;
    pthread_mutex_unlock(&osk->sh->lock);
    osk->last_m = m;
    osk->last_pt = m->print_time;
    return &osk->last_dec;
}

static double
orva_arm_calc_position(struct stepper_kinematics *sk, struct move *m
                       , double move_time)
{
    struct orva_sk *osk = container_of(sk, struct orva_sk, sk);
    struct orva_decision tmp, *d = lookup(osk, m, &tmp);
    struct coord c = orva_move_coord(m, move_time);
    if (d->radial)
        return c.x * d->ux + c.y * d->uy;
    return d->sign * sqrt(c.x*c.x + c.y*c.y);
}

static double
orva_bed_calc_position(struct stepper_kinematics *sk, struct move *m
                       , double move_time)
{
    struct orva_sk *osk = container_of(sk, struct orva_sk, sk);
    struct orva_decision tmp, *d = lookup(osk, m, &tmp);
    double angle;
    if (d->radial) {
        angle = d->phi;
    } else {
        struct coord c = orva_move_coord(m, move_time);
        angle = atan2(d->sign * c.y, d->sign * c.x);
    }
    // Stay continuous with the bed's current angle
    angle = sk->commanded_pos + wrap_angle(angle - sk->commanded_pos);
    return angle;
}

static void
orva_bed_post_fixup(struct stepper_kinematics *sk)
{
    // Keep the commanded angle in (-pi, pi] like kin_polar.c
    if (sk->commanded_pos < -M_PI)
        sk->commanded_pos += 2 * M_PI;
    else if (sk->commanded_pos > M_PI)
        sk->commanded_pos -= 2 * M_PI;
}

struct orva_shared * __visible
orva_polar_shared_alloc(double reach)
{
    struct orva_shared *sh = malloc(sizeof(*sh));
    memset(sh, 0, sizeof(*sh));
    pthread_mutex_init(&sh->lock, NULL);
    sh->reach = reach;
    sh->gen = 1;
    sh->frontier.sign = 1;
    return sh;
}

// Called by Python whenever the toolhead position is set (homing, G92,
// after a bed pivot).  Forgets all cached decisions.
void __visible
orva_polar_reset(struct orva_shared *sh, int sign, double hint)
{
    pthread_mutex_lock(&sh->lock);
    uint32_t gen = sh->gen + 1;
    if (!gen)
        gen = 1;
    __atomic_store_n(&sh->gen, gen, __ATOMIC_RELEASE);
    sh->frontier.sign = sign < 0 ? -1 : 1;
    sh->frontier.hint = hint;
    sh->frontier_time = 0.;
    pthread_mutex_unlock(&sh->lock);
}

void __visible
orva_polar_get_frontier(struct orva_shared *sh, double *out)
{
    pthread_mutex_lock(&sh->lock);
    out[0] = sh->frontier.sign;
    out[1] = sh->frontier.hint;
    pthread_mutex_unlock(&sh->lock);
}

struct stepper_kinematics * __visible
orva_polar_stepper_alloc(struct orva_shared *sh, char type)
{
    struct orva_sk *osk = malloc(sizeof(*osk));
    memset(osk, 0, sizeof(*osk));
    osk->sh = sh;
    if (type == 'r') {
        osk->sk.calc_position_cb = orva_arm_calc_position;
    } else if (type == 'a') {
        osk->sk.calc_position_cb = orva_bed_calc_position;
        osk->sk.post_cb = orva_bed_post_fixup;
    }
    osk->sk.active_flags = AF_X | AF_Y;
    return &osk->sk;
}

// Test hook: evaluate a stepper at a time within a move
double __visible
orva_polar_test_calc(struct stepper_kinematics *sk, struct move *m, double t)
{
    return sk->calc_position_cb(sk, m, t);
}
