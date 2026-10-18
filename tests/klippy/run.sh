#!/bin/bash
# Run Orva in Klipper's batch mode against a Linux-process MCU dictionary.
#   KLIPPER_DIR=~/klipper DICT=~/klipper/out/klipper.dict tests/klippy/run.sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$(dirname "$HERE")")"
KLIPPER_DIR="${KLIPPER_DIR:-$HOME/klipper}"
DICT="${DICT:-$KLIPPER_DIR/out/klipper.dict}"
"$ROOT/install.sh" --klipper "$KLIPPER_DIR" --no-service >/dev/null
OUT="$(mktemp -d)"
cd "$KLIPPER_DIR"
run() {
    python3 ./klippy/klippy.py "$HERE/orva_test.cfg" -i "$1" -o "$OUT/out.serial" \
        -d "$DICT" -l "$OUT/klippy.log" -v
}
echo "== orva_test.gcode"
if ! run "$HERE/orva_test.gcode"; then
    tail -60 "$OUT/klippy.log"; exit 1
fi
grep -E "Orva|Result|// " "$OUT/klippy.log" | sed 's/^/   /' | head -80
echo "== orva_test_fail.gcode (expected to fail)"
if run "$HERE/orva_test_fail.gcode"; then
    echo "ERROR: expected failure did not happen"; exit 1
fi
grep -E "first layer" "$OUT/klippy.log" | head -2 | sed 's/^/   /'
echo "OK"
