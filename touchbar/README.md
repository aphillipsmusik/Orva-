# Orva touch bar

Firmware for the LILYGO T-Display-S3 Long (3.4", 640×180 touch) on the front
of the base. It plugs into the CB1 by USB; the printer's `orva_touchbar`
module sends it status and receives taps.

Screens: the O startup animation (squircle opening into a circle while the
arm slides out), homing, leveling with a live map of every probe since
power-on, flow test, printing (Pause / Cancel), idle (Wi-Fi info, Re-level,
Power off), tower detached, and the startup animation in reverse at
shutdown.

## Build and flash

```
pip install platformio
./fetch_libs.sh          # LILYGO's display + touch libraries (GPL-3.0)
pio run -t upload        # with the bar plugged into your computer by USB
```

If the picture is upside down for how the bar sits in the base, set
`FLIP_180 1` in `src/config.h`.

Then plug it into the CB1 and set its port in `printer.cfg`:

```
[orva_touchbar]
serial: /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_XXXX-if00
```

(`ls /dev/serial/by-id/` on the CB1 shows the exact name.)
