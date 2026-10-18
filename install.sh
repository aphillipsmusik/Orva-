#!/bin/bash
# Install Orva's Klipper add-ons on the printer (BTT CB1 / any Klipper host).
#
#   ./install.sh                 # Klipper in ~/klipper, config in ~/printer_data
#   ./install.sh --klipper DIR   # other Klipper checkout
#   ./install.sh --no-service    # only link the modules (used by tests)
#   ./install.sh --hostname orva # also rename the host (reach it as orva.local)
#   ./install.sh --uninstall
#
# Klipper itself is not modified: the modules are symlinked into it and
# excluded from its git status, so Klipper and Moonraker updates keep
# working.  The Orva C kinematics helper is compiled automatically the first
# time Klipper starts.
set -e
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KLIPPER="$HOME/klipper"
PDATA="$HOME/printer_data"
SERVICE=1
UNINSTALL=0
HOSTNAME_NEW=""
while [ $# -gt 0 ]; do
    case "$1" in
        --klipper) KLIPPER="$2"; shift ;;
        --printer-data) PDATA="$2"; shift ;;
        --no-service) SERVICE=0 ;;
        --uninstall) UNINSTALL=1 ;;
        --hostname) HOSTNAME_NEW="$2"; shift ;;
        *) echo "unknown option $1"; exit 1 ;;
    esac
    shift
done

[ -d "$KLIPPER/klippy" ] || { echo "Klipper not found at $KLIPPER"; exit 1; }

FILES=()
FILES+=("kinematics/orva_polar.py")
for f in "$SRC"/klipper/extras/orva_*.py; do
    FILES+=("extras/$(basename "$f")")
done

EXCLUDE="$KLIPPER/.git/info/exclude"
for rel in "${FILES[@]}"; do
    dest="$KLIPPER/klippy/$rel"
    if [ $UNINSTALL -eq 1 ]; then
        [ -L "$dest" ] && rm -f "$dest"
        continue
    fi
    ln -sfn "$SRC/klipper/$rel" "$dest"
    if [ -f "$EXCLUDE" ] && ! grep -qxF "klippy/$rel" "$EXCLUDE"; then
        echo "klippy/$rel" >> "$EXCLUDE"
    fi
done

if [ $UNINSTALL -eq 1 ]; then
    echo "Orva modules removed from $KLIPPER"
    if [ $SERVICE -eq 1 ]; then
        sudo systemctl disable --now orva-net.service orva-setup.service \
            2>/dev/null || true
    fi
    exit 0
fi
echo "Linked Orva modules into $KLIPPER/klippy"

[ $SERVICE -eq 1 ] || exit 0

# Config files (never overwrite the user's edits)
CFG="$PDATA/config"
if [ -d "$CFG" ]; then
    for f in orva.cfg orva_macros.cfg; do
        if [ ! -e "$CFG/$f" ]; then
            cp "$SRC/config/$f" "$CFG/$f"; echo "Added $CFG/$f"
        fi
    done
    cp "$SRC/config/printer.cfg" "$CFG/printer.cfg.orva-example"
    echo "Example printer config: $CFG/printer.cfg.orva-example"
    if [ ! -e "$CFG/moonraker-orva.conf" ]; then
        sed "s#@ORVA_DIR@#$SRC#g" "$SRC/config/moonraker-orva.conf" \
            > "$CFG/moonraker-orva.conf"
        echo "Added $CFG/moonraker-orva.conf"
        if [ -f "$CFG/moonraker.conf" ] && \
                ! grep -q "moonraker-orva.conf" "$CFG/moonraker.conf"; then
            printf '\n[include moonraker-orva.conf]\n' >> "$CFG/moonraker.conf"
            echo "Included it from moonraker.conf"
        fi
    fi
fi

# Wi-Fi: join a saved network, or start an "Orva-XXXX" hotspot for setup
sudo install -m 755 "$SRC/system/orva-net" /usr/local/bin/orva-net
sudo install -m 755 "$SRC/system/orva-wifi" /usr/local/bin/orva-wifi
sudo install -m 755 "$SRC/system/orva-setup" /usr/local/bin/orva-setup
sudo install -m 644 "$SRC/system/orva-net.service" /etc/systemd/system/
sudo install -m 644 "$SRC/system/orva-setup.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now orva-net.service orva-setup.service
echo "Wi-Fi helper installed (orva-wifi --help; setup page on port 8090)"

if [ -n "$HOSTNAME_NEW" ]; then
    sudo hostnamectl set-hostname "$HOSTNAME_NEW"
    echo "Hostname set: reach the printer at http://$HOSTNAME_NEW.local"
fi

# Touch bar: allow the klipper user to open the USB serial port
sudo usermod -a -G dialout "$USER" || true

echo "Done. Restart Klipper: sudo systemctl restart klipper"
