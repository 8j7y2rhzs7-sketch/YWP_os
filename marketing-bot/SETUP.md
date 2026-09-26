# Marketing Bot

**Promo posts are not live tickets.** Templates auto-pass safety — you do not re-verify every post.

## Day-to-day (the bot doing its job)

```bash
cd marketing-bot && npm run dev
```

Open `http://localhost:8787` → **Post promo**.

| Mode | What happens |
|------|----------------|
| `IG_PUBLISH_ENABLED=false` | Creates image + caption instantly (already approved). Download / copy into IG. |
| `IG_PUBLISH_ENABLED=true` + Meta creds | **Same button posts to Instagram** in one tap. |

No ticket eligibility. No approve click every time.

## One-time Meta setup (only if you want auto-post)

Do this **once**, then forget it:

1. `@ywpossports` → Instagram Professional + linked Facebook Page  
2. Meta Developer app with Instagram content publish permission  
3. Put in `.env`: `IG_USER_ID`, `IG_ACCESS_TOKEN`, `META_GRAPH_VERSION`, `PUBLIC_BASE_URL` (HTTPS the bot is reachable on)  
4. Set `IG_PUBLISH_ENABLED=true`  
5. Hit **Post promo** once and confirm Meta returns a media id  

After that, marketing is one button.

## What you never need per post

- Marking tickets publication-eligible  
- Re-running Lock Check / VERIFIED gates on a live bet  
- Manual “approve draft” for promo templates  
