import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { SimState } from "../sim/types";
import {
  type FlyingCargo,
  MAP_COLS,
  MAP_ROWS,
  STATIONS,
  TILE,
  type Walker,
  type CargoKind,
  stationCenter,
} from "./layout";
import "./factoryMap.css";

const PALETTES = [
  ["#e76f51", "#f4a261", "#2a9d8f"], // boss warm
  ["#9b5de5", "#f15bb5", "#00bbf9"], // design
  ["#277da1", "#4d908e", "#90be6d"], // store
  ["#f9c74f", "#f9844a", "#43aa8b"], // ops
];

function rolePalette(role: string): number {
  if (role === "boss") return 0;
  if (role === "design") return 1;
  if (role === "store") return 2;
  return 3;
}

function cargoForAction(action: string, role: string): CargoKind | null {
  const a = action.toLowerCase();
  if (a.includes("sold") || a.includes("booked") || a.includes("drip")) return "coin";
  if (a.includes("mug") || a.includes("candle") || a.includes("brief")) return "mug";
  if (a.includes("gig") || a.includes("offer") || a.includes("shipped")) return "box";
  if (role === "design" || a.includes("original")) return "scroll";
  if (role === "boss") return null;
  return Math.random() > 0.5 ? "box" : "coin";
}

function pickJobTarget(agentRoomId: string, tick: number): string {
  const vault = "vault";
  const design = "room-design";
  const options = [agentRoomId, vault, design, agentRoomId];
  return options[tick % options.length]!;
}

interface Props {
  state: SimState;
}

export function FactoryMap({ state }: Props) {
  const [walkers, setWalkers] = useState<Walker[]>([]);
  const [cargo, setCargo] = useState<FlyingCargo[]>([]);
  const lastTick = useRef(-1);
  const lastActions = useRef<Record<string, string>>({});

  const unlocked = useMemo(
    () => new Set(state.rooms.filter((r) => r.unlocked).map((r) => r.id)),
    [state.rooms],
  );

  // Seed / sync walkers when agents change
  useEffect(() => {
    setWalkers((prev) => {
      const byId = new Map(prev.map((w) => [w.agentId, w]));
      return state.agents.map((a, i) => {
        const existing = byId.get(a.id);
        const home = stationCenter(a.roomId);
        if (existing) {
          return {
            ...existing,
            name: a.name,
            role: a.role,
            palette: rolePalette(a.role),
          };
        }
        const jitter = (i % 3) * 4;
        return {
          id: `w-${a.id}`,
          agentId: a.id,
          name: a.name.split("—")[0]?.trim() ?? a.name,
          role: a.role,
          x: home.x + jitter,
          y: home.y + (i % 2) * 3,
          targetX: home.x + jitter,
          targetY: home.y,
          facing: "down" as const,
          carrying: null,
          palette: rolePalette(a.role),
        };
      });
    });
  }, [state.agents]);

  // On each sim tick: assign walk targets + spawn flying cargo
  useEffect(() => {
    if (state.tick === lastTick.current) return;
    lastTick.current = state.tick;

    const vault = stationCenter("vault");
    const newCargo: FlyingCargo[] = [];

    setWalkers((prev) =>
      prev.map((w, idx) => {
        const agent = state.agents.find((a) => a.id === w.agentId);
        if (!agent) return w;

        const prevAction = lastActions.current[agent.id];
        lastActions.current[agent.id] = agent.lastAction;

        const busy =
          agent.status === "working" ||
          agent.status === "audited" ||
          agent.lastAction !== prevAction;

        if (!busy && Math.random() > 0.35) return w;

        const destId = pickJobTarget(agent.roomId, state.tick + idx);
        // Only walk into unlocked rooms (vault always open)
        if (destId !== "vault" && destId !== "room-design" && !unlocked.has(destId)) {
          const home = stationCenter(agent.roomId);
          return { ...w, targetX: home.x, targetY: home.y };
        }

        const dest = stationCenter(destId);
        const ox = ((idx * 7) % 11) - 5;
        const oy = ((idx * 5) % 9) - 4;
        const carrying = cargoForAction(agent.lastAction, agent.role);

        // Deliveries to vault become flying cargo
        if (carrying === "coin" || (carrying && destId === "vault")) {
          newCargo.push({
            id: `c-${agent.id}-${state.tick}`,
            kind: carrying ?? "coin",
            x: w.x,
            y: w.y - 8,
            targetX: vault.x,
            targetY: vault.y,
            born: performance.now(),
          });
        } else if (carrying && destId === agent.roomId) {
          // Design → store: fly product to the store station
          const storePos = stationCenter(agent.roomId);
          newCargo.push({
            id: `p-${agent.id}-${state.tick}`,
            kind: carrying,
            x: w.x,
            y: w.y - 8,
            targetX: storePos.x,
            targetY: storePos.y,
            born: performance.now(),
          });
        }

        const dx = dest.x - w.x;
        const dy = dest.y - w.y;
        let facing: Walker["facing"] = "down";
        if (Math.abs(dx) > Math.abs(dy)) facing = dx > 0 ? "right" : "left";
        else facing = dy > 0 ? "down" : "up";

        return {
          ...w,
          targetX: dest.x + ox,
          targetY: dest.y + oy,
          facing,
          carrying: destId === "vault" ? carrying : carrying,
        };
      }),
    );

    if (newCargo.length) {
      setCargo((c) => [...newCargo, ...c].slice(0, 24));
    }
  }, [state.tick, state.agents, unlocked]);

  // Animation loop
  useEffect(() => {
    let raf = 0;
    const speed = 1.6;
    const step = () => {
      setWalkers((prev) =>
        prev.map((w) => {
          const dx = w.targetX - w.x;
          const dy = w.targetY - w.y;
          const dist = Math.hypot(dx, dy);
          if (dist < 1.2) {
            return { ...w, x: w.targetX, y: w.targetY, carrying: dist < 0.5 ? null : w.carrying };
          }
          const nx = w.x + (dx / dist) * speed;
          const ny = w.y + (dy / dist) * speed;
          let facing = w.facing;
          if (Math.abs(dx) > Math.abs(dy)) facing = dx > 0 ? "right" : "left";
          else facing = dy > 0 ? "down" : "up";
          return { ...w, x: nx, y: ny, facing };
        }),
      );

      setCargo((prev) =>
        prev
          .map((c) => {
            const dx = c.targetX - c.x;
            const dy = c.targetY - c.y;
            const dist = Math.hypot(dx, dy);
            if (dist < 2) return null;
            const sp = 2.4;
            return { ...c, x: c.x + (dx / dist) * sp, y: c.y + (dy / dist) * sp };
          })
          .filter(Boolean) as FlyingCargo[],
      );

      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, []);

  const width = MAP_COLS * TILE;
  const height = MAP_ROWS * TILE;

  return (
    <div className="overworld-wrap">
      <div className="overworld-chrome">
        <span className="ow-title">YWP FACTORY</span>
        <span className="ow-hint">Agents walk jobs · deliver $ &amp; goods to stations</span>
      </div>
      <div
        className="overworld"
        style={{ width, height }}
        aria-label="Pixel factory map"
      >
        <div className="ow-floor" />

        {STATIONS.map((st) => {
          const isVault = st.id === "vault";
          const roomOpen =
            isVault || Boolean(state.rooms.find((r) => r.id === st.id)?.unlocked);
          return (
            <div
              key={st.id}
              className={`ow-station kind-${st.kind} ${roomOpen ? "open" : "locked"}`}
              style={{
                left: st.x * TILE,
                top: st.y * TILE,
                width: TILE * 2,
                height: TILE * 2,
              }}
            >
              <div className="ow-roof" />
              <div className="ow-door" />
              <span className="ow-label">{st.label}</span>
            </div>
          );
        })}

        {/* Path dots */}
        <div className="ow-path" />

        {cargo.map((c) => (
          <div
            key={c.id}
            className={`ow-cargo cargo-${c.kind}`}
            style={{ left: c.x - 6, top: c.y - 6 }}
            title={c.kind}
          />
        ))}

        {walkers.map((w) => {
          const colors = PALETTES[w.palette] ?? PALETTES[2]!;
          return (
            <div
              key={w.id}
              className={`ow-walker face-${w.facing}`}
              style={
                {
                  left: w.x - 8,
                  top: w.y - 12,
                  "--c1": colors[0],
                  "--c2": colors[1],
                  "--c3": colors[2],
                } as CSSProperties
              }
              title={`${w.name} (${w.role})`}
            >
              <div className="ow-sprite">
                <i className="head" />
                <i className="body" />
                <i className="feet" />
              </div>
              {w.carrying && <div className={`ow-hand cargo-${w.carrying}`} />}
              <span className="ow-name">{w.name}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
