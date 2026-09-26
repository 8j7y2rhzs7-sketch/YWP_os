import path from "node:path";
import { mkdir } from "node:fs/promises";
import sharp from "sharp";
import type { MarketingCard } from "./types.js";

function escapeXml(value: string): string {
  return value.replace(/[<>&'\"]/g, (char) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", "'": "&apos;", '"': "&quot;" })[char] ?? char);
}

function fit(value: string, max = 52): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}

export async function renderCard(card: MarketingCard, outputDirectory: string, filename: string): Promise<string> {
  await mkdir(outputDirectory, { recursive: true });
  const rows = card.legs.map((leg, index) => {
    const y = 420 + index * 150;
    const detail = [leg.selection, leg.market, leg.line, leg.price].filter(Boolean).join(" • ");
    return `<g>
      <rect x="70" y="${y - 52}" width="940" height="122" rx="22" fill="#111111" stroke="#c9a227" stroke-width="2"/>
      <circle cx="125" cy="${y + 8}" r="29" fill="#c9a227"/><text x="125" y="${y + 20}" text-anchor="middle" class="num">${index + 1}</text>
      <text x="175" y="${y - 5}" class="event">${escapeXml(fit(leg.event, 48))}</text>
      <text x="175" y="${y + 39}" class="pick">${escapeXml(fit(detail, 58))}</text>
    </g>`;
  }).join("\n");

  const score = typeof card.ywpScore === "number" ? `${Math.round(card.ywpScore)}/100 YWP SCORE` : "YWP VERIFIED CARD";
  const svg = `<svg width="1080" height="1350" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#050505"/><stop offset="0.55" stop-color="#17120a"/><stop offset="1" stop-color="#000000"/></linearGradient>
      <linearGradient id="gold" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#8d6a13"/><stop offset="0.5" stop-color="#f2d675"/><stop offset="1" stop-color="#a67c16"/></linearGradient>
      <filter id="glow"><feGaussianBlur stdDeviation="7" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <style>
        .brand{font:900 72px Arial,sans-serif;letter-spacing:7px;fill:url(#gold)}
        .sub{font:700 28px Arial,sans-serif;letter-spacing:5px;fill:#f2d675}
        .title{font:800 42px Arial,sans-serif;fill:#fff}
        .event{font:700 27px Arial,sans-serif;fill:#fff}
        .pick{font:600 24px Arial,sans-serif;fill:#e5cf86}
        .num{font:900 28px Arial,sans-serif;fill:#050505}
        .footer{font:600 22px Arial,sans-serif;fill:#d8d8d8}
      </style>
    </defs>
    <rect width="1080" height="1350" fill="url(#bg)"/>
    <rect x="32" y="32" width="1016" height="1286" rx="32" fill="none" stroke="#c9a227" stroke-width="3"/>
    <path d="M470 90 L500 125 L540 78 L580 125 L610 90 L595 160 L485 160 Z" fill="url(#gold)" filter="url(#glow)"/>
    <text x="540" y="250" text-anchor="middle" class="brand">YWP OS</text>
    <text x="540" y="302" text-anchor="middle" class="sub">${escapeXml(card.sport.toUpperCase())} DECISION CARD</text>
    <text x="540" y="356" text-anchor="middle" class="title">${escapeXml(fit(card.title, 40))}</text>
    ${rows}
    <rect x="245" y="1165" width="590" height="66" rx="33" fill="url(#gold)"/>
    <text x="540" y="1208" text-anchor="middle" style="font:900 26px Arial,sans-serif;fill:#090909;letter-spacing:3px">${escapeXml(score)}</text>
    <text x="540" y="1270" text-anchor="middle" class="footer">VERIFIED AS OF ${escapeXml(new Date(card.verifiedAsOf).toLocaleString("en-US", { timeZone: "America/New_York" }))}</text>
    <text x="540" y="1300" text-anchor="middle" class="footer">21+ • BET RESPONSIBLY • RESULTS ARE NOT GUARANTEED</text>
  </svg>`;

  const destination = path.join(outputDirectory, filename);
  await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toFile(destination);
  return destination;
}
