# YWP OS — iOS

See also **[RELEASE_CHANNELS.md](./RELEASE_CHANNELS.md)** so Android APKs and iOS builds stay separated.

Expo managed workflow (SDK 57). No committed `ios/` directory — EAS prebuilds on Expo’s servers.

## Try on your iPhone now (free — Expo Go)

No Apple Developer fee required.

1. Install **Expo Go** from the App Store.
2. On a computer with this repo:

```bash
cd mobile
npm ci
npm run start:phone
```

3. Scan the QR code with the iPhone Camera → open in Expo Go.
4. You should hit the live API (`https://ywp-os-api.onrender.com/api/v1`).
5. Create/login with the same email you will use on Whop → paywall → Sync.

Same Wi‑Fi is nicest; `--tunnel` (used by `start:phone`) works across networks.

## Real TestFlight / App Store (needs $99 Apple Developer)

1. Enroll in the **Apple Developer Program**.
2. Register bundle ID **`com.ywpos.app`** in Apple Developer → Identifiers.
3. Create the app in App Store Connect.
4. On your Mac:

```bash
cd mobile
npx eas-cli login
npx eas-cli init          # writes projectId into app.json extra.eas
npx eas-cli credentials -p ios
npm run build:ios:preview
```

5. Submit to TestFlight; invite testers.
6. Later: `npm run build:ios:production` + `npm run submit:ios`.

### Version knobs (iOS)

- Marketing: `app.json` → `expo.version` (keep aligned with Android `versionName`)
- Build number: `app.json` → `expo.ios.buildNumber` — bump for every TestFlight/App Store upload

### EAS profiles (`eas.json`)

| Profile | Use |
|---|---|
| `development` | Dev client, iOS Simulator |
| `preview` | TestFlight / internal iOS |
| `production` | App Store iOS |

Android is **not** built via EAS in this repo.

## App Store Connect checklist (before public listing)

- Privacy policy URL + support URL
- Age rating (gambling-adjacent — review carefully)
- Screenshots for required sizes
- Account / data deletion disclosures
- Export compliance (`ITSAppUsesNonExemptEncryption` is already false for standard HTTPS)

## Do not

- Use BetaDrop / InstallOnAir / random enterprise signers for customers
- Commit Apple certificates, `.p8` keys, or provisioning profiles
- Run `expo prebuild` casually (can disturb the committed Android tree)
- Put an IPA on the Whop Android download URL
