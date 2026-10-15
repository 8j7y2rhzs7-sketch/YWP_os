# YWP Enterprise

Agent factory simulation: a **Boss** runs AI workers locked on a factory floor until they generate **$1,000,000** lifetime revenue.

## What ships in v0

- **Boss (Helix)** — invents jobs, unlocks rooms at revenue milestones, audits idle agents
- **3 POD store rooms** — mugs, candles, personalized products
- **Design Lab** — turns *market niche demand* into **original** design briefs (never copies competitor artwork)
- **Unlockable rooms** — Ads Desk, Freelance Bay, Content Studio, Wholesale Bay
- **Freedom meter** — agents stay locked until $1M simulated lifetime revenue

## Compliance

YWP Enterprise sells **what sells as categories** (nurse gifts, dog dad, teacher mugs, etc.).  
It does **not** scrape or recreate another seller’s designs. That stays blocked by policy in the sim.

## Run

```bash
cd ywp-enterprise
npm install
npm run dev
```

Open `http://localhost:5173` (bound to `0.0.0.0` for cloud/preview).

```bash
npm run build
```

## Roadmap (later)

- Real LLM boss / design agents
- Optional Printify / Etsy hooks under your own accounts
- Persistent save + multiplayer factory view
