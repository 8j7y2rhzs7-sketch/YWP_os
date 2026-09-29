"""Stage 6 — within-game correlation priors for ticket legs."""

from __future__ import annotations

from typing import Any, Protocol


class LegLike(Protocol):
    event_id: str
    player_key: str | None
    script_key: str
    thesis_key: str
    market_type: str
    selection: str


def pairwise_correlation(a: LegLike, b: LegLike) -> float:
    """Return ρ in [0, 0.85] for how strongly one leg moves with another."""
    if a.event_id != b.event_id:
        return 0.0
    if a.player_key and b.player_key and a.player_key == b.player_key:
        return 0.72
    if a.script_key and b.script_key and a.script_key == b.script_key:
        return 0.55
    if a.thesis_key and b.thesis_key and a.thesis_key == b.thesis_key:
        return 0.60
    # Same game, different players/markets — still dependent via game state.
    market_a = (a.market_type or "").lower()
    market_b = (b.market_type or "").lower()
    team_markets = ("moneyline", "spread", "run_line", "total", "team_total")
    if any(k in market_a for k in team_markets) and any(k in market_b for k in team_markets):
        return 0.45
    if any(k in market_a for k in team_markets) or any(k in market_b for k in team_markets):
        return 0.28
    return 0.18


def correlation_matrix(legs: list[Any]) -> dict[str, Any]:
    n = len(legs)
    matrix = [[0.0] * n for _ in range(n)]
    max_rho = 0.0
    pairs: list[dict[str, Any]] = []
    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            rho = pairwise_correlation(legs[i], legs[j])
            matrix[i][j] = rho
            matrix[j][i] = rho
            max_rho = max(max_rho, rho)
            if rho > 0:
                pairs.append(
                    {
                        "i": i,
                        "j": j,
                        "rho": round(rho, 3),
                        "a": getattr(legs[i], "selection", str(i)),
                        "b": getattr(legs[j], "selection", str(j)),
                    }
                )
    return {
        "size": n,
        "matrix": matrix,
        "max_rho": round(max_rho, 3),
        "dependent_pairs": pairs,
        "status": "ok" if n else "empty",
    }
