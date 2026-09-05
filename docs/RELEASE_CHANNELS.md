# Release channels — keep Android and iOS from mixing

Shared JS lives in `mobile/`. Native release pipelines stay separate.

## Android (sideload / Whop APK)

| Item | Source of truth |
|---|---|
| Marketing version | `mobile/android/app/build.gradle` → `versionName` |
| Store/install code | `mobile/android/app/build.gradle` → `versionCode` |
| Build command | `cd mobile && npm run build:apk` |
| Artifact | `android/app/build/outputs/apk/release/app-release.apk` → rename `YWP-OS-X.Y.Z.apk` |
| Publish | GitHub Release tag **`android-vX.Y.Z`** only |
| Customer download | Whop Software/Files + `YWP_APP_DOWNLOAD_URL` |

Do **not** ship Android through EAS. Do **not** put an IPA on the Whop Android download slot.

Mirror marketing version in `mobile/app.json` `expo.version` and `expo.android.versionCode` for docs/Expo — Gradle still wins for the APK.

## iOS (Expo Go now → TestFlight later)

| Item | Source of truth |
|---|---|
| Marketing version | `mobile/app.json` → `expo.version` |
| Build number | `mobile/app.json` → `expo.ios.buildNumber` (bump every upload) |
| Free phone test | `cd mobile && npm run start:phone` → Expo Go |
| Real IPA | `npm run build:ios:preview` / `build:ios:production` (needs Apple Developer + EAS login) |
| Publish | TestFlight / App Store only — tag **`ios-vX.Y.Z`** when you cut a store build |

EAS profiles are **iOS-only**. There is no committed `ios/` folder; EAS prebuilds on Expo servers. Never run `npx expo prebuild` into this repo unless you intentionally regenerate natives — it can rewrite `android/`.

## Version lockstep (recommended)

When both platforms ship the same product cut:

1. Set `expo.version` = Android `versionName` (e.g. `3.3.9`)
2. Set Android `versionCode` and iOS `buildNumber` to the same integer (e.g. `19`)
3. Tag releases `android-v3.3.9` and (later) `ios-v3.3.9` separately

## Env

- Phone / production clients: `mobile/.env.production` (HTTPS Render API)
- Local simulator: `mobile/.env.example` → `.env` (localhost / LAN)

Never put provider secrets in `EXPO_PUBLIC_*`.
