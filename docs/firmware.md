# Orva firmware

Orva runs [Klipper](https://www.klipper3d.org/). This repo adds a custom
kinematics module and a set of Klipper "extras" on top of it, without
modifying Klipper itself: `install.sh` symlinks the files into your Klipper
checkout and hides them from its git status, so Klipper and Moonraker updates
keep working.

## Pieces

| File | What it does |
|---|---|
| `klipper/kinematics/orva_polar.py` | Polar kinematics: bed angle + arm that can reach 32 mm past center. Z homing on the rim stop. Bed-only pivots. |
| `klipper/chelper/kin_orva_polar.c` | Step generation for the bed and arm. Compiled automatically into its own small library the first time Klipper starts. |
| `klipper/extras/orva_geometry.py` | The math shared by everything else (no Klipper imports, unit tested). |
| `klipper/extras/orva_motion.py` | G-code move transform: routing through center, pivots, splitting near center, Z correction, safety checks. |
| `klipper/extras/orva_level.py` | 9-point polar leveling with memory since power-on. |
| `klipper/extras/orva_flowtest.py` | Flow test outline around the first object. |
| `klipper/extras/orva_wiper.py` | Retracting brush and the wipe routine. |
| `klipper/extras/orva_tower.py` | Tower detach/reattach detection. |
| `klipper/extras/orva_touchbar.py` | USB serial link to the touch bar. |
| `config/printer.cfg` | Hardware config for the Manta M4P + CB1 + EBB36 (check pins). |
| `config/orva.cfg`, `config/orva_macros.cfg` | Orva behaviour and macros (startup, PRINT_START/END, tower, shutdown). |

## How the motion works

A point on the bed is printed by turning the bed to angle φ and sliding the
arm to distance r. Every point has two solutions: (φ, +r) and (φ + 180°, −r).
The second, "behind center", is only possible within the arm's 32 mm reach
past center.

The two solutions can only be swapped where they meet: at the exact center.
That has consequences worth knowing:

* **A line straight through center needs no bed turn.** The arm just runs
  through center into its reach on the other side. Leveling uses this for
  the "back" center point.
* **A line that passes close to (but not through) center still needs a fast
  bed swing**, whichever solution is used. The firmware slows such a line only
  around its closest point: the bed's turn rate there is
  `speed × (line's distance from center) / r²`, capped by
  `max_angular_velocity` and `max_angular_accel`. Long moves near center are
  split into short pieces so each piece slows only as much as it needs.
  Klipper meters the extruder per millimeter of path over the bed, so flow
  follows the speed automatically and line width stays even.
* **Lines passing within `center_snap` (0.3 mm) of center** are routed exactly
  through it (moving the line by at most 0.3 mm at that one point).
* **When a line continues past center beyond the arm's reach**, the nozzle
  stops at center, the bed turns (a "pivot", no extrusion during it), and the
  line continues on the normal side. The touch bar and Mainsail show nothing
  special; you'll just see a short pause at center.
* **When the arm is behind center and the next move goes out of reach**, a
  travel move comes back through center first (with a pivot if needed). For a
  printing move, the nozzle travels to center and back out to the start point
  on the normal side, then prints the line. That travel isn't retracted, so
  slicers should avoid stopping lines just past center.

The C code keeps the bed and arm steppers agreeing on which solution each
move uses, even though Klipper generates each stepper's steps in its own
thread and in any order: each move's choice is computed once, from the
previous move's choice, and shared under a lock.

**Homing.** `G28` homes the arm against its endstop in the base and declares
the bed's current angle to be 0, so the bed never has to turn to a home
position. Z homes against the sealed switch fixed in the rim: the arm first
moves out to `z_home_radius` along its current line (no bed turn), then the
nozzle lowers until the tab on the shroud presses the plunger (nozzle 0.5 mm
above the bed). Because the stop is on the base and the tab is next to the
nozzle, every Z home measures the nozzle against the bed itself.

## Leveling

* Runs at power-on (`ORVA_STARTUP`), automatically when the tower is
  reattached, and on demand (`ORVA_RELEVEL`, the touch bar's Re-level button,
  or `orva relevel` from a computer). Picking a new print does **not**
  re-level; `PRINT_START` only levels if nothing valid is remembered.
* Starts wherever the bed is sitting. 6 points every 60° at 110 mm, then 3 near
  center at 23 mm: the first on the last edge point's line, the second
  directly behind it past center (no bed turn), the third a quarter turn away.
* Every probe since power-on is kept and refit together (tilt + dome, plus
  saddle and twist once there are 12+ points). Each run usually starts at a
  different angle, so the map fills in. Power-off or a Klipper restart clears
  it.
* Uses Klipper's `PROBE`, so any `[probe]`-compatible sensor works. On a
  rotating bed a probe offset turns with the bed; Orva treats `x_offset` as
  along the arm and `y_offset` as across it. A nozzle-contact probe (offset 0)
  is simplest.

## Flow test

`ORVA_FLOW_TEST` (called from `PRINT_START`) prints one outline 3.5 mm outside
the first object's footprint, in three sections at rising target speed. The
footprint comes from the slicer's `EXCLUDE_OBJECT_DEFINE` lines, so turn on
**Label objects: firmware specific** in the slicer.

Measuring how much of the commanded flow actually came out needs a sensor
(e.g. a load cell under the extruder). That hardware isn't chosen yet, so
measurement is a small plug-in class in `orva_flowtest.py`:

```python
class MyBackend:
    name = 'loadcell'
    def __init__(self, printer, config): ...
    def start_section(self, index, target_flow): ...   # mm^3/s
    def end_section(self, index):
        return delivered_fraction   # e.g. 0.97, or None
BACKENDS['loadcell'] = MyBackend
```

With `measure: none` (default) the outline still primes the nozzle and the
configured `default_flow_ratio` / `default_pressure_advance` are applied.

## Wiper

The brush rises at power-on and stays up for normal prints. If any object's
outline reaches past the bed (`overhang_radius`, 128 mm), `ORVA_WIPER_MODE
MODE=AUTO` switches to overhang mode: the brush stays down and `ORVA_WIPE`
raises it only at a bed angle where nothing overhangs, while the bed is
stopped. The Z-min switch is not on the lift.

## Safety checks (orva_motion)

* Extrusion below `first_layer_max_z` (0.6 mm) beyond `first_layer_radius`
  (128 mm) is refused: only overhangs may reach past the print surface.
* Extrusion below `zstop_clear_z` (3.5 mm) at the Z stop's radius is refused:
  it would hit the fixed plunger as the bed turns.

## Commands

| Command | |
|---|---|
| `G28` / `G28 Z` | Home (arm declares the current bed angle as 0; Z on the rim stop) |
| `ORVA_LEVEL` | Home Z and probe the 9 points (adds to the memory) |
| `ORVA_ENSURE_LEVEL` | Level only if not leveled since power-on / tower reattach |
| `ORVA_RELEVEL` | Macro: `G28 Z` + `ORVA_LEVEL` |
| `ORVA_LEVEL_STATUS` / `ORVA_LEVEL_CLEAR` | Show / forget the remembered surface |
| `ORVA_FLOW_TEST [OBJECT=name]` | Flow test outline |
| `ORVA_WIPE [SAFE_Z=..]` | Wipe on the brush |
| `ORVA_WIPER STATE=UP\|DOWN` | Move the brush |
| `ORVA_WIPER_MODE MODE=AUTO\|NORMAL\|OVERHANG` | Brush behaviour |
| `ORVA_TOWER STATE=ATTACHED\|DETACHED` | Tell Orva about the tower (if no sense pin) |
| `ORVA_PIVOT ANGLE=deg` | Turn only the bed (nozzle at center) |
| `ORVA_MOTION_STATUS` | Arm side, bed angle, pivot count |
| `ORVA_TOUCHBAR STATE=OFF\|ON MSG=..` | Drive the touch bar |
| `ORVA_SHUTDOWN` | Park, brush down, shutdown animation, power off |

## Slicer setup

Import `slicer/orva.ini` into PrusaSlicer (OrcaSlicer: same settings by hand):

* Round bed, 256 mm diameter (128 mm radius), origin at the center, 256 mm
  tall. `slicer/orva-overhang.ini` uses a 146.5 mm radius for parts that
  overhang past the print surface (keep their first layers inside 128 mm; the
  firmware refuses otherwise).
* G-code flavor **Klipper**, **Label objects: firmware specific**.
* Start G-code `PRINT_START BED=[first_layer_bed_temperature]
  EXTRUDER=[first_layer_temperature]`, end G-code `PRINT_END`.
* Relative extrusion on, arc fitting off.
* Physical printer: Klipper / Moonraker at `orva.local`.

## Tests

```
python3 tests/test_geometry.py                         # math, no Klipper needed
KLIPPER_DIR=~/klipper python3 tests/test_kinematics_c.py   # C step logic on real trapq moves
KLIPPER_DIR=~/klipper tests/klippy/run.sh              # full Klipper batch run
```

The batch run needs a Linux-process MCU dictionary: in the Klipper checkout,
`printf 'CONFIG_MACH_LINUX=y\n' > .config && make olddefconfig && make`.
GitHub Actions runs all three plus a touch bar build on every push.

## Known limits

* Not yet run on real hardware: pins, gear ratios, currents and the probe
  section in `config/printer.cfg` must be checked against the actual build.
* Input shaping hasn't been tested with this kinematics; leave it off for now.
* Flow measurement needs a sensor and a backend (see above).
* Pivots at center flush the motion queue, so they cause a short stop.
