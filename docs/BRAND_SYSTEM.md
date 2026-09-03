# YWP OS Brand System

This file is the implementation contract for every screen, exported decision card, store asset, and future builder. The original supplied artwork is bundled in `mobile/assets/brand`; generated placeholders must not replace it.

## Canonical assets

| Asset | Source path | Required use |
|---|---|---|
| Metallic crown crest | `mobile/assets/brand/ywp-crest.png` | App icon, splash, dark UI header, decision graphics |
| Minimal YWP os mark | `mobile/assets/brand/ywp-minimal.png` | Light documents, monochrome/light surfaces, partner material |
| App icon copy | `mobile/assets/brand/app-icon.png` | Expo iOS/Android icon configuration |
| Splash copy | `mobile/assets/brand/splash-logo.png` | Expo Splash Screen plugin |
| Original design references | `mobile/assets/brand/reference-cards/` | Visual QA for panels, hierarchy, PASS/PLAY status, card density |
| Untouched originals | `mobile/assets/brand/originals/` | Archival source; do not optimize, redraw, or overwrite |

`mobile/src/brandAssets.ts` statically imports every canonical asset so Expo and downstream app builders preserve them. `mobile/app.json` independently points native icon and splash generation to the crest.

## Visual direction

- Black and blue-charcoal briefing-board background.
- Metallic gold used for borders, numbers, dividers, premium controls, and the crown crest.
- White/silver type for decisions and supporting facts.
- Neon green only for cleared/approved states.
- Amber for caution, incomplete confirmation, or lean status.
- Red/pink for removal, PASS, failed gates, and material change.
- Dense but readable cards, beveled/gradient panels, symmetrical metric rows, rounded status badges, and explicit hierarchy.
- The interface should feel like a disciplined sports operations room—not a casino game.

## Canonical implementation tokens

These values in `mobile/src/theme.ts` are authoritative for code:

| Token | Hex | Use |
|---|---:|---|
| Background | `#050608` | Page canvas |
| Raised background | `#090C11` | Navigation and secondary canvas |
| Surface | `#0E131A` | Primary panels |
| Raised surface | `#141B24` | Inputs and inset controls |
| Gold | `#F5C542` | Primary brand accent |
| Bright gold | `#FFE48A` | Metallic gradient highlight |
| Dark gold | `#8A6412` | Gradient shadow and active tracks |
| White | `#F8F9FB` | Primary decisions |
| Silver | `#C3C9D3` | Supporting information |
| Success | `#42E49B` | Cleared/LOCKED/PLAY |
| Warning | `#FFB83E` | LEAN/WATCH/incomplete check |
| Danger | `#FF6577` | SKIP/removal/failure |
| Information | `#50B6FF` | Neutral data callout |

## Typography and language

Use heavy uppercase display type for card titles, decisions, and ratings. Supporting paragraphs use compact neutral sans-serif type. Never use decorative type for statistics.

Approved brand language:

- `YWP OS — THE UNDERDOG STRATEGIST`
- `DISCIPLINE. DATA. EDGE.`
- `WE DON'T GUESS, WE ANALYZE.`
- `TRUST THE PROCESS.`
- `GRIND EVERYDAY. LONGTERM PAYDAY.`
- `MEASURE TWICE. CUT ONCE.`
- `STRICT MODE • NO FORCING • WAGER RESPONSIBLY`

Avoid `guaranteed`, `can't lose`, `sure thing`, and any wording that converts probability into certainty.

## Component mapping

| Visual requirement | Source implementation |
|---|---|
| Branded page header | `mobile/src/components/BrandHeader.tsx` |
| Beveled metallic panel | `mobile/src/components/MetalPanel.tsx` |
| PLAY/LEAN/WATCH/SKIP badges | `mobile/src/components/StatusPill.tsx` |
| Recommendation hierarchy | `mobile/src/components/RecommendationCard.tsx` |
| Official ticket/card hierarchy | `mobile/src/components/TicketCardView.tsx` |
| 1080 × 1350 social decision graphic | `mobile/src/components/ShareCard.tsx` |
| Export/share workflow | `mobile/app/share-card.tsx` |
| App icon, adaptive icon, splash, favicon | `mobile/app.json` |

## Graphic rules

1. A graphic must be generated from the same stored recommendation/card object shown in the app; never retype picks into an image.
2. PASS graphics are first-class and use a red-bordered official decision panel.
3. PLAY graphics show the price, YIS, Vision, confidence, risk, and first control warning.
4. A five-leg layout is the maximum for the 1080 × 1350 template. Longer tickets require a second page rather than shrinking text below legibility.
5. Exported graphics include protocol version, slate date, Strict Mode, no-forcing language, and responsible-wagering language.
6. Reference-card content is historical design reference only. It must never enter current analysis or a live ticket.

## Accessibility

- Maintain at least WCAG AA contrast for ordinary text.
- Status is never communicated by color alone; every badge includes text.
- Logo images include an accessibility label where displayed.
- Touch targets remain at least 44 logical pixels.
- Reduced readability is never accepted merely to fit another parlay leg.
