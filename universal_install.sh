#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DAS_SCRIPT_DIST="/opt/resolve/Fusion/Scripts/Utility"
DAS_ALAC_CONVERTER_DIST="/usr/bin"
AAC2ALACBIN="${DAS_ALAC_CONVERTER_DIST}/aac2alac"

# Check dependencies
for dep in python ffmpeg; do
    if ! command -v "$dep" &>/dev/null; then
        echo "Error: '$dep' is required but not installed." >&2
        exit 1
    fi
done

echo "Installing davinci-alac-scripts..."

mkdir -p "${DAS_SCRIPT_DIST}"
mkdir -p "${DAS_ALAC_CONVERTER_DIST}"

install -Dm644 "${SCRIPT_DIR}/convert_aac_to_alac.py" "${DAS_SCRIPT_DIST}/convert_aac_to_alac.py"
install -Dm755 "${SCRIPT_DIR}/aac2alac.py" "${AAC2ALACBIN}"

echo "Done."
echo "  Fusion script -> ${DAS_SCRIPT_DIST}/convert_aac_to_alac.py"
echo "  CLI tool      -> ${AAC2ALACBIN}"
