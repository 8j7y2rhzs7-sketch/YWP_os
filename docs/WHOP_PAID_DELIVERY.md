# Whop paid delivery — Android first

Target customer loop (no license-key rebuild):

1. Customer pays on Whop (**DECISION ENGINE**, **$25 / 1 day**)
2. Whop shows the **Android APK download** on the paid product
3. Customer installs APK, creates/signs into YWP OS with the **same email used at checkout**
4. Customer taps **Sync my access** → membership unlocks the engine

No new Whop app shell. No fake login page. No separate license-key database.

## What this repo already does

- Checkout URL: `https://whop.com/checkout/plan_MwJ2qcFxmvqDY` (`prod_NuPQUAGoibkpW`)
- In-app paywall (already installed): Subscribe → Sync my access
- First-time APK delivery stays on Whop after payment (backup link also from `/api/v1/whop/checkout` as `app_download_url`):

  `https://github.com/8j7y2rhzs7-sketch/YWP_os/releases/download/android-v3.3.9/YWP-OS-3.3.9.apk`

- Sync resolves membership by:
  - webhook / pending access (email match), then
  - Whop member email lookup + `users.check_access` on the DECISION ENGINE product

## Day-pass expiry (no overstay)

Whop auto-expires the 1-day membership. YWP OS does **not** cache a permanent unlock:

- `/users/me`, login/register, protected routes, and `/whop/sync` re-hit Whop `checkAccess` on a TTL (default **5 minutes**)
- Local hard ceiling: without a fresh confirming check within **24 hours** of grant, access is revoked
- App foreground + every 5 minutes while open → force `/whop/sync`
- API `402` clears client `has_app_access` and returns the user to the paywall
- Re-pay → webhook `payment.succeeded` / `membership.activated` **or** Sync `checkAccess` → access restored

Optional env:

```bash
WHOP_ACCESS_RECHECK_SECONDS=300
WHOP_DAY_PASS_SECONDS=86400
```

## What you still do in Whop (dashboard / Whop support)

Whop must attach the APK to the **paid** product so buyers see download after payment.

### Message to send Whop

Copy/paste:

```text
Ready to wire paid Android delivery for DECISION ENGINE.

Product: existing DECISION ENGINE (prod_NuPQUAGoibkpW / plan_MwJ2qcFxmvqDY)
Price: $25 for 1 day
Do not create a new Whop app shell or fake login page.

Please wire:
payment → Software/Files experience with this APK download → done

APK:
https://github.com/8j7y2rhzs7-sketch/YWP_os/releases/download/android-v3.3.9/YWP-OS-3.3.9.apk

SHA-256:
d702e29e1521775524c6432e029f91a200476e2447c088138345ef476d69918b

Unlock in the installed app is email-sync (same email as checkout → Sync my access).
No license-key screen for v1.
```

### Checklist

- [ ] Unhide / enable the **$25/day** DECISION ENGINE product for sale
- [ ] Attach Software/Files experience with the APK above (or re-host the same file in Whop)
- [ ] Confirm checkout still uses `plan_MwJ2qcFxmvqDY`
- [ ] Leave the $0 Whop app product alone (no download required there)
- [ ] After Whop confirms, buy once with a fresh email and walk: pay → download → install → register/login same email → Sync

## Env overrides (optional)

```bash
YWP_APP_DOWNLOAD_URL=https://github.com/8j7y2rhzs7-sketch/YWP_os/releases/download/android-v3.3.9/YWP-OS-3.3.9.apk
EXPO_PUBLIC_APP_DOWNLOAD_URL=https://github.com/8j7y2rhzs7-sketch/YWP_os/releases/download/android-v3.3.9/YWP-OS-3.3.9.apk
WHOP_ACCESS_RECHECK_SECONDS=300
WHOP_DAY_PASS_SECONDS=86400
```

## Out of scope here

- iOS IPA / TestFlight (needs Apple Developer + EAS login)
- License-key unlock UI (deferred unless email-sync proves painful)
