// Orva mark for the startup / shutdown animation.
//
// The O is drawn as a superellipse ring that morphs from the Michroma-style
// squircle (n = 4) into a circle (n = 2) while the grey arm and blue nozzle
// tip slide outward along their line, like the printer's r axis.  Same
// geometry as the logo canvas (font units, y down).
#pragma once
#include <math.h>
#include <stdint.h>

namespace logo {

static const float CX = 1072.5f, CY = 800.f;
static const float UX = -0.763f, UY = 0.646f;        // arm direction
static const float TIP_BASE_X = 1164.f, TIP_BASE_Y = 722.f;
static const float ARM_W = 166.f;
static const float CUT_X0 = -200.f, CUT_Y0 = 1800.f;  // gap cut in the ring
static const float CUT_X1 = 1072.f, CUT_Y1 = 800.f;
static const float CUT_W = 446.f;
static const float TIP[4][2] = {{1217.6f, 785.3f}, {1346.1f, 596.7f},
                                {1317.7f, 563.1f}, {1110.4f, 658.7f}};

static inline float lerp(float a, float b, float t) { return a + (b - a) * t; }

static inline float ease(float x)
{
    if (x < 0.f) return 0.f;
    if (x > 1.f) return 1.f;
    return x < 0.5f ? 4.f * x * x * x : 1.f - powf(-2.f * x + 2.f, 3.f) / 2.f;
}

// distance from point to segment
static inline float seg_dist(float px, float py, float ax, float ay,
                             float bx, float by)
{
    float dx = bx - ax, dy = by - ay;
    float t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy);
    if (t < 0.f) t = 0.f;
    if (t > 1.f) t = 1.f;
    float qx = ax + dx * t - px, qy = ay + dy * t - py;
    return sqrtf(qx * qx + qy * qy);
}

static inline bool in_quad(float px, float py, const float q[4][2],
                           float ox, float oy)
{
    int pos = 0, neg = 0;
    for (int i = 0; i < 4; i++) {
        float ax = q[i][0] + ox, ay = q[i][1] + oy;
        float bx = q[(i + 1) % 4][0] + ox, by = q[(i + 1) % 4][1] + oy;
        float c = (bx - ax) * (py - ay) - (by - ay) * (px - ax);
        if (c > 0) pos++; else if (c < 0) neg++;
    }
    return !(pos && neg);
}

struct Frame {
    float n, ao, bo, ai, bi;      // ring
    float ax0, ay0, ax1, ay1;     // arm segment
    float tipx, tipy;             // tip offset
};

// m = 0: squircle, arm in; m = 1: circle, arm slid out
static inline Frame frame(float m)
{
    Frame f;
    f.n = lerp(4.f, 2.f, m);
    f.ao = lerp(944.5f, 800.f, m);
    f.bo = 800.f;
    f.ai = lerp(752.5f, 628.f, m);
    f.bi = lerp(634.f, 628.f, m);
    float rr = 1.f / powf(powf(fabsf(UX / f.ao), f.n)
                          + powf(fabsf(UY / f.bo), f.n), 1.f / f.n) - 40.f;
    float slide = 170.f * m;
    f.ax0 = CX + UX * rr;
    f.ay0 = CY + UY * rr;
    f.ax1 = TIP_BASE_X + UX * slide;
    f.ay1 = TIP_BASE_Y + UY * slide;
    f.tipx = UX * slide;
    f.tipy = UY * slide;
    return f;
}

static inline float se(float dx, float dy, float a, float b, float n)
{
    return powf(fabsf(dx / a), n) + powf(fabsf(dy / b), n);
}

// What colour is font-unit point (x, y)?  0 = background, 1 = ring,
// 2 = arm, 3 = tip
static inline int sample(const Frame &f, float x, float y)
{
    if (in_quad(x, y, TIP, f.tipx, f.tipy))
        return 3;
    if (seg_dist(x, y, f.ax0, f.ay0, f.ax1, f.ay1) <= ARM_W * 0.5f)
        return 2;
    float dx = x - CX, dy = y - CY;
    if (se(dx, dy, f.ao, f.bo, f.n) <= 1.f && se(dx, dy, f.ai, f.bi, f.n) > 1.f
        && seg_dist(x, y, CUT_X0, CUT_Y0, CUT_X1, CUT_Y1) > CUT_W * 0.5f)
        return 1;
    return 0;
}

} // namespace logo
