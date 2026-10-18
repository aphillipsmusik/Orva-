# Wi-Fi and connecting from a computer

Orva's controller (BTT CB1) has 2.4 GHz Wi-Fi built in. On the network the
printer runs Moonraker and Mainsail, the standard Klipper web interface, so
any computer, tablet or phone can drive it from a browser, and slicers can
send prints straight to it.

## First-time Wi-Fi setup

1. Power Orva on. If it can't find a saved network within ~45 s it starts its
   own hotspot. The touch bar shows the name and password:
   `Wi-Fi setup: join Orva-XXXX, password ...`
2. Join that network from a phone or laptop and open
   **http://10.42.0.1:8090**. Pick your Wi-Fi, type the password, Connect.
3. Rejoin your own Wi-Fi. The printer is now at **http://orva.local**
   (the touch bar shows its IP address too).

Or from a computer on the hotspot: `python3 desktop/orva.py wifi connect
"MyNetwork" "password"`.

Orva remembers every network it has joined. When you take it somewhere new,
it falls back to the hotspot again, so you can add that network the same way.
Over SSH, `orva-wifi` does the same from a shell (`orva-wifi add SSID PASS`,
`orva-wifi scan`, `orva-wifi status`).

Because the base is metal, plan an antenna exit for the CB1 (see
docs/parts.md).

## From your computer

* **Browser:** http://orva.local opens Mainsail: upload and start prints,
  watch temperatures and progress, run macros (ORVA_RELEVEL, ORVA_SHUTDOWN...),
  edit config, and update the Orva firmware from the update panel.
* **Slicer:** in PrusaSlicer or OrcaSlicer add a physical printer of type
  Klipper (Moonraker) at `orva.local`; "Send to printer" uploads and starts.
* **Command line:** `desktop/orva.py` (Python 3, no extra packages; Windows,
  macOS, Linux):

  ```
  python3 orva.py status
  python3 orva.py print benchy.gcode
  python3 orva.py pause | resume | cancel
  python3 orva.py relevel
  python3 orva.py gcode "ORVA_LEVEL_STATUS"
  python3 orva.py open          # opens Mainsail
  python3 orva.py shutdown
  ```

  It finds the printer as `orva.local`, or `10.42.0.1` in hotspot mode; use
  `--host` or `ORVA_HOST` for anything else.

## Installing on the CB1

Flash BTT's CB1 image (it includes Klipper, Moonraker and Mainsail), then:

```
git clone https://github.com/aphillipsmusik/orva-.git ~/orva
cd ~/orva
./install.sh --hostname orva
```

This links the Orva modules into Klipper, adds `orva.cfg`,
`orva_macros.cfg` and `moonraker-orva.conf` to your config folder (without
overwriting anything), puts an example `printer.cfg.orva-example` next to
them, installs the Wi-Fi services, and names the host `orva` so it shows up
as orva.local. Then copy the example to `printer.cfg`, fix the serial IDs and
pins for your boards, and restart Klipper.

`moonraker-orva.conf` turns on network discovery (zeroconf) and adds Orva to
Moonraker's update manager, so firmware updates come from this GitHub repo.
