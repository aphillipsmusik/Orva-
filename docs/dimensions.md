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
| Overhang reach (above the first layers) | to radius 146.5 mm, just inside the base edge |
| Arm reach past center | 32 mm (the arm covers 160 mm, 5/8 of the diameter) |
| Arm travel | −32 to +146.5 mm (178.5 mm) |

## Base

| | |
|---|---|
| Outside diameter | 300 mm |
| Height | ~56 mm (bed top flush with the base top) |
| Bed opening | Ø270 mm |
| Rim (stationary ring around the bed) | radius 135–150 mm |
| Wiper brush | centred at radius 141 mm (wipes 138.5–143.5) |
| Z-min plunger | radius ~141.6 mm, beside the brush |
| Feet | 4 × Ø15 mm, set in from the rounded edge |

## Bed

| | |
|---|---|
| Bed plate | Ø266 mm, 6 mm cast tooling plate (MIC-6) |
| PEI sheet | Ø265 mm round spring steel on a magnetic base |
| Heater | Ø250 mm round silicone, 48 V, ~180 W, 100k NTC |
| Bearing | thin-section, 7" (178 mm) bore, 4-point contact |
| Ring gear | laser-cut steel, module 2, 120 teeth, Ø262 mm outside, 3 mm thick, 8 × M3 to the bed plate underside |
| Pinion | module 2, 16 teeth, 104 mm from center |
| Belt stage | GT2 20T on the motor → 60T on the pinion shaft |
| Total bed reduction | 22.5 : 1 (72,000 microsteps per turn; ~0.011 mm per microstep at the edge) |

## Tower

| | |
|---|---|
| Column | 2020 extrusion, ~380 mm |
| Arm | 2020 (or 2040 for stiffness), ~210 mm |
| Nozzle to column centre | ~196 mm (keeps the column clear of the base at the arm's innermost position) |
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
| Overhangs must clear the Z-min plunger | 3.5 mm above the bed at radius ~141.6 mm |

## Footprint and carrying

| | |
|---|---|
| While printing | ~300 mm wide; ~505 mm long with the arm fully out (base plus tower) |
| Height while printing | ~470 mm to the top of the tower |
| Packed | base and tower side by side in one layer: bag about 400 × 480 × 80 mm |

## Power at this size

The 256 mm bed has about 1.6× the area of the earlier 200 mm design. With a
240 W USB-C supply, the bed heater is held to ~180 W and heating is
sequential (bed first, then nozzle), so expect a few extra minutes to reach
bed temperature. See docs/parts.md for the details.
