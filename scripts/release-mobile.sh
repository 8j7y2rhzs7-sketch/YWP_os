#!/usr/bin/env bash
# Dual-platform release helper — Android APK + iOS EAS in one cut.
# Usage: ./scripts/release-mobile.sh 3.3.56
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "Usage: $0 <version>   e.g. $0 3.3.56" >&2
  exit 2
fi

cd "$ROOT/mobile"

echo "==> Version lockstep check for $VERSION"
node -e "
const fs=require('fs');
const app=JSON.parse(fs.readFileSync('app.json','utf8'));
const pkg=JSON.parse(fs.readFileSync('package.json','utf8'));
const gradle=fs.readFileSync('android/app/build.gradle','utf8');
const v=process.argv[1];
if(app.expo.version!==v) throw new Error('app.json expo.version='+app.expo.version);
if(pkg.version!==v) throw new Error('package.json version='+pkg.version);
if(!gradle.includes('versionName \"'+v+'\"')) throw new Error('gradle versionName mismatch');
console.log('ok', v, 'buildNumber', app.expo.ios.buildNumber, 'versionCode', app.expo.android.versionCode);
" "$VERSION"

echo "==> Android APK"
npm run build:apk
APK_SRC="android/app/build/outputs/apk/release/app-release.apk"
APK_OUT="/tmp/YWP-OS-${VERSION}.apk"
cp -f "$APK_SRC" "$APK_OUT"
gh release create "android-v${VERSION}" "$APK_OUT" \
  --repo 8j7y2rhzs7-sketch/YWP_os \
  --title "YWP OS Android ${VERSION}" \
  --notes "Android sideload cut ${VERSION}. iOS EAS build follows in the same release window." \
  || gh release upload "android-v${VERSION}" "$APK_OUT" --repo 8j7y2rhzs7-sketch/YWP_os --clobber

echo "==> iOS EAS (requires EXPO_TOKEN)"
if [[ -z "${EXPO_TOKEN:-}" ]]; then
  echo "EXPO_TOKEN missing — cannot build iOS. Add an expo.dev access token, then re-run." >&2
  exit 3
fi
npm run build:ios:preview -- --non-interactive

echo "==> Tag ios-v${VERSION} notes (EAS URL printed above)"
gh release create "ios-v${VERSION}" \
  --repo 8j7y2rhzs7-sketch/YWP_os \
  --title "YWP OS iOS ${VERSION}" \
  --notes "iOS EAS/TestFlight cut ${VERSION}. See Expo dashboard for the build artifact." \
  || true

echo "Done. Both platforms targeted for ${VERSION}."
