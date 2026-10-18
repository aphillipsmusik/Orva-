# Orva motion: G-code move transform for the orva_polar kinematics.
#
#  * Routes lines that pass through (or within `snap` of) center exactly
#    through it, and turns the bed at center when the far side is beyond
#    the arm's reach behind center (a "pivot").
#  * Brings the arm back from behind center before it would run out of reach.
#  * Splits moves near center into short pieces so each piece only slows as
#    much as its own closest point needs (flow follows automatically, since
#    Klipper meters the extruder per mm of path over the bed).
#  * Applies Z corrections from registered providers (orva_level).
#  * Refuses extrusion that would put a first layer off the print surface or
#    run an overhang into the fixed Z-min plunger on the rim.
#
# Copyright (C) 2026  Orva contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging, math
from . import orva_geometry as og


class OrvaMotion:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.cfg = og.MotionConfig(
            reach=0.,   # filled in from the kinematics at connect
            snap=config.getfloat('center_snap', 0.3, minval=0.),
            split_radius=config.getfloat('split_radius', 38., above=0.),
            split_len=config.getfloat('split_length', 2., above=0.),
            min_split=config.getfloat('min_split_length', 0.2, above=0.))
        self.first_layer_radius = config.getfloat('first_layer_radius', 128.,
                                                  above=0.)
        self.first_layer_max_z = config.getfloat('first_layer_max_z', 0.6,
                                                 minval=0.)
        self.zstop_radius = config.getfloat('zstop_radius', 147.5, above=0.)
        self.zstop_band = config.getfloat('zstop_band', 3., minval=0.)
        self.zstop_clear_z = config.getfloat('zstop_clear_z', 3.5, minval=0.)
        self.pivot_speed = math.radians(config.getfloat(
            'pivot_speed', 180., above=0.))
        self.pivot_accel = math.radians(config.getfloat(
            'pivot_accel', 720., above=0.))
        self.detour_speed = config.getfloat('detour_speed', 150., above=0.)
        self.zcomp_segment = config.getfloat('zcomp_segment', 10., above=0.)
        self.z_providers = []
        self.pivots = 0
        self.toolhead = self.kin = self.gcode_move = None
        self.next_transform = None
        self.printer.register_event_handler("klippy:connect",
                                            self._handle_connect)
        self.gcode.register_command('ORVA_MOTION_STATUS',
                                    self.cmd_ORVA_MOTION_STATUS,
                                    desc=self.cmd_ORVA_MOTION_STATUS_help)

    def _handle_connect(self):
        self.toolhead = self.printer.lookup_object('toolhead')
        self.kin = self.toolhead.get_kinematics()
        if not hasattr(self.kin, 'orva_pivot'):
            raise self.printer.config_error(
                "[orva_motion] requires 'kinematics: orva_polar'")
        self.cfg.reach = self.kin.reach
        self.gcode_move = self.printer.lookup_object('gcode_move')
        self.next_transform = self.gcode_move.set_move_transform(self,
                                                                 force=True)

    # Z correction providers ------------------------------------------------
    def register_z_provider(self, fn):
        self.z_providers.append(fn)

    def z_adjust(self, x, y):
        return sum(fn(x, y) for fn in self.z_providers)

    # Move transform interface ----------------------------------------------
    def get_position(self):
        pos = self.next_transform.get_position()
        pos[2] -= self.z_adjust(pos[0], pos[1])
        return pos

    def move(self, newpos, speed):
        start = self.get_position()
        p0, p1 = start[:2], newpos[:2]
        if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) < 1e-9:
            self._emit(list(newpos), speed)
            return
        extruding = len(newpos) > 3 and newpos[3] > start[3] + 1e-9
        if extruding:
            self._check_extrusion(start, newpos)
        if not self.kin.is_xy_homed():
            # Let the kinematics produce its usual "Must home" error
            self._emit(list(newpos), speed)
            return
        try:
            steps, _ = og.plan_xy(self.kin.get_rep_state(), p0, p1,
                                  self.cfg, extruding)
        except ValueError as e:
            raise self.gcode.error(str(e))
        cur = list(start)
        pivoted = False
        for s in steps:
            kind = s[0]
            if kind == 'pivot':
                self._pivot(s[1])
                pivoted = True
                continue
            if kind == 'line':
                tgt = [a + (b - a) * s[1] for a, b in zip(start, newpos)]
                spd = speed
            elif kind == 'center':
                tgt = [a + (b - a) * s[1] for a, b in zip(start, newpos)]
                tgt[0] = tgt[1] = 0.
                spd = speed
            else:   # 'to': travel-only detour
                tgt = list(cur)
                tgt[0], tgt[1] = s[1]
                spd = max(speed, self.detour_speed)
            self._emit(tgt, spd, cur)
            cur = tgt
        if pivoted:
            # The pivot reset the toolhead position, which made gcode_move
            # re-read its position mid-move; put the real target back.
            self.gcode_move.last_position[:] = list(newpos)

    def _emit(self, pos, speed, cur=None):
        if self.z_providers and cur is not None:
            # Keep Z following the bed on long moves
            L = math.hypot(pos[0] - cur[0], pos[1] - cur[1])
            n = int(math.ceil(L / self.zcomp_segment))
            for k in range(1, n):
                p = [a + (b - a) * k / n for a, b in zip(cur, pos)]
                p[2] += self.z_adjust(p[0], p[1])
                self.next_transform.move(p, speed)
        out = list(pos)
        out[2] += self.z_adjust(out[0], out[1])
        self.next_transform.move(out, speed)

    def _pivot(self, dphi):
        logging.info("orva_motion: bed pivot %.2f deg at center",
                     math.degrees(dphi))
        self.kin.orva_pivot(dphi, self.pivot_speed, self.pivot_accel)
        self.pivots += 1

    # Safety ----------------------------------------------------------------
    def _check_extrusion(self, start, end):
        p0, p1 = start[:2], end[:2]
        rmax = max(og.hypot2(p0), og.hypot2(p1))
        rmin = og.segment_min_distance(p0, p1)
        zmin = min(start[2], end[2])
        if rmax > self.first_layer_radius + 0.05 and \
                zmin < self.first_layer_max_z:
            raise self.gcode.error(
                "Orva: first layer extends past the print surface "
                "(r=%.1f mm > %.1f mm). Only overhangs may reach past it."
                % (rmax, self.first_layer_radius))
        if (zmin < self.zstop_clear_z
                and rmax > self.zstop_radius - self.zstop_band
                and rmin < self.zstop_radius + self.zstop_band):
            raise self.gcode.error(
                "Orva: an overhang below %.1f mm reaches the Z stop's radius"
                " (%.1f mm) and would hit it as the bed turns."
                % (self.zstop_clear_z, self.zstop_radius))

    def get_status(self, eventtime):
        return {'pivots': self.pivots,
                'arm_sign': self.kin.mirror.sign if self.kin else 1}

    cmd_ORVA_MOTION_STATUS_help = "Report Orva motion state"
    def cmd_ORVA_MOTION_STATUS(self, gcmd):
        st = self.kin.get_rep_state()
        gcmd.respond_info(
            "Orva motion: arm %s, bed angle %.1f deg, reach %.1f mm, "
            "%d center pivots so far"
            % ("behind center" if st.sign < 0 else "normal",
               math.degrees(self.kin.bed_angle_under_arm()), self.cfg.reach,
               self.pivots))


def load_config(config):
    return OrvaMotion(config)
