# Orva bed leveling: 9-point polar pattern that starts wherever the bed is
# already sitting, with every probe since power-on remembered and refit.
#
#  * 6 points around the edge (every 60 deg, 110 mm out) and 3 near center
#    (23 mm out).  The first
#    center point is on the last edge point's line (arm just moves in), the
#    second is directly behind it past center (arm reaches through center,
#    bed doesn't turn), the third needs a quarter turn.
#  * Points from all runs since power-on are kept in memory (RAM only; a
#    restart or power-off clears them) and the surface is refit from all of
#    them: tilt + dome, plus saddle + twist once there are 12+ points.
#  * The fitted surface is applied as a Z correction by orva_motion.
#  * Leveling is "valid" after a run until power-off or until the tower is
#    detached and reattached (orva_tower calls invalidate()).
#
# Probing uses Klipper's standard PROBE command, so any [probe]-compatible
# sensor works (nozzle load cell, Beacon contact, Eddy, BLTouch...).
#
# Copyright (C) 2026  Orva contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging, math
from . import orva_geometry as og


class OrvaLevel:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.edge_radius = config.getfloat('edge_radius', 110., above=0.)
        self.center_radius = config.getfloat('center_radius', 23., above=0.)
        self.probe_height = config.getfloat('probe_height', 3., above=0.)
        self.travel_speed = config.getfloat('travel_speed', 80., above=0.)
        self.lift_speed = config.getfloat('lift_speed', 10., above=0.)
        self.max_points = config.getint('max_points', 400, minval=9)
        self.max_range = config.getfloat('max_range', 1.5, above=0.)
        self.points = []        # (x, y, z) from every run since power-on
        self.last_run = []
        self.current = []
        self.runs = 0
        self.surface = None
        self.valid = False
        self.active = False
        self.progress = 0
        self.motion = None
        self.printer.register_event_handler("klippy:connect",
                                            self._handle_connect)
        for cmd, desc in [
                ('ORVA_LEVEL', "Home Z and probe the 9-point pattern"),
                ('ORVA_ENSURE_LEVEL', "Level only if not leveled since "
                 "power-on or since the tower was reattached"),
                ('ORVA_LEVEL_STATUS', "Report the remembered bed surface"),
                ('ORVA_LEVEL_CLEAR', "Forget all remembered probe points")]:
            self.gcode.register_command(cmd, getattr(self, 'cmd_' + cmd),
                                        desc=desc)

    def _handle_connect(self):
        self.motion = self.printer.lookup_object('orva_motion', None)
        if self.motion is None:
            raise self.printer.config_error(
                "[orva_level] requires [orva_motion]")
        self.motion.register_z_provider(self.z_at)
        if self.printer.lookup_object('probe', None) is None:
            logging.warning("orva_level: no [probe] section; ORVA_LEVEL "
                            "will fail until a probe is configured")

    def z_at(self, x, y):
        if self.surface is None or self.active:
            return 0.   # probe the raw bed while leveling
        return self.surface.z(x, y)

    def invalidate(self):
        self.valid = False

    def forget(self):
        self.points = []
        self.last_run = []
        self.runs = 0
        self.surface = None
        self.valid = False

    # Probing ---------------------------------------------------------------
    def _run(self, script):
        self.gcode.run_script_from_command(script)

    def _probe_here(self, kin, x, y):
        """Probe at the nozzle position (x, y).  Returns the bed-frame point
        actually measured and its height.  Probe x/y offsets are taken in
        the arm's frame (x_offset along the arm, y_offset across it), since
        on a polar printer a fixed offset turns with the bed."""
        self._run("PROBE")
        probe = self.printer.lookup_object('probe')
        st = probe.get_status(self.printer.get_reactor().monotonic())
        pos = st.get('last_probe_position')
        z = float(pos[2]) if pos is not None else float(st['last_z_result'])
        try:
            ox, oy = probe.get_offsets()[:2]
        except Exception:
            ox = oy = 0.
        if ox or oy:
            phi = kin.get_rep_state().angle_of((x, y))
            ux, uy = math.cos(phi), math.sin(phi)
            x, y = x + ox * ux - oy * uy, y + ox * uy + oy * ux
        return x, y, z

    def _level(self, gcmd):
        toolhead = self.printer.lookup_object('toolhead')
        kin = toolhead.get_kinematics()
        self.active = True
        self.progress = 0
        run = self.current = []
        try:
            self._run("SAVE_GCODE_STATE NAME=orva_level")
            self._run("G90")
            # Home Z on the rim stop (arm moves out along its current line);
            # homes the arm too if it isn't yet.
            self._run("G28 Z")
            a0 = kin.bed_angle_under_arm()
            pts = og.probe_pattern(a0, self.edge_radius, self.center_radius)
            zf = self.lift_speed * 60.
            tf = self.travel_speed * 60.
            for i, (x, y) in enumerate(pts):
                self._run("G1 Z%.3f F%.0f" % (self.probe_height, zf))
                self._run("G1 X%.4f Y%.4f F%.0f" % (x, y, tf))
                run.append(self._probe_here(kin, x, y))
                self.progress = i + 1
                self._run("G1 Z%.3f F%.0f" % (self.probe_height, zf))
            zs = [p[2] for p in run]
            if max(zs) - min(zs) > self.max_range:
                raise gcmd.error(
                    "Orva: bed probes span %.3f mm (> max_range %.3f); "
                    "check the bed and the tower joint"
                    % (max(zs) - min(zs), self.max_range))
            self.points.extend(run)
            if len(self.points) > self.max_points:
                self.points = self.points[-self.max_points:]
            self.last_run = run
            self.runs += 1
            self.surface = og.Surface.fit(self.points)
            self.valid = True
        finally:
            self.active = False
            self._run("RESTORE_GCODE_STATE NAME=orva_level")
        res = self.surface.residuals(self.points)
        gcmd.respond_info(
            "Orva leveling run %d: %d points in map, range %.3f mm, "
            "fit residual max %.4f mm"
            % (self.runs, len(self.points), max(zs) - min(zs),
               max(abs(r) for r in res)))

    def cmd_ORVA_LEVEL(self, gcmd):
        self._level(gcmd)

    def cmd_ORVA_ENSURE_LEVEL(self, gcmd):
        if self.valid:
            gcmd.respond_info("Orva: leveling still valid (run %d, %d points)"
                              % (self.runs, len(self.points)))
            return
        self._level(gcmd)

    def cmd_ORVA_LEVEL_STATUS(self, gcmd):
        if self.surface is None:
            gcmd.respond_info("Orva: no leveling since power-on")
            return
        names = ['offset', 'tilt x', 'tilt y', 'dome', 'saddle', 'twist']
        coeffs = ", ".join("%s %.4f" % (n, c) for n, c in
                           zip(names, self.surface.coeffs))
        gcmd.respond_info("Orva leveling: %s, %d runs, %d points; %s"
                          % ("valid" if self.valid else "needs re-level",
                             self.runs, len(self.points), coeffs))

    def cmd_ORVA_LEVEL_CLEAR(self, gcmd):
        self.forget()
        gcmd.respond_info("Orva: leveling memory cleared")

    def get_status(self, eventtime):
        return {
            'valid': self.valid,
            'active': self.active,
            'progress': self.progress,
            'runs': self.runs,
            'point_count': len(self.points),
            # while leveling: the points so far in this run; otherwise the
            # last completed run.  'history' = everything remembered before.
            'last_run': [list(p) for p in (self.current if self.active
                                           else self.last_run)],
            'history': [list(p) for p in (
                self.points if self.active
                else self.points[:len(self.points) - len(self.last_run)])
                        ][-200:],
            'coeffs': list(self.surface.coeffs) if self.surface else [],
        }


def load_config(config):
    return OrvaLevel(config)
