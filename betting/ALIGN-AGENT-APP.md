# Why the app cashes and agent tickets die on 1 leg

## Your complaint (correct)

- App / floor bags: ugly juice, but they **cash**
- Agent tickets: look sharp, then **1 leg kills the slip**

That’s not bad luck. Two systems were optimizing different things.

## What the app does right

`decision_engine` vision = **30% hit rate + 25% cushion** (+ matchup/script/paths).  
`ticket_builder` **cash_builder / fortress** only use `safe_pool` where `miss_by_one_risk < 0.55`.

That produces Fri’s bag: REB O5.5–O10.5 and soft PTS shaves with real clearance room.

## What was broken

1. **Official core cards used the full eligible pool** (confidence/edge), not `safe_pool`.  
   One thin-cushion “strong” leg got into Official 4/5 and killed tickets.  
   **Fixed:** `core_3/4/5`, `core_parlay`, `elite_two`, tickets A/B/C, handicap, scripted now use `safe_pool` (same as cash/fortress).

2. **Agent chat slips weren’t bound to that rule.**  
   5/7 RISK-KEEP, exact-clear overs, soft pads as spine all slipped in.  
   **Fixed:** `betting/no_kill_ticket.py` — spine needs L7≥6/7 **and** avg clear margin ≥1.5 **and** mpg≥24; soft floors pad-only.

3. **Two data pipes.** Live slate still fakes `recent_hit_rate ≈ implied`. Demo/gate floors were the real signal.  
   Next: feed GATE L7 into candidates so app + agent share one truth.

## Rule going forward

Official bag = **no-kill spine only**.  
Edge/Ghostt cards may still chase price — labeled as upside, not Official.
