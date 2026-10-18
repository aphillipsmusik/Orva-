# Orva wiper: brass brush on a small lift in the base rim, beside the fixed
# Z-min stop (the stop is NOT on the lift).
#
#  * Power on: the brush rises out of the rim (klippy:ready).
#  * Power off: a return spring pulls it below the rim (hardware); the
#    ORVA_SHUTDOWN macro also lowers it first.
#  * Normal prints: the brush stays up the whole time.
#  * Prints that overhang past the bed: the brush stays down so the rim is
#    clear, and pops up only while the bed is stopped for a wipe, at an angle
#    where no overhang is over the brush.
#
# Copyright (C) 2026  Orva contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging, math
from . import orva_geometry as og


class OrvaWiper:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.servo_name = config.get('servo', None)
        self.up_angle = config.getfloat('up_angle', 90.)
        self.down_angle = config.getfloat('down_angle', 0.)
        self.lift_time = config.getfloat('lift_time', 0.4, minval=0.)
        self.radius = config.getfloat('radius', 141., above=0.)
        self.r_min = config.getfloat('radius_min', 138.5, above=0.)
        self.r_max = config.getfloat('radius_max', 143.5, above=0.)
        self.wipe_z = config.getfloat('wipe_z', 1.5)
        self.passes = config.getint('passes', 3, minval=1)
        self.wipe_speed = config.getfloat('wipe_speed', 60., above=0.)
        self.travel_speed = config.getfloat('travel_speed', 150., above=0.)
        self.overhang_radius = config.getfloat('overhang_radius', 128.,
                                               above=0.)
        # brush half-width plus toolhead clearance, as an angle at the brush
        self.clear_width = config.getfloat('clear_width', 30., above=0.)
        self.raise_on_ready = config.getboolean('raise_on_ready', True)
        self.mode = 'normal'
        self.raised = False
        self.printer.register_event_handler("klippy:ready",
                                            self._handle_ready)
        for cmd, desc in [
                ('ORVA_WIPER', "Raise or lower the wiper brush: STATE=UP|DOWN"),
                ('ORVA_WIPER_MODE', "MODE=AUTO|NORMAL|OVERHANG (AUTO checks "
                 "the object outlines for overhangs past the bed)"),
                ('ORVA_WIPE', "Wipe the nozzle on the brush")]:
            self.gcode.register_command(cmd, getattr(self, 'cmd_' + cmd),
                                        desc=desc)

    def _handle_ready(self):
        if self.raise_on_ready and self.servo_name:
            reactor = self.printer.get_reactor()
            reactor.register_callback(self._raise_at_power_on)

    def _raise_at_power_on(self, eventtime):
        try:
            self.gcode.run_script("SET_SERVO SERVO=%s ANGLE=%.1f"
                                  % (self.servo_name, self.up_angle))
            self.raised = True
        except Exception:
            logging.exception("orva_wiper: unable to raise the brush")

    def set_raised(self, up):
        """Move the brush (call from within a G-code command)."""
        if self.servo_name is None:
            self.raised = up
            return
        self.gcode.run_script_from_command(
            "SET_SERVO SERVO=%s ANGLE=%.1f" % (
                self.servo_name, self.up_angle if up else self.down_angle))
        if up != self.raised:
            toolhead = self.printer.lookup_object('toolhead')
            toolhead.dwell(self.lift_time)
        self.raised = up

    def _polygons(self):
        eo = self.printer.lookup_object('exclude_object', None)
        if eo is None:
            return []
        return [o['polygon'] for o in eo.get_status()['objects']
                if len(o.get('polygon', [])) >= 3]

    def detect_overhang(self):
        for poly in self._polygons():
            if any(og.hypot2(p) > self.overhang_radius + 0.05 for p in poly):
                return True
        return False

    def cmd_ORVA_WIPER(self, gcmd):
        state = gcmd.get('STATE').upper()
        if state not in ('UP', 'DOWN'):
            raise gcmd.error("STATE must be UP or DOWN")
        self.set_raised(state == 'UP')

    def cmd_ORVA_WIPER_MODE(self, gcmd):
        mode = gcmd.get('MODE', 'AUTO').upper()
        if mode == 'AUTO':
            mode = 'OVERHANG' if self.detect_overhang() else 'NORMAL'
        if mode not in ('NORMAL', 'OVERHANG'):
            raise gcmd.error("MODE must be AUTO, NORMAL or OVERHANG")
        self.mode = mode.lower()
        self.set_raised(self.mode == 'normal')
        gcmd.respond_info("Orva wiper: %s mode (brush %s)" % (
            self.mode, "up" if self.raised else "down between wipes"))

    def cmd_ORVA_WIPE(self, gcmd):
        toolhead = self.printer.lookup_object('toolhead')
        kin = toolhead.get_kinematics()
        run = self.gcode.run_script_from_command
        pos = toolhead.get_position()
        safe_z = gcmd.get_float('SAFE_Z', max(pos[2], self.wipe_z) + 2.)
        a = kin.bed_angle_under_arm()
        if self.mode == 'overhang':
            margin = self.clear_width / self.radius
            a2 = og.clear_wipe_angle(a % (2. * math.pi), self._polygons(),
                                     self.overhang_radius, margin)
            if a2 is None:
                raise gcmd.error("Orva: no clear angle to raise the brush")
            a = a + og.wrap(a2 - a)
        ca, sa = math.cos(a), math.sin(a)
        tf, wf = self.travel_speed * 60., self.wipe_speed * 60.
        run("SAVE_GCODE_STATE NAME=orva_wipe")
        try:
            run("G90")
            run("G1 Z%.3f F600" % (safe_z,))
            # Turn to the clear angle at a radius inside the brush, then
            # out to the brush along the arm's line
            run("G1 X%.3f Y%.3f F%.0f" % (self.r_min * ca, self.r_min * sa, tf))
            if self.mode == 'overhang':
                self.set_raised(True)
            run("G1 X%.3f Y%.3f F%.0f" % (self.radius * ca, self.radius * sa,
                                          tf))
            run("G1 Z%.3f F600" % (self.wipe_z,))
            for _ in range(self.passes):
                run("G1 X%.3f Y%.3f F%.0f" % (self.r_max * ca,
                                              self.r_max * sa, wf))
                run("G1 X%.3f Y%.3f F%.0f" % (self.r_min * ca,
                                              self.r_min * sa, wf))
            run("G1 Z%.3f F600" % (safe_z,))
            if self.mode == 'overhang':
                self.set_raised(False)
        finally:
            run("RESTORE_GCODE_STATE NAME=orva_wipe")

    def get_status(self, eventtime):
        return {'mode': self.mode, 'raised': self.raised}


def load_config(config):
    return OrvaWiper(config)
