// Test harness: drive kin_orva_polar.c with real Klipper trapq moves.
#include <stddef.h>
#include <stdlib.h>
#include "itersolve.h"
#include "trapq.h"
#include "list.h"

void *h_tq_new(void) { return trapq_alloc(); }
void h_append(void *tq, double pt, double at, double ct, double dt,
              double sx, double sy, double sz, double rx, double ry,
              double rz, double sv, double cv, double acc)
{
    trapq_append(tq, pt, at, ct, dt, sx, sy, sz, rx, ry, rz, sv, cv, acc);
}
int h_moves(void *tqv, void **out, int max)
{
    struct trapq *tq = tqv;
    trapq_check_sentinels(tq);
    int n = 0;
    struct move *m;
    list_for_each_entry(m, &tq->moves, node) {
        if ((m->axes_r.x != 0. || m->axes_r.y != 0.) && n < max)
            out[n++] = m;
    }
    return n;
}
void h_move_info(void *mv, double *o)
{
    struct move *m = mv;
    o[0] = m->print_time; o[1] = m->move_t;
    struct coord c = move_get_coord(m, 0.); o[2] = c.x; o[3] = c.y;
}
void h_coord(void *mv, double t, double *o)
{
    struct coord c = move_get_coord(mv, t); o[0] = c.x; o[1] = c.y;
}
void h_set_tq(struct stepper_kinematics *sk, void *tq) { sk->tq = tq; }
void h_set_cmd(struct stepper_kinematics *sk, double v) { sk->commanded_pos = v; }
