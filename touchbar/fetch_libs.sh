#!/bin/bash
# Copy the display/touch libraries LILYGO ships for the T-Display-S3 Long
# (a patched Arduino_GFX with the AXS15231 driver, and Arduino_DriveBus)
# into lib/.  They are GPL-3.0, from github.com/Xinyuan-LilyGO/T-Display-S3-Long
set -e
cd "$(dirname "$0")"
TMP=$(mktemp -d)
git clone --depth 1 https://github.com/Xinyuan-LilyGO/T-Display-S3-Long.git "$TMP/lilygo"
mkdir -p lib
rm -rf lib/Arduino_GFX lib/Arduino_DriveBus
cp -r "$TMP"/lilygo/lib/Arduino_GFX-* lib/Arduino_GFX
cp -r "$TMP"/lilygo/lib/Arduino_DriveBus-* lib/Arduino_DriveBus
rm -rf "$TMP"
echo "Libraries ready in lib/"
