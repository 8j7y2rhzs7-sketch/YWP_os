# YWP OS — iOS

See also **[RELEASE_CHANNELS.md](./RELEASE_CHANNELS.md)** so Android APKs and iOS builds stay separated.

Expo managed workflow (SDK 57). No committed `ios/` directory — EAS prebuilds on Expo’s servers. A local `mobile/ios/` folder may appear for **free personal-device** installs; it is gitignored — do not commit it.

## Try on your iPhone now (free — Expo Go)

No Apple Developer fee required. Best for **you + friends**.

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

## Free personal device install (Option 2 — your iPhone only)

Install a real **YWP OS** home-screen icon **without** the $99 Apple Developer Program.

**Limits (Apple free team):**

- Works on **your** iPhone(s) signed into Xcode with your free Apple ID
- Signing expires about **every 7 days** → reconnect and reinstall
- **Not** a share link for friends (friends should use Expo Go)
- Needs a **Mac + Xcode + USB cable** (or paired wireless debugging)

### On your Mac mini

1. Install **Xcode** from the Mac App Store (open it once, accept license).
2. Xcode → Settings → Accounts → **+** → add your **Apple ID** (free).
3. Plug in the iPhone → Trust this computer → on iPhone: Settings → Privacy & Security → Developer Mode **On** (if shown) → reboot if asked.
4. In Terminal:

```bash
cd ~/YWP_os
git fetch origin
git checkout cursor/ios-free-device-4fbe
cd mobile
npm ci
npm run ios:device:free
```

5. When Xcode / the CLI asks for a **Signing Team**, pick your personal team (`Your Name (Personal Team)`).
6. If build fails with **bundle identifier unavailable**, temporarily change `expo.ios.bundleIdentifier` in `mobile/app.json` to something unique, e.g. `com.yourname.ywpos.dev`, then rerun. Keep `com.ywpos.app` for the real App Store later.
7. On the iPhone the first time: Settings → General → **VPN & Device Management** → trust your developer certificate → open **YWP OS**.

API should already point at production via `mobile/.env.production` (`https://ywp-os-api.onrender.com/api/v1`).

### Reinstall after ~7 days

Reconnect the phone and run `npm run ios:device:free` again from `mobile/`.

### Do not for this path

- Do not commit `mobile/ios/`
- Do not run `npx expo prebuild` without `--platform ios` (can disturb the Android tree)
- Do not upload this build to BetaDrop / random OTA hosts for friends

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
- Run `expo prebuild` casually without `--platform ios` (can disturb the committed Android tree)
- Put an IPA on the Whop Android download URL
