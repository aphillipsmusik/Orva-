# Orva flow test: before a print, trace one outline a few mm outside the
# first object's footprint (taken from the slicer's EXCLUDE_OBJECT_DEFINE
# polygons).  Following that shape on a polar printer makes the bed swing
# and the arm dart in and out, so the extruder sees the same fast flow
# changes the real print will.  The outline runs in three sections at
# rising target speed.
#
# Measuring how much of the commanded flow actually came out needs a sensor
# on the toolhead (e.g. a load cell under the extruder).  That hardware
# isn't specified yet, so measurement is a pluggable backend: with
# `measure: none` the outline is printed (it still primes the nozzle and
# shows the operator how flow behaves) and the configured defaults are
# applied.  See docs/firmware.md for the backend interface.
#
# Copyright (C) 2026  Orva contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging, math
from . import orva_geometry as og


class NoMeasure:
    """Measurement backend that measures nothing."""
    name = 'none'
    def __init__(self, printer, config):
        pass
    def start_section(self, index, target_flow):
        pass
    def end_section(self, index):
        return None     # fraction of commanded flow delivered, or None


BACKENDS = {'none': NoMeasure}


class OrvaFlowTest:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.offset = config.getfloat('offset', 3.5, above=0.)
        self.max_radius = config.getfloat('max_radius', 126.8, above=0.)
        self.speeds = [float(v) for v in config.getlist(
            'speeds', ['35', '75', '125'])]
        self.line_width = config.getfloat('line_width', 0.45, above=0.)
        self.layer_height = config.getfloat('layer_height', 0.2, above=0.)
        self.travel_speed = config.getfloat('travel_speed', 150., above=0.)
        self.lift = config.getfloat('lift', 1., minval=0.)
        self.default_flow_ratio = config.getfloat('default_flow_ratio', 1.,
                                                  above=0.)
        self.default_pressure_advance = config.getfloat(
            'default_pressure_advance', 0.035, minval=0.)
        self.apply_results = config.getboolean('apply_results', True)
        backend = config.getchoice('measure', {k: k for k in BACKENDS},
                                   'none')
        self.backend = BACKENDS[backend](self.printer, config)
        self.active = False
        self.section = 0
        self.results = []
        self.flow_ratio = None
        self.pressure_advance = None
        self.max_flow = None
        self.gcode.register_command(
            'ORVA_FLOW_TEST', self.cmd_ORVA_FLOW_TEST,
            desc="Print an outline around the first object and check flow")

    def _run(self, s):
        self.gcode.run_script_from_command(s)

    def _filament_area(self):
        toolhead = self.printer.lookup_object('toolhead')
        ext = toolhead.get_extruder()
        area = getattr(ext, 'filament_area', None)
        return area if area else math.pi * (1.75 / 2.) ** 2

    def _first_polygon(self, name):
        eo = self.printer.lookup_object('exclude_object', None)
        if eo is None:
            return None, None
        objs = eo.get_status()['objects']
        for o in objs:
            if 'polygon' not in o or len(o['polygon']) < 3:
                continue
            if name is None or o['name'].upper() == name.upper():
                return o['name'], o['polygon']
        return None, None

    def cmd_ORVA_FLOW_TEST(self, gcmd):
        name, poly = self._first_polygon(gcmd.get('OBJECT', None))
        if poly is None:
            gcmd.respond_info(
                "Orva flow test skipped: no object outlines. In the slicer, "
                "set 'Label objects' to firmware-specific / exclude objects "
                "so EXCLUDE_OBJECT_DEFINE lines come before PRINT_START.")
            return
        path = og.offset_outline(poly, self.offset, self.max_radius)
        total = og.path_length(path)
        e_per_mm = (self.line_width * self.layer_height
                    / self._filament_area())
        z = gcmd.get_float('Z', self.layer_height, above=0.)
        self.active = True
        self.results = [None] * len(self.speeds)
        try:
            self._run("SAVE_GCODE_STATE NAME=orva_flow")
            self._run("G90\nM83")
            self._run("G1 Z%.3f F600" % (z + self.lift,))
            self._run("G1 X%.3f Y%.3f F%.0f" % (path[0][0], path[0][1],
                                                self.travel_speed * 60.))
            self._run("G1 Z%.3f F600" % (z,))
            nsec = len(self.speeds)
            done, sec = 0., 0
            self.section = 0
            self.backend.start_section(0, self.speeds[0] * self.line_width
                                       * self.layer_height)
            for i in range(1, len(path)):
                a, b = path[i - 1], path[i]
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                done += L
                v = self.speeds[sec]
                self._run("G1 X%.4f Y%.4f E%.5f F%.0f"
                          % (b[0], b[1], L * e_per_mm, v * 60.))
                new_sec = min(nsec - 1, int(nsec * done / total))
                if new_sec != sec or i == len(path) - 1:
                    self.results[sec] = self.backend.end_section(sec)
                    if new_sec != sec:
                        sec = new_sec
                        self.section = sec
                        self.backend.start_section(
                            sec, self.speeds[sec] * self.line_width
                            * self.layer_height)
            self._run("G1 Z%.3f F600" % (z + self.lift,))
        finally:
            self.active = False
            self._run("RESTORE_GCODE_STATE NAME=orva_flow")
        self._finish(gcmd, name)

    def _finish(self, gcmd, name):
        measured = [r for r in self.results if r is not None]
        flows = [v * self.line_width * self.layer_height for v in self.speeds]
        if measured:
            self.flow_ratio = sum(measured) / len(measured)
            ok = [f for f, r in zip(flows, self.results)
                  if r is not None and r >= 0.95]
            self.max_flow = max(ok) if ok else min(flows)
            # Pressure advance tuning from the measured lag would go here;
            # until a backend reports it, keep the configured value.
            self.pressure_advance = self.default_pressure_advance
            src = self.backend.name
        else:
            self.flow_ratio = self.default_flow_ratio
            self.max_flow = max(flows)
            self.pressure_advance = self.default_pressure_advance
            src = "defaults (no flow sensor configured)"
        if self.apply_results:
            self._run("SET_PRESSURE_ADVANCE ADVANCE=%.4f"
                      % (self.pressure_advance,))
            self._run("M221 S%.1f" % (self.flow_ratio * 100.,))
        gcmd.respond_info(
            "Orva flow test around %s: flow ratio %.3f, pressure advance "
            "%.4f, max flow %.1f mm^3/s (%s)"
            % (name, self.flow_ratio, self.pressure_advance, self.max_flow,
               src))

    def get_status(self, eventtime):
        return {'active': self.active, 'section': self.section,
                'sections': len(self.speeds),
                'target_flows': [v * self.line_width * self.layer_height
                                 for v in self.speeds],
                'results': self.results,
                'flow_ratio': self.flow_ratio,
                'pressure_advance': self.pressure_advance,
                'max_flow': self.max_flow}


def load_config(config):
    return OrvaFlowTest(config)
