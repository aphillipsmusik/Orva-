# Orva parts list (bought parts)

What you can buy off the shelf for Orva, and where (US sellers preferred).
Custom-made parts (base shell, curved bracket, tower foot, hotend shroud,
wheel block, bezel, wiper lift carriage, Z stopper tab, carry bag) are not
listed here; their STLs come from the concept page.

Checked October 2026. Prices change; "~" means approximate. A dash in the
link column means no specific listing was checked, so any reputable
equivalent works.

Sizes are for the P1S-class build: a **256 mm round print surface** and
**256 mm build height** (see docs/dimensions.md).

**Not off the shelf:** the bed ring gear is laser-cut from steel to our file
(hardware/ring_gear), the round 48 V bed heater is a custom order, and there
is no ready-made nozzle load cell (use a contact probe instead). Details are
under "Gaps / design flags".

## Control

| Part | Pick (model) | Vendor | Price (USD) | Link | Notes |
|---|---|---|---|---|---|
| Mainboard + compute module | **BTT Manta M4P + CB1** | BIQU (BTT official) | ~$84 board, ~$110 with CB1 | [biqu.equipment](https://biqu.equipment/collections/motor-driver/products/manta-m4p-m8p) | 4 plug-in driver slots (drivers sold separately). **No CAN port.** Logic power 12/24 V only; motor power input up to 56 V (jumper). ([wiki](https://global.bttwiki.com/M4P.html)) |
| CB1 Wi-Fi | built in | — | — | [CB1 wiki](https://global.bttwiki.com/CB1.html) | **2.4 GHz only.** Get the 1 GB RAM version. A metal base blocks Wi-Fi: plan an external antenna. |
| Stepper drivers ×3–4 | BTT TMC2209 (plug-in) | BIQU | ~$6–8 each | (same page) | **Max ~28 V**: run motors from the 24 V rail. The 4th slot is spare when the extruder is on the EBB36. |
| Toolhead board | **BTT EBB36 Gen2 V1.0** (USB or CAN) | BIQU | $48.99 | [biqu.equipment](https://biqu.equipment/products/bigtreetech-ebb36-42-can-bus-u2c-v2-1-klipper-board) | Use **USB mode** (the M4P has no CAN). Made for 36 mm NEMA14 motors; plan a printed adapter for a round pancake motor. |
| USB-to-CAN adapter | BTT U2C V2.1 | BIQU | $23.99 | (same page) | Only if you run the EBB36 in CAN mode. |
| Touch bar | **LILYGO T-Display-S3 Long** (3.4", 180×640, touch) | LILYGO on Tindie | $30.68 | [tindie.com](https://www.tindie.com/products/lilygo/t-display-s3-long-34-esp32-s3-development-board/) | In stock. Connects to the CB1 by USB (see touchbar/). |

## Power

| Part | Pick (model) | Vendor | Price (USD) | Link | Notes |
|---|---|---|---|---|---|
| 240 W USB-C PD 3.1 charger | **Framework Power Adapter 240W** | Framework | $109 | [frame.work](https://frame.work/products/power-adapter-240w) | 48 V / 5 A, includes a 240 W cable. Pre-order at the time of checking. Alternative: HKY 240W 48V/5A GaN, ~$40–60 ([Amazon](https://www.amazon.com/HKY-Adapter-Detachable-Laptops-Speaker/dp/B0F99CJ5K7)). Multi-port chargers don't give 240 W on one port. |
| 240 W cable (spare/longer) | Anker Prime USB-C 240W | Amazon / Anker | ~$15–26 | — | Or StarTech USB2EPR1M. |
| 48 V PD trigger board | **ChargerLAB POWER-Z SINK240** | Amazon US | ~$20–30 | [chargerlab.com](https://www.chargerlab.com/chargerlab-power-z-sink240-a-compact-usb-pd3-1-48v-trigger-board/) | Requests up to 48 V. Sold as a test board with no continuous-current rating: heatsink it and derate. |
| 48 → 24 V converter | **Mean Well SD-200C-24** (24 V 8.4 A) | TRC Electronics | ~$60–75 | [trcelectronics.com](https://trcelectronics.com/products/mean-well-sd-200c-24) | For boards, motors, hotend, fans. |
| 48 → 5 V converter | **Pololu D36V50F5** (5 V 5.5 A) | Pololu | ~$25 | [pololu.com](https://www.pololu.com/product/4091) | CB1, touch bar, servo. Rated 50 V max input: add a TVS diode or pick a 60 V part. |
| Bed switch | 48 V DC SSR or logic-level MOSFET module | Amazon / Digi-Key | ~$10 | — | Driven by the M4P bed output; switches the 48 V heater. |

## I/O

| Part | Pick (model) | Vendor | Price (USD) | Link | Notes |
|---|---|---|---|---|---|
| Panel USB-C data | **Adafruit 4218** round panel-mount USB-C extension | Adafruit | $9.95 | [adafruit.com](https://www.adafruit.com/category/612) | Smaller: #6069 ($4.50). |
| Panel microSD | **Adafruit 6070** round panel-mount microSD extender | Adafruit / The Pi Hut | ~$10 | [thepihut.com](https://thepihut.com/collections/raspberry-pi-sd-cards-and-adapters/products/round-panel-mount-micro-sd-card-extender) | SD extenders can make booting unreliable: test it, or boot the CB1 from eMMC and use the slot for files. |

## Bed

| Part | Pick (model) | Vendor | Price (USD) | Link | Notes |
|---|---|---|---|---|---|
| Round silicone heater Ø250 mm | **Keenovo custom** (48 V, ~180 W, 100k NTC) | Keenovo / West3D | ~$50–90 (quote) | [west3d.com](https://west3d.com/products/keenovo-silicone-heater-heating-pad) | Stock pads are square, 24/120 V only. |
| Thermal fuse | **Cantherm SDF-DF128S** (128 °C) or **SDF-DF119S** (119 °C) | Digi-Key | ~$1–2 | [128 °C](https://www.digikey.fr/en/products/detail/cantherm/SDF-DF128S/1014762) / [119 °C](https://www.digikey.com/product-detail/en/cantherm/SDF-DF119S/317-1132-ND/1014761) | In series with the heater, on the rotating side. |
| Slip ring | **Adafruit 1196** (12 wires, 2 A each) | Adafruit | $19.95 | [adafruit.com](https://www.adafruit.com/category/223) | Parallel wires for the heater (2 per leg at 48 V, 180 W = 3.75 A). |
| Bed bearing ~180 mm | **Kaydon KA070XP0** / **Silverthin SA070XP0** (7" bore, 4-point contact) | automa.net / PIB Sales | ~$180–350 (quote) | [automa.net (series)](https://automa.net/silverthin/sa055cpo/) | Sits inside the ring gear. Budget: 8" lazy-susan bearing (~$12, [Lee Valley](https://www.leevalley.com/en-gb/shop/hardware/project-supplies/metal-parts/44014-aluminum-lazy-susan-bearings)), but it wobbles. |
| Round PEI sheet + magnet base | **265 mm round PEI spring steel** (delta-printer size) | Amazon | ~$35–45 | [amazon.com](https://www.amazon.com/Magnetic-Flexible-Compatible-QQ-S-Pro-Printer/dp/B0H7BYHPGS) | On the 266 mm bed plate; 256 mm of it is print surface. Magnet bases are good to ~80–100 °C. |
| Bed ring gear | **Laser-cut steel, module 2, 120 teeth** (hardware/ring_gear/orva_ring_gear.dxf), 0.120" (3 mm) mild steel or 4130 | SendCutSend (upload the DXF) | ~$30–50 (quote) | [sendcutsend.com](https://sendcutsend.com/) | Bolts under the bed plate (8 × M3). Deburr the teeth. See hardware/ring_gear/README.md. |
| Bed pinion | **KHK SS2-16** (module 2, 16T, S45C steel, 12 mm bore, 20 mm face) | KHK USA | ~$25–35 | [catalog.khkgears.us](https://catalog.khkgears.us/item/spur-gears/spur-gears-ss/ss2-16) | On a 12 mm shaft with two 6801 bearings, 104 mm from bed center; spring-preloaded into the ring. |
| Belt stage | **GT2 20T pulley (5 mm bore)** on the motor + **GT2 60T pulley (12 mm bore)** on the pinion shaft + **GT2 closed loop ~160–170 mm**, 6 mm | Amazon / [RobotShop (60T, 8 mm bore example)](https://www.robotshop.com/products/phidgets-gt2-pulley-w-8mm-bore-60-teeth) | ~$15–20 | — | 3:1, almost no backlash. Total bed reduction 120:16 × 60:20 = 22.5:1 (`gear_ratio: 120:16, 60:20`). |
| Pinion shaft bearings | 6801-2RS (12 × 21 × 5 mm) ×2 + 12 mm shaft | Amazon / McMaster | ~$10 | — | |

## Motion

| Part | Pick (model) | Vendor | Price (USD) | Link | Notes |
|---|---|---|---|---|---|
| NEMA 17 pancake (bed) | **StepperOnline 17HS08-1004S** (20 mm) | StepperOnline / Amazon | ~$10–14 | [example listing](https://www.ebay.de/itm/204394002463) | |
| NEMA 14 round pancake (arm) | **StepperOnline 14HR07-1004VRN** (5 mm D-shaft) | West3D | ~$20 | [west3d.com](https://west3d.com/de-de/products/stepperonline-omc-nema14-36mm-pancake-stepper-motor-14hr07-1004vrn) | LDO-36STH20 has a geared 2.5 mm shaft (extruder use only). |
| NEMA 14 0.9° (Z) | **StepperOnline 14HR08-0654S** | StepperOnline | $20.99 | [tindie.com](https://www.tindie.com/products/stepperonline/round-nema-14-stepper-motor-12ncm-17ozin/) | Often out of stock; check omc-stepperonline.com. |
| m1 rack | **SDP-SI KSR1-500** (steel, cut to 200 mm) | SDP-SI | ~$30–45 | [datasheet](https://datasheets.globalspec.com/ds/designatronics/ksr1-500/77260a48-e08a-45c4-b87a-2076bddc46f2) | |
| m1 20T pinion, 5 mm bore | **SDP-SI S10T10M020A0505** | SDP-SI | $19.90 | [shop.sdp-si.com](https://shop.sdp-si.com/s10t10m020a0505.html) | Firmware: `rotation_distance: 62.832`. |
| 20×40 V-slot (~280 mm) | OpenBuilds V-Slot 20×40 | OpenBuilds | ~$10–14 | [openbuildspartstore.com](https://openbuildspartstore.com/v-slot-20x40-linear-rail/) | r shaft (179 mm of travel). |
| 2020 V-slot (380 + 210 mm) | OpenBuilds V-Slot 20×20 | OpenBuilds | ~$12–18 | [openbuildspartstore.com](https://openbuildspartstore.com/v-slot-20x20-linear-rail/?revpage=5) | Column (256 mm of Z) and arm. Consider 2040 for the arm at this length. |
| V-wheels ×4 + eccentric spacers | Solid V Wheel Kit | Rat Rig US / OpenBuilds | ~$3–4 per wheel | [us.ratrig.com](https://us.ratrig.com/parts/bearings-pulleys/solid-v-wheel-kit.html) | Eccentrics on one side. |

## Z axis

| Part | Pick (model) | Vendor | Price (USD) | Link | Notes |
|---|---|---|---|---|---|
| GT2 6 mm belt | **Gates LL-2GT-6** | West3D / Fabreeko | ~$5–8 per m | [west3d.com](https://west3d.com/products/gates-gt2-open-belt-ll-2gt-6-6mm-wide-voron-v0-v1-v2-switchwire) | Z belt loop. |
| GT2 40T pulley, 5 mm bore | generic aluminum | Amazon / 3DPrintingUSA | ~$5–8 | — | Firmware: `rotation_distance: 80`. |
| GT2 40T idler | toothed idler, 5 mm bore | Amazon | ~$6–10 | — | |
| F623ZZ bearings | 3×10×4 mm flanged | RobotShop / Amazon | ~$1 each | [robotshop.com](https://ca.robotshop.com/products/3d-printing-canada-usa-f623zz-flange-ball-bearing-3-x-10-x-4-mm) | Tensioner. |
| Constant-force spring (optional) | stainless | McMaster-Carr | ~$8–15 | [mcmaster.com](https://www.mcmaster.com/product/1368A16/) | Size it to the carriage weight. |

## Toolhead

| Part | Pick (model) | Vendor | Price (USD) | Link | Notes |
|---|---|---|---|---|---|
| Hotend | **E3D Revo Micro 24V** | PartsBuilt | $79.95 | [partsbuilt.com](https://partsbuilt.com/revo-micro-with-single-nozzle-24-volt-e3d) | Check the heatsink fits the 20 mm shroud. Alt: Phaetus Dragonfly BMO. |
| Extruder | **LDO Orbiter V2.5** (motor included) | West3D | ~$80–95 | [west3d.com](https://west3d.com/en-au/products/ldo-orbiter-extruder-v2-5-orbiter-v2-5-and-v2-0-to-v2-5-upgrade-kit) | Includes the extruder's NEMA14. |
| Heatsink fan | **GDSTIME GDA2510** 24 V | West3D | ~$5–7 | [west3d.com](https://west3d.com/products/gdstime-dc-24v-25x25x10-axial-fan-24v-gda2510-dual-ball-bearing-1600rpm-06a-xh2-54) | |
| Part-cooling blower | **GDSTIME GDB4010** 24 V | 3DPrintingUSA | ~$6–9 | [3dprintingusa.com](https://3dprintingusa.com/products/gdstime-4010-24v-premium-blower-fan-with-ball-bearing) | |
| PTFE tube | 2×4 mm or Capricorn XS | Amazon | ~$8–15 per m | — | |

## Sensors

| Part | Pick (model) | Vendor | Price (USD) | Link | Notes |
|---|---|---|---|---|---|
| Sealed Z-min switch (rim) | **Omron D2HW-C201H** (IP67, pin plunger) | Digi-Key | ~$4–7 | [Digi-Key](https://www.digikey.com/en/product-highlight/o/omron/d2hw-sealed-snap-switch) | |
| Other endstops | **Omron D2F-01L** | Digi-Key | ~$2–3 | [octopart](https://octopart.com/ko/part/omron/D2F-01L) | r home, Z-max, tower sense. |
| Leveling probe (nozzle contact) | **Beacon Rev H + Contact** | Fabreeko / West3D | $79.99 | [fabreeko.com](https://www.fabreeko.com/products/beacon-rev-h-eddy-current-surface-scanner-contact-probe) | Works with `[probe]`-style probing. Orva rotates its x/y offset with the bed. |
| Leveling probe (budget) | **BTT Eddy Duo** | BIQU | $28.98 | [biqu.equipment](https://biqu.equipment/products/bigtreetech-eddy) | Non-contact. |

## Joint

| Part | Pick (model) | Vendor | Price (USD) | Link | Notes |
|---|---|---|---|---|---|
| Pogo pins ×10 | **Mill-Max 0906-2-15-20-75-14-11-0** | Digi-Key | ~$2–4 each | [digikey.com](https://www.digikey.com/en/products/detail/mill-max-manufacturing-corp/0906-2-15-20-75-14-11-0/1147050) | Typically 2–3 A each: parallel them for power. One pin is the tower-sense contact. |
| Spring plunger / latch | ball-nose spring plunger, M4 | McMaster-Carr | ~$5–10 | [mcmaster.com](https://www.mcmaster.com/products/plungers/thread-size~m4-1/) | |

## Misc

| Part | Pick (model) | Vendor | Price (USD) | Link | Notes |
|---|---|---|---|---|---|
| Wiper brush | brass nozzle-scrub strip | Amazon / West3D | ~$5–10 | — | |
| Wiper lift servo | **MG90S** (metal gear) | Waveshare / Amazon | ~$5–8 | [waveshare.com](https://www.waveshare.com/MG90S-Servo.htm) | 5 V. |
| Rubber feet | 3M Bumpon | Amazon | ~$6 | — | |
| Screws + T-nuts | M3/M5 assortment, 2020 drop-in T-nuts | Amazon / OpenBuilds | ~$20–30 | — | |
| Silicone wire | 18 + 22 AWG kit | Amazon | ~$20–30 | — | 18 AWG for heater and 48 V. |

## Gaps / design flags

1. **Two voltage rails.** The TMC2209 drivers, M4P logic, EBB36, hotend and
   fans all need **24 V**. Only the bed heater runs straight from 48 V, through
   an SSR/MOSFET switched by the M4P bed output.
2. **Power budget.** The 256 mm bed has ~1.6× the area of the original 200 mm
   one. A ~180 W heater plus the hotend (~40 W), motors and electronics uses
   nearly all of the 240 W USB-C supply, so heating is sequential
   (PRINT_START waits for the bed before the nozzle) and the bed takes several
   minutes to reach 60 °C. A bigger heater would need a bigger supply.
3. **Heater.** A round 48 V heater is custom-order (Keenovo). At 48 V and 180 W
   it draws 3.75 A: 2 slip-ring wires per leg on the 12-wire, 2 A ring.
4. **Bed ring gear.** Laser-cut to our file (module 2 so the laser can cut the
   tooth roots). Its edges are ±0.13 mm, so the pinion is spring-preloaded
   into the ring to take up play.
5. **No CAN on the M4P.** Run the EBB36 Gen2 over USB, or add a U2C.
6. **Wi-Fi** is 2.4 GHz only on the CB1; a metal base needs an antenna exit.
7. **48 V regulators** need input margin (TVS diode or 60 V-rated parts).
8. **Probing** uses Klipper's PROBE; Orva's own leveling module handles the
   polar pattern, so any `[probe]`-compatible sensor works.

## Estimated total (bought parts only)

| Group | Budget | Premium |
|---|---|---|
| Control | ~$215 | ~$240 |
| Power | ~$160 | ~$250 |
| I/O | ~$20 | ~$20 |
| Bed | ~$200 | ~$560 |
| Motion | ~$200 | ~$240 |
| Z | ~$35 | ~$45 |
| Toolhead | ~$140 | ~$195 |
| Sensors | ~$40 | ~$95 |
| Joint | ~$35 | ~$45 |
| Misc | ~$60 | ~$80 |
| **Total** | **~$1,105** | **~$1,770** |

Excludes shipping, tax and the custom-made parts.
