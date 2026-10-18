# Orva dimensions

Orva's build volume matches a Bambu Lab P1S (256 × 256 × 256 mm), but round:
the print surface is a **256 mm circle** (the P1S plate's width) and the
build height is **256 mm**. Everything else is sized from that.

A circle 256 mm across holds about 80% of the P1S's square area; any part
that fits within 256 mm in both directions and isn't a full-size square
fits. Overhangs can also reach past the print surface out to the base edge
(see "Rim and overhangs").

## Build volume

| | |
|---|---|
| Print surface | Ø256 mm (radius 128) |
| Build height | 256 mm |
| Overhang reach (above the first layers) | to radius 152 mm, just inside the base edge |
| Arm reach past center | 32 mm (the arm covers 160 mm, 5/8 of the diameter) |
| Arm travel | −32 to +152 mm (184 mm) |

## Base

| | |
|---|---|
| Outside diameter | 310 mm |
| Height | ~56 mm (bed top flush with the base top) |
| Bed opening | Ø282 mm |
| Rim (stationary ring around the bed) | radius 141–155 mm |
| Wiper brush | centred at radius 147 mm (wipes 144.5–149.5) |
| Z-min plunger | radius ~147.5 mm, beside the brush |
| Feet | 4 × Ø15 mm, set in from the rounded edge |

## Bed

| | |
|---|---|
| Bed plate (hot plate) | Ø280 mm, 6 mm cast tooling plate (MIC-6); the outer ring past the heater carries the ball groove |
| PEI sheet | Ø265 mm round spring steel on a magnetic base |
| Heater | Ø250 mm round silicone, 48 V, ~180 W, 100k NTC |
| Rotation | ball race: 101 × Ø4 mm steel balls on a Ø271 mm circle, running in a groove cut into the hot plate's underside and a channel cut into the base (see hardware/bed_race) |
| Radial location | 6806 bearing (30 × 42 × 7) at the hub, around the slip ring; wave springs under the hub nut hold the plate down on the balls |
| Ring gear | laser-cut steel, module 2, 120 teeth, Ø262 mm outside, 3 mm thick, 8 × M3 to the hot plate underside (inside the ball race) |
| Pinion | module 2, 16 teeth, 104 mm from center |
| Belt stage | GT2 20T on the motor → 60T on the pinion shaft |
| Total bed reduction | 22.5 : 1 (72,000 microsteps per turn; ~0.011 mm per microstep at the edge) |

## Tower

| | |
|---|---|
| Column | 2020 extrusion, ~380 mm |
| Arm | 2020 (or 2040 for stiffness), ~210 mm |
| Nozzle to column centre | ~201 mm (keeps the column clear of the base at the arm's innermost position) |
| Z travel | 256 mm + homing margin (`position_max: 260`) |

## r axis (inside the base)

| | |
|---|---|
| Shaft | 20×40 V-slot, ~280 mm |
| Rack | module 1 steel, 200 mm |
| Pinion | module 1, 20 teeth (62.83 mm per turn) |

## Leveling, flow test, firmware limits

| Setting | Value |
|---|---|
| Edge probe points | 6 at radius 110 mm, every 60° |
| Center probe points | 3 at radius 23 mm (inside the 32 mm reach, so the "back" point needs no bed turn) |
| Flow test outline limit | radius 126.8 mm |
| First layers allowed to | radius 128 mm |
| Overhangs must clear the Z-min plunger | 3.5 mm above the bed at radius ~147.5 mm |

## Footprint and carrying

| | |
|---|---|
| While printing | ~310 mm wide; ~525 mm long with the arm fully out (base plus tower) |
| Height while printing | ~470 mm to the top of the tower |
| Packed | base and tower side by side in one layer: bag about 410 × 490 × 80 mm |

## Power at this size

The 256 mm bed has about 1.6× the area of the earlier 200 mm design. With a
240 W USB-C supply, the bed heater is held to ~180 W and heating is
sequential (bed first, then nozzle), so expect a few extra minutes to reach
bed temperature.
