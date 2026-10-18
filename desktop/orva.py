#!/usr/bin/env python3
"""orva: talk to an Orva printer from your computer over Wi-Fi.

Works on Windows, macOS and Linux with plain Python 3 (no extra packages).
It uses Moonraker's HTTP API, the same one Mainsail, Fluidd and
OrcaSlicer use.

  orva status                      what the printer is doing
  orva print model.gcode           upload a file and start printing it
  orva upload model.gcode          upload only
  orva files                       list files on the printer
  orva pause | resume | cancel
  orva relevel                     re-home Z and re-level the bed
  orva gcode "G28"                 send any G-code / macro
  orva open                        open the web interface (Mainsail)
  orva wifi scan                   (hotspot mode) list networks the printer sees
  orva wifi connect SSID PASSWORD  (hotspot mode) put the printer on your Wi-Fi
  orva shutdown                    park, lower the brush and power off

The printer is found as orva.local (mDNS).  When it is in setup-hotspot mode
(joined to its "Orva-XXXX" network) it is at 10.42.0.1.  Use --host to give
an address directly, or set ORVA_HOST.
"""
import argparse, json, mimetypes, os, socket, sys, time, uuid, webbrowser
from urllib import request, parse, error

DEFAULT_HOSTS = ["orva.local", "10.42.0.1"]


def find_host(explicit):
    if explicit:
        return explicit
    env = os.environ.get("ORVA_HOST")
    if env:
        return env
    for h in DEFAULT_HOSTS:
        try:
            socket.getaddrinfo(h, 80)
            with socket.create_connection((h, 80), timeout=2):
                return h
        except OSError:
            continue
    sys.exit("Can't find the printer. Is it on the same Wi-Fi? "
             "Try --host <ip address>.")


class Printer:
    def __init__(self, host):
        self.base = "http://%s" % host
        self.host = host

    def _req(self, method, path, data=None, headers=None, timeout=30):
        req = request.Request(self.base + path, data=data, method=method,
                              headers=headers or {})
        try:
            with request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode()
        except error.HTTPError as e:
            msg = e.read().decode(errors="ignore")
            try:
                msg = json.loads(msg)["error"]["message"]
            except Exception:
                pass
            sys.exit("Printer said: %s" % msg)
        except error.URLError as e:
            sys.exit("Can't reach %s: %s" % (self.host, e.reason))
        return json.loads(body) if body else {}

    def get(self, path):
        return self._req("GET", path)

    def post(self, path, obj=None):
        data = json.dumps(obj or {}).encode()
        return self._req("POST", path, data,
                         {"Content-Type": "application/json"})

    def gcode(self, script):
        return self._req("POST", "/printer/gcode/script?script="
                         + parse.quote(script), timeout=600)

    def upload(self, path, start=False):
        boundary = uuid.uuid4().hex
        name = os.path.basename(path)
        with open(path, "rb") as f:
            content = f.read()
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        parts = []
        if start:
            parts.append(b"--%s\r\nContent-Disposition: form-data; "
                         b"name=\"print\"\r\n\r\ntrue\r\n" % boundary.encode())
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"file\";"
                      " filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
                      % (boundary, name, ctype)).encode() + content + b"\r\n")
        parts.append(("--%s--\r\n" % boundary).encode())
        body = b"".join(parts)
        return self._req("POST", "/server/files/upload", body, {
            "Content-Type": "multipart/form-data; boundary=" + boundary},
            timeout=600)

    def status(self):
        objs = "print_stats&display_status&extruder&heater_bed&toolhead" \
               "&orva_level&orva_tower&orva_wiper&orva_flowtest"
        return self.get("/printer/objects/query?" + objs)["result"]["status"]


def cmd_status(p, a):
    s = p.status()
    ps = s.get("print_stats", {})
    lv = s.get("orva_level", {})
    tw = s.get("orva_tower", {})
    ex, bed = s.get("extruder", {}), s.get("heater_bed", {})
    prog = 100. * (s.get("display_status", {}).get("progress") or 0.)
    print("State:     %s %s" % (ps.get("state", "?"),
                                ps.get("filename", "") or ""))
    if ps.get("state") in ("printing", "paused"):
        info = ps.get("info") or {}
        print("Progress:  %.1f%%  layer %s/%s" % (
            prog, info.get("current_layer") or "?",
            info.get("total_layer") or "?"))
    print("Nozzle:    %.1f / %.0f C" % (ex.get("temperature", 0),
                                         ex.get("target", 0)))
    print("Bed:       %.1f / %.0f C" % (bed.get("temperature", 0),
                                         bed.get("target", 0)))
    print("Homed:     %s" % (s.get("toolhead", {}).get("homed_axes") or "no"))
    if lv:
        print("Leveling:  %s, %d runs, %d points in map" % (
            "valid" if lv.get("valid") else "needed",
            lv.get("runs", 0), lv.get("point_count", 0)))
    if tw:
        print("Tower:     %s" % ("attached" if tw.get("attached")
                                 else "DETACHED"))


def cmd_wifi(p, a):
    setup = "http://%s:8090" % p.host
    if a.action == "scan":
        with request.urlopen(setup + "/api/scan", timeout=30) as r:
            for n in json.loads(r.read().decode()):
                print("%-32s %3d%% %s" % (n["ssid"], n["signal"],
                                          "secured" if n["secure"] else ""))
    elif a.action == "connect":
        if not a.ssid:
            sys.exit("usage: orva wifi connect SSID [PASSWORD]")
        data = json.dumps({"ssid": a.ssid,
                           "password": a.password or ""}).encode()
        req = request.Request(setup + "/api/connect", data=data, method="POST",
                              headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=90) as r:
                res = json.loads(r.read().decode())
        except error.HTTPError as e:
            res = json.loads(e.read().decode() or "{}")
        except error.URLError:
            # The hotspot goes away as the printer joins your network
            res = {"ok": True, "message": "hotspot closed while switching"}
        if res.get("ok"):
            print("Done. Rejoin your own Wi-Fi; the printer will be at "
                  "http://orva.local")
        else:
            sys.exit("Failed: %s" % res.get("message"))
    else:
        with request.urlopen(setup + "/api/state", timeout=10) as r:
            print(r.read().decode())


def main():
    ap = argparse.ArgumentParser(prog="orva", description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--host", help="printer address (default: orva.local)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sp = sub.add_parser("print"); sp.add_argument("file")
    sp = sub.add_parser("upload"); sp.add_argument("file")
    sub.add_parser("files")
    for c in ("pause", "resume", "cancel", "relevel", "open", "shutdown"):
        sub.add_parser(c)
    sp = sub.add_parser("gcode"); sp.add_argument("script")
    sp = sub.add_parser("wifi")
    sp.add_argument("action", nargs="?", default="state",
                    choices=["state", "scan", "connect"])
    sp.add_argument("ssid", nargs="?")
    sp.add_argument("password", nargs="?")
    a = ap.parse_args()
    p = Printer(find_host(a.host))
    if a.cmd == "status":
        cmd_status(p, a)
    elif a.cmd in ("print", "upload"):
        p.upload(a.file, start=(a.cmd == "print"))
        print("%s %s" % ("Printing" if a.cmd == "print" else "Uploaded",
                         os.path.basename(a.file)))
    elif a.cmd == "files":
        for f in p.get("/server/files/list?root=gcodes")["result"]:
            print("%-50s %8.1f kB" % (f["path"], f["size"] / 1024.))
    elif a.cmd == "pause":
        p.post("/printer/print/pause")
    elif a.cmd == "resume":
        p.post("/printer/print/resume")
    elif a.cmd == "cancel":
        p.post("/printer/print/cancel")
    elif a.cmd == "relevel":
        print("Re-leveling...")
        p.gcode("ORVA_RELEVEL")
        print("Done.")
    elif a.cmd == "shutdown":
        p.gcode("ORVA_SHUTDOWN")
    elif a.cmd == "gcode":
        p.gcode(a.script)
    elif a.cmd == "open":
        webbrowser.open("http://%s" % p.host)
    elif a.cmd == "wifi":
        cmd_wifi(p, a)


if __name__ == "__main__":
    main()
