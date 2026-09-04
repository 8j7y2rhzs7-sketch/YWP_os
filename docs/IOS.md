# YWP OS — iOS / TestFlight

Expo managed workflow (SDK 57). There is no committed `ios/` directory; EAS runs prebuild on the build servers.

## Prerequisites (your Apple / Expo accounts)

1. **Apple Developer Program** enrollment (paid) for the Apple ID that will own the app.
2. **App Store Connect** access for that team (create the app record when ready).
3. **Expo account** logged in on this machine:

```bash
cd mobile
npx eas-cli login
npx eas-cli init          # creates/links projectId → writes to app.json extra.eas
npx eas-cli credentials -p ios   # generate or upload distribution cert + provisioning
```

4. Bundle ID is fixed as **`com.ywpos.app`**. Register the same identifier in Apple Developer → Identifiers if it does not exist yet.

## Profiles (`mobile/eas.json`)

| Profile | Use |
|---|---|
| `development` | Dev client, iOS Simulator |
| `preview` | Internal distribution → TestFlight / ad-hoc devices |
| `production` | App Store / TestFlight production build |

## Build commands

```bash
cd mobile
npm run build:ios:preview      # TestFlight / internal
npm run build:ios:production   # store
npm run submit:ios             # after a production build (needs ASC API key or Apple login)
```

Version / build:

- Marketing version: `app.json` → `expo.version` (currently **3.3.5**, same as Android)
- iOS build number: `app.json` → `expo.ios.buildNumber` (currently **15**) — bump this for every App Store / TestFlight upload

## What this branch already configured

- iOS bundle ID, build number, tablet support
- Photo library usage strings (Graphic Studio / share flows)
- Privacy manifest reasons for UserDefaults + file timestamps
- `expo-build-properties` with iOS deployment target **16.4**
- EAS iOS preview + production profiles
- npm scripts for build / submit

## App Store Connect checklist (before first public listing)

- Privacy policy URL
- Support URL / marketing URL
- Age rating (gambling / simulated gambling categories — review carefully)
- Screenshots for required device sizes
- Account deletion / data deletion disclosures if accounts are offered
- Export compliance (usually “no” for standard HTTPS apps)

## Local Expo Go (quick UI check)

```bash
cd mobile
npx expo start
```

Scan the QR code with Camera → Expo Go on a physical iPhone. API must be reachable over HTTPS (`EXPO_PUBLIC_API_URL`).

## Notes

- Android `android/` is still committed for the signed APK path. That triggers an expo-doctor CNG warning; expected until Android also moves fully to prebuild-only.
- Do **not** commit Apple certificates, `.p8` keys, or provisioning profiles.
- No IPA is produced in CI from this agent until Expo + Apple credentials are available on the build machine.
