#!/usr/bin/env bash
# Free Apple ID → install YWP OS on YOUR iPhone only (no $99 program).
# Run on a Mac with Xcode + the phone plugged in. Do not commit mobile/ios/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MOBILE="$ROOT/mobile"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer must run on your Mac mini (needs Xcode)."
  echo "See docs/IOS.md → Free personal device install."
  exit 1
fi

if ! command -v xcodebuild >/dev/null 2>&1; then
  echo "Xcode is required. Install it from the Mac App Store, open it once, then rerun."
  exit 1
fi

cd "$MOBILE"

if [[ ! -d node_modules ]]; then
  npm ci
fi

echo "Generating iOS native project only (android/ untouched)…"
npx expo prebuild --platform ios --no-install

echo ""
echo "Building and installing on a connected iPhone…"
echo "In Signing, choose your free Personal Team (Apple ID)."
echo ""

npx expo run:ios --device

echo ""
echo "If the icon won’t open: iPhone → Settings → General → VPN & Device Management → Trust."
echo "Cert expires ~7 days — rerun: npm run ios:device:free"
echo "Friends should use Expo Go (npm run start:phone), not this build."
