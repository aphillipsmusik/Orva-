# Orva

Firmware and software for **Orva**, a portable polar 3D printer: a round
heated bed that turns, an arm on a detachable tower that reaches 25 mm past
the bed's center, and a touch bar on the front of the base. Everything packs
flat into one bag.

Orva runs on [Klipper](https://www.klipper3d.org/). This repo adds:

* **Polar kinematics with reach past center** (`klipper/kinematics`,
  `klipper/chelper`): lines through center need no bed turn; lines near center
  slow down only as much as their own geometry needs, and flow follows.
* **Orva behaviour** (`klipper/extras`):
  * Z homes on a stop fixed in the base rim, so every startup re-measures the
    nozzle against the bed, even after the tower was reattached.
  * 9-point polar leveling that starts wherever the bed is, with every probe
    since power-on remembered. It runs at power-on, after the tower is
    reattached, and on demand.
  * A flow test outline around the first part before each print.
  * A retracting nozzle brush (down only for prints that overhang past the
    bed).
  * Tower detach/reattach detection.
  * Safety checks for first layers and the rim Z stop.
* **Wi-Fi and computer connection** (`system`, `desktop`): joins your Wi-Fi or
  starts an "Orva-XXXX" setup hotspot, a setup page, mDNS name orva.local,
  Mainsail in the browser, slicer upload, and a small `orva` command-line tool.
* **Touch bar firmware** (`touchbar`) for the LILYGO T-Display-S3 Long.
* **Slicer presets** (`slicer`) and a **parts list with vendors**
  (`docs/parts.md`).

## Start here

| | |
|---|---|
| Install on the printer, Wi-Fi, computer | [docs/connect.md](docs/connect.md) |
| How the firmware works, commands, slicer setup | [docs/firmware.md](docs/firmware.md) |
| What to buy and where | [docs/parts.md](docs/parts.md) |
| Touch bar | [touchbar/README.md](touchbar/README.md) |

Quick install on the CB1 (after flashing BTT's Klipper image):

```
git clone https://github.com/aphillipsmusik/orva-.git ~/orva
cd ~/orva && ./install.sh --hostname orva
```

## Status

The code is tested in software only: unit tests for the math, the C step
logic driven with real Klipper motion-queue moves, and full Klipper runs in
batch mode (homing, leveling memory, routing through center, pivots, flow
test, wipe, tower reattach, safety refusals). It has not run on hardware yet.
Pins, gear ratios and currents in `config/printer.cfg` must be checked
against the real build. See "Known limits" in docs/firmware.md.

## Layout

```
klipper/kinematics/orva_polar.py   kinematics (symlinked into Klipper)
klipper/chelper/kin_orva_polar.c   step generation (built automatically)
klipper/extras/orva_*.py           Orva modules
config/                            printer.cfg, orva.cfg, macros, Moonraker
system/                            Wi-Fi services and tools for the CB1
desktop/orva.py                    command-line tool for your computer
touchbar/                          ESP32-S3 firmware (PlatformIO)
slicer/                            PrusaSlicer presets
tests/                             unit, C and Klipper batch tests
docs/                              guides and parts list
install.sh                         installer
```

## License

GPL-3.0 (see LICENSE). Orva's firmware runs inside Klipper and its touch
bar links LILYGO's display libraries, both GPL-3.0, so the whole project
uses the same license. You can use, change and share it; if you distribute
a modified version, share its source under the same terms.
