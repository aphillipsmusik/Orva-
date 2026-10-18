# Orva tower: notices when the tower is detached and reattached.
#
# A sense contact in the dovetail joint (one of the pogo pins shorted to
# ground by a pad on the tower) tells the firmware whether the tower is on.
#  * Detached: Z homing is forgotten (the tower and its Z carriage can move
#    freely), the leveling is marked stale, and `detach_gcode` runs (by
#    default it pauses a running print).
#  * Reattached: `attach_gcode` runs (by default: home Z and re-level),
#    because the joint may seat a little differently every time.
# Without a sense pin, use ORVA_TOWER STATE=ATTACHED|DETACHED.
#
# Copyright (C) 2026  Orva contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging


class OrvaTower:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.attach_template = gcode_macro.load_template(
            config, 'attach_gcode', 'ORVA_ON_TOWER_ATTACH')
        self.detach_template = gcode_macro.load_template(
            config, 'detach_gcode', 'ORVA_ON_TOWER_DETACH')
        self.attached = True
        self.changes = 0
        self.ready = False
        pin = config.get('sense_pin', None)
        if pin is not None:
            buttons = self.printer.load_object(config, 'buttons')
            buttons.register_buttons([pin], self._sense_callback)
        self.printer.register_event_handler("klippy:ready",
                                            self._handle_ready)
        self.gcode.register_command(
            'ORVA_TOWER', self.cmd_ORVA_TOWER,
            desc="Tell Orva the tower was attached or detached "
                 "(STATE=ATTACHED|DETACHED)")

    def _handle_ready(self):
        self.ready = True

    def _sense_callback(self, eventtime, state):
        # Pin reads pressed (1) when the tower's pad shorts the contact
        self.reactor.register_callback(
            lambda e: self._set_attached(bool(state), from_command=False))

    def _set_attached(self, attached, from_command):
        if attached == self.attached:
            return
        self.attached = attached
        self.changes += 1
        toolhead = self.printer.lookup_object('toolhead')
        kin = toolhead.get_kinematics()
        level = self.printer.lookup_object('orva_level', None)
        if level is not None:
            level.invalidate()
        if not attached:
            kin.clear_homing_state("z")
        if not self.ready:
            return
        template = self.attach_template if attached else self.detach_template
        script = template.render()
        try:
            if from_command:
                self.gcode.run_script_from_command(script)
            else:
                self.gcode.run_script(script)
        except Exception:
            logging.exception("orva_tower: %s script failed",
                              "attach" if attached else "detach")

    def cmd_ORVA_TOWER(self, gcmd):
        state = gcmd.get('STATE').upper()
        if state not in ('ATTACHED', 'DETACHED'):
            raise gcmd.error("STATE must be ATTACHED or DETACHED")
        self._set_attached(state == 'ATTACHED', from_command=True)

    def get_status(self, eventtime):
        return {'attached': self.attached, 'changes': self.changes}


def load_config(config):
    return OrvaTower(config)
