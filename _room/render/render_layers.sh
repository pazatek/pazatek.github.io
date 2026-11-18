#!/bin/zsh
# Renders every light layer for the app (white light, transparent background, linear EXR), then encodes them for the web.
#   ./render_layers.sh [width] [samples]
cd "$(dirname "$0")"
WIDTH=${1:-1400}; SAMPLES=${2:-160}
BL=/Applications/Blender.app/Contents/MacOS/Blender
mkdir -p out/layers
for L in day pixar little fan fill; do
  $BL -b -P build_scene.py -- --out out/layers/$L.exr --samples $SAMPLES --width $WIDTH --layer $L 2>&1 | grep -E "Error|Traceback|RENDERED"
done
$BL -b -P encode_layers.py -- out/layers 2>&1 | grep -E "Error|Traceback|ENCODED|layer"
echo DONE
