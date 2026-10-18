# Orva touch bar link: talks to the LILYGO T-Display-S3 Long on the front
# of the base over USB serial (newline-delimited JSON).
#
#  printer -> bar:  {"t":"s", ...}   status, 4 times a second
#                   {"t":"map", ...} leveling points, when they change
#                   {"t":"off"}      play the shutdown animation
#  bar -> printer:  {"cmd":"relevel"} etc. (whitelisted, see COMMANDS)
#
# The bar plays the O startup animation by itself when it powers up, then
# shows whatever phase the printer reports.
#
# Copyright (C) 2026  Orva contributors
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import json, logging, os

COMMANDS = {
    'relevel': 'ORVA_RELEVEL',
    'pause': 'PAUSE',
    'resume': 'RESUME',
    'cancel': 'CANCEL_PRINT',
    'home': 'G28',
    'wiper_up': 'ORVA_WIPER STATE=UP',
    'wiper_down': 'ORVA_WIPER STATE=DOWN',
    'shutdown': 'ORVA_SHUTDOWN',
}


class OrvaTouchbar:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.port = config.get('serial')
        self.baud = config.getint('baud', 115200)
        self.net_file = config.get('net_status_file', '/run/orva/net.json')
        self.interval = config.getfloat('interval', 0.25, above=0.05)
        self.ser = None
        self.fd_handle = None
        self.rx = b''
        self.timer = None
        self.last_map_key = None
        self.next_open = 0.
        self.off = False
        self.net = {}
        self.net_time = 0.
        self.printer.register_event_handler("klippy:ready",
                                            self._handle_ready)
        self.printer.register_event_handler("klippy:shutdown",
                                            self._handle_shutdown)
        self.printer.register_event_handler("klippy:disconnect",
                                            self._close)
        self.gcode.register_command(
            'ORVA_TOUCHBAR', self.cmd_ORVA_TOUCHBAR,
            desc="Send to the touch bar: STATE=OFF plays the shutdown "
                 "animation, MSG=text shows a message")

    # Serial ------------------------------------------------------------------
    def _open(self):
        import serial
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0,
                                     write_timeout=0)
        except Exception as e:
            self.ser = None
            return False
        self.fd_handle = self.reactor.register_fd(self.ser.fileno(),
                                                  self._on_read)
        self.last_map_key = None
        self._send({'t': 'hello'})
        logging.info("orva_touchbar: connected on %s", self.port)
        return True

    def _close(self):
        if self.fd_handle is not None:
            self.reactor.unregister_fd(self.fd_handle)
            self.fd_handle = None
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def _send(self, obj):
        if self.ser is None:
            return
        try:
            self.ser.write((json.dumps(obj, separators=(',', ':'))
                            + "\n").encode())
        except Exception:
            # Full buffer (bar busy) drops the message; a real error closes
            if not self.ser.is_open:
                self._close()

    def _on_read(self, eventtime):
        try:
            data = self.ser.read(4096)
        except Exception:
            self._close()
            return
        self.rx += data
        while b'\n' in self.rx:
            line, self.rx = self.rx.split(b'\n', 1)
            try:
                msg = json.loads(line.decode('utf-8', 'ignore'))
            except ValueError:
                continue
            script = COMMANDS.get(str(msg.get('cmd', '')))
            if script:
                self.reactor.register_callback(
                    lambda e, s=script: self._run(s))
        if len(self.rx) > 4096:
            self.rx = b''

    def _run(self, script):
        try:
            self.gcode.run_script(script)
        except Exception as e:
            self._send({'t': 'msg', 'text': str(e)[:80]})

    # Status ------------------------------------------------------------------
    def _handle_ready(self):
        self.off = False
        self.timer = self.reactor.register_timer(self._tick, self.reactor.NOW)

    def _handle_shutdown(self):
        self._send({'t': 'err', 'text': 'Firmware stopped'})

    def _status(self, name, eventtime):
        obj = self.printer.lookup_object(name, None)
        if obj is None or not hasattr(obj, 'get_status'):
            return {}
        try:
            return obj.get_status(eventtime)
        except Exception:
            return {}

    def _read_net(self, eventtime):
        if eventtime - self.net_time < 5.:
            return self.net
        self.net_time = eventtime
        try:
            with open(self.net_file) as f:
                self.net = json.load(f)
        except Exception:
            self.net = {}
        return self.net

    def _tick(self, eventtime):
        if self.ser is None:
            if eventtime < self.next_open or not self._open():
                self.next_open = eventtime + 2.
                return eventtime + 1.
        if self.off:
            return eventtime + 1.
        ps = self._status('print_stats', eventtime)
        ds = self._status('display_status', eventtime)
        lv = self._status('orva_level', eventtime)
        ft = self._status('orva_flowtest', eventtime)
        tw = self._status('orva_tower', eventtime)
        wp = self._status('orva_wiper', eventtime)
        ex = self._status('extruder', eventtime)
        bed = self._status('heater_bed', eventtime)
        state = ps.get('state', 'standby')
        if lv.get('active'):
            phase = 'level' if lv.get('progress', 0) else 'home'
        elif ft.get('active'):
            phase = 'flow'
        elif state in ('printing', 'paused'):
            phase = 'print' if state == 'printing' else 'paused'
        elif tw and not tw.get('attached', True):
            phase = 'detached'
        elif state == 'error':
            phase = 'error'
        else:
            phase = 'idle'
        info = ps.get('info') or {}
        net = self._read_net(eventtime)
        msg = {
            't': 's', 'ph': phase,
            'pct': round(100. * (ds.get('progress') or 0.), 1),
            'ly': info.get('current_layer') or 0,
            'lyt': info.get('total_layer') or 0,
            'file': (ps.get('filename') or '')[-40:],
            'te': round(ex.get('temperature', 0.), 1),
            'tet': ex.get('target', 0.),
            'tb': round(bed.get('temperature', 0.), 1),
            'tbt': bed.get('target', 0.),
            'lvp': lv.get('progress', 0),
            'lvr': lv.get('runs', 0),
            'lvn': lv.get('point_count', 0),
            'fts': ft.get('section', 0),
            'ftf': ft.get('target_flows', []),
            'ftr': ft.get('results', []),
            'wp': wp.get('mode', ''),
            'net': {k: net.get(k) for k in ('mode', 'ssid', 'ip',
                                            'hotspot_ssid', 'hotspot_pass')
                    if net.get(k)},
        }
        self._send(msg)
        key = (lv.get('runs'), lv.get('progress'))
        if key != self.last_map_key:
            self.last_map_key = key
            self._send({'t': 'map',
                        'cur': [[round(v, 3) for v in p]
                                for p in lv.get('last_run', [])],
                        'old': [[round(v, 3) for v in p]
                                for p in lv.get('history', [])][-120:]})
        return eventtime + self.interval

    def cmd_ORVA_TOUCHBAR(self, gcmd):
        state = gcmd.get('STATE', None)
        text = gcmd.get('MSG', None)
        if state is not None:
            if state.upper() == 'OFF':
                self._send({'t': 'off'})
                self.off = True
            elif state.upper() == 'ON':
                self.off = False
                self._send({'t': 'hello'})
        if text is not None:
            self._send({'t': 'msg', 'text': text[:80]})

    def get_status(self, eventtime):
        return {'connected': self.ser is not None}


def load_config(config):
    return OrvaTouchbar(config)
