# Orva polar kinematics: rotating bed (stepper_bed), linear arm that can
# reach past the bed's center (stepper_arm), belt-driven Z (stepper_z).
#
# Based on Klipper's kinematics/polar.py
#   Copyright (C) 2018-2021  Kevin O'Connor <kevin@koconnor.net>
# Copyright (C) 2026  Orva contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
# Differences from polar.py:
#  * The arm may go negative (past center) down to stepper_arm's
#    position_min.  The C side (kin_orva_polar.c) keeps the bed and arm
#    steppers agreeing on which of a point's two solutions to use.
#  * Moves near center slow down only as much as their own geometry needs
#    (bed turn rate = speed * line distance / r^2), so radial moves through
#    center run at full speed.
#  * Z homes against a stop fixed in the base rim at z_home_radius; the arm
#    moves out there along its current line (no bed turn) before homing.
#  * orva_pivot() turns only the bed while the nozzle sits at center.
import logging, math, os, subprocess
import stepper, chelper
from extras import orva_geometry as og

######################################################################
# Build / load the C helper as its own small library (Klipper unchanged)
######################################################################

ORVA_CDEFS = """
    void *orva_polar_shared_alloc(double reach);
    void orva_polar_reset(void *sh, int sign, double hint);
    void orva_polar_get_frontier(void *sh, double *out);
    void *orva_polar_stepper_alloc(void *sh, char type);
    double orva_polar_test_calc(void *sk, void *m, double t);
    void free(void*);
"""

_orva_lib = None

def _source_paths():
    here = os.path.dirname(os.path.realpath(__file__))
    src = os.path.join(os.path.dirname(here), 'chelper', 'kin_orva_polar.c')
    out_dir = os.path.join(os.path.dirname(here), 'chelper', 'build')
    return src, out_dir

def get_orva_lib():
    """Compile kin_orva_polar.c (if needed) against Klipper's chelper
    headers and load it.  Returns (ffi, lib)."""
    global _orva_lib
    if _orva_lib is not None:
        return _orva_lib
    import cffi
    src, out_dir = _source_paths()
    inc = os.path.dirname(os.path.realpath(chelper.__file__))
    dest = os.path.join(out_dir, 'orva_kin.so')
    deps = [src] + [os.path.join(inc, h) for h in (
        'itersolve.h', 'trapq.h', 'list.h', 'compiler.h')]
    need = (not os.path.exists(dest)
            or any(os.path.getmtime(d) > os.path.getmtime(dest)
                   for d in deps if os.path.exists(d)))
    if need:
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        cmd = ["gcc", "-Wall", "-g", "-O2", "-shared", "-fPIC",
               "-I" + inc, "-o", dest, src, "-lm", "-lpthread"]
        logging.info("Building Orva kinematics helper: %s", " ".join(cmd))
        ret = subprocess.call(cmd)
        if ret != 0:
            raise Exception("Unable to build Orva kinematics helper %s"
                            % (src,))
    ffi = cffi.FFI()
    ffi.cdef(ORVA_CDEFS)
    lib = ffi.dlopen(dest)
    _orva_lib = (ffi, lib)
    return _orva_lib

def _to_klipper_sk(ptr):
    """Hand a pointer from our library to Klipper's FFI as its own type,
    freed by Klipper's free() like any other stepper_kinematics."""
    ffi, lib = get_orva_lib()
    ffi_main, ffi_lib = chelper.get_ffi()
    addr = int(ffi.cast('uintptr_t', ptr))
    sk = ffi_main.cast('struct stepper_kinematics *', addr)
    return ffi_main.gc(sk, ffi_lib.free)

######################################################################
# Kinematics
######################################################################

class OrvaPolarKinematics:
    def __init__(self, toolhead, config):
        self.printer = config.get_printer()
        self.toolhead = toolhead
        stepper_bed = stepper.PrinterStepper(config.getsection('stepper_bed'),
                                             units_in_radians=True)
        rail_arm = stepper.LookupRail(config.getsection('stepper_arm'))
        rail_z = stepper.LookupMultiRail(config.getsection('stepper_z'))
        arm_min, arm_max = rail_arm.get_range()
        self.reach = max(0., -arm_min)
        self.max_radius = arm_max
        # Shared decision state for the bed and arm steppers
        ffi, lib = get_orva_lib()
        self._lib = lib
        self._ffi = ffi
        self.shared = ffi.gc(lib.orva_polar_shared_alloc(self.reach),
                             lib.free)
        stepper_bed.set_stepper_kinematics(_to_klipper_sk(
            lib.orva_polar_stepper_alloc(self.shared, b'a')))
        for s in rail_arm.get_steppers():
            s.set_stepper_kinematics(_to_klipper_sk(
                lib.orva_polar_stepper_alloc(self.shared, b'r')))
        rail_z.setup_itersolve('cartesian_stepper_alloc', b'z')
        self.bed_stepper = stepper_bed
        self.rails = [rail_arm, rail_z]
        self.steppers = [stepper_bed] + [s for r in self.rails
                                         for s in r.get_steppers()]
        for s in self.get_steppers():
            s.set_trapq(toolhead.get_trapq())
        # Limits
        self.max_velocity, self.max_accel = toolhead.get_max_velocity()
        self.max_z_velocity = config.getfloat(
            'max_z_velocity', self.max_velocity, above=0.,
            maxval=self.max_velocity)
        self.max_z_accel = config.getfloat(
            'max_z_accel', self.max_accel, above=0., maxval=self.max_accel)
        self.omega_max = config.getfloat('max_angular_velocity', 6.,
                                         above=0.)
        self.alpha_max = config.getfloat('max_angular_accel', 60., above=0.)
        self.z_home_radius = config.getfloat('z_home_radius', 106.,
                                             above=0., maxval=arm_max)
        self.z_home_travel_speed = config.getfloat('z_home_travel_speed',
                                                   50., above=0.)
        self.limit_z = (1.0, -1.0)
        self.limit_xy2 = -1.
        min_z, max_z = rail_z.get_range()
        self.axes_min = toolhead.Coord((-arm_max, -arm_max, min_z))
        self.axes_max = toolhead.Coord((arm_max, arm_max, max_z))
        # Python mirror of the C decision state (start of the next move)
        self.mirror = og.RepState(1, 0.)
        self.pending_hint = None
        self.printer.load_object(config, 'force_move')
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command('ORVA_PIVOT', self.cmd_ORVA_PIVOT,
                               desc=self.cmd_ORVA_PIVOT_help)
    def get_steppers(self):
        return list(self.steppers)
    def calc_position(self, stepper_positions):
        bed_angle = stepper_positions[self.bed_stepper.get_name()]
        arm_pos = stepper_positions[self.rails[0].get_name()]
        z_pos = stepper_positions[self.rails[1].get_name()]
        return [math.cos(bed_angle) * arm_pos, math.sin(bed_angle) * arm_pos,
                z_pos]
    # Representation state ------------------------------------------------
    def get_rep_state(self):
        """State at the end of everything queued so far."""
        return self.mirror.copy()
    def bed_angle_under_arm(self):
        """Bed-frame angle currently under the arm (on its normal side)."""
        pos = self.toolhead.get_position()
        return self.mirror.angle_of(pos[:2]) + (
            math.pi if self.mirror.sign < 0 else 0.)
    def _reset_rep(self, sign, hint):
        self._lib.orva_polar_reset(self.shared, sign, hint)
        self.mirror = og.RepState(sign, hint)
    def set_position(self, newpos, homing_axes):
        x, y = newpos[0], newpos[1]
        h = math.hypot(x, y)
        if self.pending_hint is not None:
            hint = self.pending_hint
            self.pending_hint = None
        else:
            hint = self.bed_stepper.get_commanded_position()
        sign = 1
        if "x" in homing_axes or "y" in homing_axes:
            # Homing declares the bed's current angle to be 0 and puts the
            # arm at x (negative if its endstop is behind center).
            sign = -1 if x < -og.EPS_POINT else 1
            hint = 0.
        else:
            arm_cmd = self.rails[0].get_steppers()[0].get_commanded_position()
            if h > og.EPS_POINT and arm_cmd < -og.EPS_POINT:
                sign = -1
            if h > og.EPS_POINT:
                hint = math.atan2(sign * y, sign * x)
        self._reset_rep(sign, hint)
        for s in self.steppers:
            s.set_position(newpos)
        if "z" in homing_axes:
            self.limit_z = self.rails[1].get_range()
        if "x" in homing_axes and "y" in homing_axes:
            self.limit_xy2 = self.max_radius ** 2
    def clear_homing_state(self, clear_axes):
        if "x" in clear_axes or "y" in clear_axes:
            self.limit_xy2 = -1.
        if "z" in clear_axes:
            self.limit_z = (1.0, -1.0)
    def is_xy_homed(self):
        return self.limit_xy2 >= 0.
    def is_z_homed(self):
        return self.limit_z[0] <= self.limit_z[1]
    # Homing ----------------------------------------------------------------
    def _home_axis(self, homing_state, axis, rail):
        position_min, position_max = rail.get_range()
        hi = rail.get_homing_info()
        homepos = [None, None, None, None]
        homepos[axis] = hi.position_endstop
        if axis == 0:
            homepos[1] = 0.
        forcepos = list(homepos)
        if hi.positive_dir:
            forcepos[axis] -= hi.position_endstop - position_min
        else:
            forcepos[axis] += position_max - hi.position_endstop
        homing_state.home_rails([rail], forcepos, homepos)
    def _move_to_z_home(self):
        # Out to the rim Z stop along the arm's current line: radial, so the
        # bed doesn't turn and nothing on the plate is disturbed.
        a = self.bed_angle_under_arm()
        R = self.z_home_radius
        self.toolhead.manual_move([R * math.cos(a), R * math.sin(a)],
                                  self.z_home_travel_speed)
    def home(self, homing_state):
        homing_axes = homing_state.get_axes()
        home_xy = 0 in homing_axes or 1 in homing_axes
        home_z = 2 in homing_axes
        if home_z and not home_xy and not self.is_xy_homed():
            home_xy = True      # Z stop is on the rim: need the arm first
        updated_axes = []
        if home_xy:
            updated_axes = [0, 1]
        if home_z:
            updated_axes.append(2)
        homing_state.set_axes(updated_axes)
        if home_xy:
            # Declares the bed's current angle as 0: wherever it sits
            self._home_axis(homing_state, 0, self.rails[0])
        if home_z:
            self._move_to_z_home()
            self._home_axis(homing_state, 2, self.rails[1])
    # Move checks -------------------------------------------------------------
    def check_move(self, move):
        end_pos = move.end_pos
        xy2 = end_pos[0]**2 + end_pos[1]**2
        if xy2 > self.limit_xy2:
            if self.limit_xy2 < 0.:
                raise move.move_error("Must home axis first")
            raise move.move_error()
        if move.axes_d[2]:
            if end_pos[2] < self.limit_z[0] or end_pos[2] > self.limit_z[1]:
                if self.limit_z[0] > self.limit_z[1]:
                    raise move.move_error("Must home axis first")
                raise move.move_error()
            z_ratio = move.move_d / abs(move.axes_d[2])
            move.limit_speed(self.max_z_velocity * z_ratio,
                             self.max_z_accel * z_ratio)
        if not (move.axes_d[0] or move.axes_d[1]):
            return
        p0, p1 = move.start_pos[:2], end_pos[:2]
        dec, new, ok = og.decide(self.mirror, p0, p1, self.reach)
        if not ok:
            raise move.move_error(
                "Orva: move needs the arm past its reach behind center or "
                "an instant bed turn (use the orva_motion transform)")
        self.mirror = new
        # Slow down only as much as this line's geometry needs
        lim = og.center_speed_limit(p0, p1, self.omega_max, self.alpha_max)
        if lim is not None:
            v, a = lim
            if v < self.max_velocity or a < self.max_accel:
                move.limit_speed(min(v, self.max_velocity),
                                 min(a, self.max_accel))
    # Bed-only rotation at center ------------------------------------------
    def orva_pivot(self, dphi, speed, accel):
        pos = self.toolhead.get_position()
        if math.hypot(pos[0], pos[1]) > og.EPS_POINT:
            raise self.printer.command_error(
                "Orva: bed pivot needs the nozzle at center")
        if abs(dphi) < 1e-9:
            return
        new_hint = self.mirror.hint + dphi
        force_move = self.printer.lookup_object('force_move')
        force_move.manual_move(self.bed_stepper, dphi, speed, accel)
        self.pending_hint = new_hint
        self.toolhead.set_position(pos)
    cmd_ORVA_PIVOT_help = "Turn only the bed (nozzle must be at center)"
    def cmd_ORVA_PIVOT(self, gcmd):
        deg = gcmd.get_float('ANGLE')
        speed = gcmd.get_float('SPEED', 180., above=0.)
        self.orva_pivot(math.radians(deg), math.radians(speed),
                        math.radians(speed) * 4.)
        gcode_move = self.printer.lookup_object('gcode_move')
        gcode_move.reset_last_position()
    def get_status(self, eventtime):
        xy_home = "xy" if self.limit_xy2 >= 0. else ""
        z_home = "z" if self.limit_z[0] <= self.limit_z[1] else ""
        return {
            'homed_axes': xy_home + z_home,
            'axis_minimum': self.axes_min,
            'axis_maximum': self.axes_max,
            'arm_sign': self.mirror.sign,
            'reach': self.reach,
        }

def load_kinematics(toolhead, config):
    return OrvaPolarKinematics(toolhead, config)
