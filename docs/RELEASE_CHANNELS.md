# Release channels — keep Android and iOS from mixing

Shared JS lives in `mobile/`. Native release pipelines stay separate.

## Hard rule: ship both platforms every product cut

When mobile product changes land (UI, API client, Learning, Run, tickets, metacognition, etc.), **always release Android and iOS in the same cut**:

| Platform | Artifact | Tag |
|---|---|---|
| Android | Sideload APK on GitHub Releases | `android-vX.Y.Z` |
| iOS | EAS → TestFlight / App Store | `ios-vX.Y.Z` |

Do not close a release after only one platform.

### Who builds what

| Agent | Responsibility |
|---|---|
| Product / ops agent (this run) | Code, tests, Render deploy, Android APK GitHub release, **DISTRIBUTION_HANDOFF.md** |
| **YWP OS CLOUD AGENT** (Expo) | Expo reload + EAS iOS / TestFlight from the handoff tip |

After every mobile cut, write `DISTRIBUTION_HANDOFF.md` and hand it to the Expo cloud agent — do not stall asking this agent for `EXPO_TOKEN` when Expo credentials live on that agent.

Helper: `./scripts/release-mobile.sh X.Y.Z` (Android half + iOS command when `EXPO_TOKEN` is available on the Expo agent).

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

## iOS (EAS → TestFlight)

| Item | Source of truth |
|---|---|
| Marketing version | `mobile/app.json` → `expo.version` |
| Build number | `mobile/app.json` → `expo.ios.buildNumber` (bump every upload) |
| Free phone test | `cd mobile && npm run start:phone` → Expo Go (dev only; not a store cut) |
| Real IPA | `npm run build:ios:preview` / `build:ios:production` (needs Apple Developer + valid `EXPO_TOKEN`) |
| Publish | TestFlight / App Store — tag **`ios-vX.Y.Z`** when you cut a store build |
| Auth | Cloud Agent secret `EXPO_TOKEN` from expo.dev → Access Token |

EAS profiles are **iOS-only**. There is no committed `ios/` folder; EAS prebuilds on Expo servers. Never run `npx expo prebuild` into this repo unless you intentionally regenerate natives — it can rewrite `android/`.

### iOS release commands

```bash
cd mobile
# Requires EXPO_TOKEN in the environment (expo.dev access token)
npm run build:ios:preview      # TestFlight-capable preview profile
# or
npm run build:ios:production   # production profile (autoIncrement)
npm run submit:ios             # submit last production build to App Store Connect
```

After EAS finishes, create GitHub release tag `ios-vX.Y.Z` with the Expo build URL in the notes (IPA stays on EAS/TestFlight).

## Version lockstep (required)

When both platforms ship the same product cut:

1. Set `expo.version` = Android `versionName` (e.g. `3.3.56`)
2. Set Android `versionCode` and iOS `buildNumber` to the same integer (e.g. `51`)
3. Tag releases `android-v3.3.56` and `ios-v3.3.56` separately
4. Deploy backend that the clients expect in the same window

## Env

- Phone / production clients: `mobile/.env.production` (HTTPS Render API)
- Local simulator: `mobile/.env.example` → `.env` (localhost / LAN)
- Cloud Agent iOS builds: `EXPO_TOKEN` (required), Apple credentials configured in EAS dashboard

Never put provider secrets in `EXPO_PUBLIC_*`.
