# Bed ring gear (laser-cut steel)

`orva_ring_gear.dxf` is the cutting file for Orva's bed gear: an internal
spur gear, module 2, 120 teeth, 20° pressure angle, 240 mm pitch circle,
262 mm outside, with 8 × Ø3.4 mm holes on a 254 mm circle for M3 screws into
the underside of the bed plate. `orva_ring_gear.svg` is the same shape to
look at.

It's driven by a stock module 2, 16-tooth steel pinion (KHK SS2-16) 104 mm
from the bed's center, with a 20T → 60T GT2 belt stage between the motor and
the pinion. Total reduction 22.5 : 1; in `printer.cfg`:

```
[stepper_bed]
gear_ratio: 120:16, 60:20
```

## Why module 2

A laser can't cut a slot much narrower than half the plate's thickness. On an
internal gear the narrowest cut is at the bottom of each tooth space. At
module 1 that's about 0.6 mm, too fine for any steel plate worth using. At
module 2, ending each space in a full-radius root keeps every cut at least
1.6 mm wide, which suits 3 mm (0.120") steel, and still clears the pinion's
tooth tips.

## Ordering (SendCutSend or similar)

1. Upload `orva_ring_gear.dxf` (units: millimetres).
2. Material: **mild steel 0.120" (3 mm)** or **4130 chromoly 0.125"**.
   Stainless 304 works too if you want it rust-free.
3. No bends, no hardware. Deburring/tumbling is worth adding if offered.
4. Check the quote shows a 262 mm outside diameter.

Laser-cut edges are within about ±0.13 mm and slightly tapered, so:

* Lightly deburr the tooth edges and oil or grease the mesh.
* Mount the pinion on a pivoting motor plate with a spring pulling it into
  the ring. The spring takes up play from cutting tolerances and wear; the
  design already leaves 0.2 mm of backlash so the gears never bind.
* Check the ring runs true when bolted to the bed plate (a dial indicator on
  the tooth tips, or just watch the pinion's spring arm as the bed turns).

## Changing it

```
python3 make_ring_gear.py --help
python3 make_ring_gear.py --teeth 110 --outer-dia 242 --bolt-circle-dia 234
python3 make_ring_gear.py --check        # simulate meshing (pip install shapely)
```

The script prints the pitch and root diameters, the narrowest cut (and so the
thickest plate a laser can cut it from), the web left around the bolt holes,
and, with `--check`, the minimum flank clearance against the pinion over a
full tooth of rotation. The current file checks clean: no overlap, 0.09 mm
minimum clearance.
