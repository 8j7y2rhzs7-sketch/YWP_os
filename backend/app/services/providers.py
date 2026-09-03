from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

from app.schemas import CandidateInput


def _start(slate_date: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(slate_date, time(hour, minute), tzinfo=UTC)


def _base(
    *,
    slate_date: date,
    candidate_id: str,
    event_id: str,
    event_name: str,
    sport: str,
    league: str,
    market_type: str,
    selection: str,
    odds: int,
    probability: float,
    variance: float,
    quality: float,
    thesis_key: str,
    script_key: str,
    reason_codes: list[str],
    reasoning: list[str],
    player_key: str | None = None,
    line: Decimal | None = None,
    hour: int = 23,
    **extra: object,
) -> CandidateInput:
    now = datetime.now(UTC)
    return CandidateInput(
        candidate_id=candidate_id,
        event_id=event_id,
        event_name=event_name,
        sport=sport,
        league=league,
        start_time=_start(slate_date, hour),
        market_type=market_type,
        selection=selection,
        line=line,
        american_odds=odds,
        estimated_probability=probability,
        variance=variance,
        data_quality=quality,
        factors={"matchup": 0.66, "current_form": 0.52, "market_value": 0.40},
        reason_codes=reason_codes,
        reasoning=reasoning,
        data_source="YWP_DEMO_PROVIDER",
        source_timestamp=now,
        source_status={
            "schedule": "confirmed",
            "market": "confirmed",
            "lineup": "confirmed",
            "injuries": "confirmed",
        },
        schedule_verified=True,
        universe_scan_complete=True,
        current_form_verified=True,
        l5_l10_verified=True,
        lineup_confirmed=True,
        injuries_verified=True,
        weather_verified=True,
        starter_confirmed=True,
        motivation_rotation_verified=True,
        home_away_verified=True,
        market_movement_verified=True,
        sport_specific_sweep_complete=True,
        recent_hit_rate=min(0.9, probability + 0.08),
        average_cushion=1.8,
        matchup_score=0.72,
        script_alignment=0.70,
        multiple_paths_score=0.72,
        role_stability=0.82,
        miss_by_one_count_l10=1,
        ain_checks={
            "recent_form_l5_l10": True,
            "situational_angles": True,
            "h2h_context": True,
        },
        thesis_key=thesis_key,
        script_key=script_key,
        player_key=player_key,
        safer_alternative=f"Safer version of {selection}",
        higher_upside=f"Higher-upside version of {selection}",
        invalidation_conditions=["Material lineup change", "Large adverse price move"],
        live_trigger="Recheck price and underlying game state before any live entry.",
        hedge=(
            "Compare any cash-out offer with current fair remaining value. Reduce exposure or "
            "use an opposing protected market only after material thesis change, an exposure "
            "limit, or independent live value."
        ),
        **extra,
    )


def demo_slate(sport: str, slate_date: date) -> list[CandidateInput]:
    sport_key = sport.lower()
    if sport_key == "mlb":
        return _demo_mlb(slate_date)
    if sport_key in {"wnba", "nba", "basketball"}:
        return _demo_basketball(sport_key, slate_date)
    if sport_key == "soccer":
        return _demo_soccer(slate_date)
    return _demo_generic(sport_key, slate_date)


def _demo_mlb(slate_date: date) -> list[CandidateInput]:
    return [
        _base(
            slate_date=slate_date,
            candidate_id="demo-mlb-1",
            event_id="demo-harbor-metro",
            event_name="Demo Harbor @ Demo Metro",
            sport="mlb",
            league="MLB",
            market_type="moneyline",
            selection="Demo Metro ML",
            odds=-145,
            probability=0.68,
            variance=0.22,
            quality=0.96,
            thesis_key="demo-metro-moneyline",
            script_key="demo-harbor-metro-home-control",
            reason_codes=["STARTING_PITCHER_EDGE", "HOME_FIELD", "LINEUP_EDGE"],
            reasoning=["Verified starter, lineup, and bullpen inputs favor the home side."],
            team_image_url="https://midfield.mlbstatic.com/v1/team/147/spots/96",
        ),
        _base(
            slate_date=slate_date,
            candidate_id="demo-mlb-2",
            event_id="demo-coastal-north",
            event_name="Demo Coastal @ Demo North",
            sport="mlb",
            league="MLB",
            market_type="game_total_under",
            selection="Under 8.5 runs",
            line=Decimal("8.5"),
            odds=-108,
            probability=0.61,
            variance=0.28,
            quality=0.93,
            thesis_key="demo-coastal-north-under-8-5",
            script_key="demo-coastal-north-low-scoring",
            reason_codes=["STARTING_PITCHER_EDGE", "BULLPEN_EDGE"],
            reasoning=["Both verified run-prevention paths support the total."],
            team_image_url="https://midfield.mlbstatic.com/v1/team/121/spots/96",
        ),
        _base(
            slate_date=slate_date,
            candidate_id="demo-mlb-3",
            event_id="demo-river-lake",
            event_name="Demo River @ Demo Lake",
            sport="mlb",
            league="MLB",
            market_type="player_hits_over",
            selection="A. Carter 1+ hit",
            line=Decimal("0.5"),
            odds=-155,
            probability=0.69,
            variance=0.31,
            quality=0.91,
            thesis_key="demo-a-carter-hit",
            script_key="demo-river-lake-carter-contact",
            player_key="demo-a-carter",
            reason_codes=["PLATOON_EDGE", "CURRENT_FORM"],
            reasoning=["Contact quality and the supplied matchup projection clear the price."],
            image_url=(
                "https://img.mlbstatic.com/mlb-photos/image/upload/"
                "d_people:generic:headshot:67:current.png/w_180,q_auto:best/"
                "v1/people/0/headshot/silo/current"
            ),
            team_image_url="https://midfield.mlbstatic.com/v1/team/119/spots/96",
        ),
        _base(
            slate_date=slate_date,
            candidate_id="demo-mlb-4",
            event_id="demo-valley-capital",
            event_name="Demo Valley @ Demo Capital",
            sport="mlb",
            league="MLB",
            market_type="first_5_moneyline",
            selection="Demo Valley F5 +0.5",
            line=Decimal("0.5"),
            odds=-125,
            probability=0.63,
            variance=0.27,
            quality=0.90,
            thesis_key="demo-valley-f5-plus-half",
            script_key="demo-valley-capital-starter-edge",
            reason_codes=["STARTING_PITCHER_EDGE", "QUICK_CASH"],
            reasoning=["The early-game starter edge avoids late bullpen variance."],
            quick_cash=True,
        ),
        _base(
            slate_date=slate_date,
            candidate_id="demo-mlb-5",
            event_id="demo-pine-summit",
            event_name="Demo Pine @ Demo Summit",
            sport="mlb",
            league="MLB",
            market_type="team_total_over",
            selection="Demo Summit over 3.5 runs",
            line=Decimal("3.5"),
            odds=-112,
            probability=0.60,
            variance=0.34,
            quality=0.90,
            thesis_key="demo-summit-tt-over-3-5",
            script_key="demo-pine-summit-home-offense",
            reason_codes=["LINEUP_EDGE", "BULLPEN_EDGE"],
            reasoning=["Lineup and bullpen paths independently support the team total."],
        ),
        _base(
            slate_date=slate_date,
            candidate_id="demo-mlb-6",
            event_id="demo-forest-union",
            event_name="Demo Forest @ Demo Union",
            sport="mlb",
            league="MLB",
            market_type="player_strikeouts_over",
            selection="J. Stone over 5.5 strikeouts",
            line=Decimal("5.5"),
            odds=-115,
            probability=0.64,
            variance=0.37,
            quality=0.92,
            thesis_key="demo-j-stone-k-over-5-5",
            script_key="demo-forest-union-stone-strikeouts",
            player_key="demo-j-stone",
            reason_codes=["STRIKEOUT_MATCHUP"],
            reasoning=[
                "Raw strikeout matchup is favorable, but the workload gate controls the decision."
            ],
            market_is_pitcher_strikeout_over=True,
            first_start_back=True,
            normal_workload_confirmed=False,
            k_duration_verified=False,
        ),
        _base(
            slate_date=slate_date,
            candidate_id="demo-mlb-7",
            event_id="demo-east-west",
            event_name="Demo East @ Demo West",
            sport="mlb",
            league="MLB",
            market_type="game_total_over",
            selection="Over 6.5 runs",
            line=Decimal("6.5"),
            odds=-260,
            probability=0.82,
            variance=0.30,
            quality=0.84,
            thesis_key="demo-east-west-over-6-5",
            script_key="demo-east-west-runs",
            reason_codes=["LOW_ALT_TOTAL"],
            reasoning=["The low number looks safe but still requires independent scoring paths."],
            low_alt_over=True,
            credible_scoring_paths=1,
            dominant_scoring_path_verified=False,
        ),
        _base(
            slate_date=slate_date,
            candidate_id="demo-mlb-8",
            event_id="demo-bay-central",
            event_name="Demo Bay @ Demo Central",
            sport="mlb",
            league="MLB",
            market_type="moneyline",
            selection="Demo Central ML",
            odds=-340,
            probability=0.78,
            variance=0.24,
            quality=0.86,
            thesis_key="demo-central-expensive-ml",
            script_key="demo-bay-central-home",
            reason_codes=["HOME_FIELD"],
            reasoning=["Favorite price is evaluated for value, not assumed safe."],
            heavily_juiced_filler=True,
            independent_value_verified=False,
        ),
    ]


def _demo_basketball(sport: str, slate_date: date) -> list[CandidateInput]:
    league = sport.upper() if sport != "basketball" else "WNBA"
    rows = [
        ("1", "Demo Comets @ Demo Waves", "K. Reed 15+ points", -150, 0.69, 0.26, "points"),
        ("2", "Demo Sparks @ Demo Flight", "M. Cole 5+ assists", -135, 0.66, 0.29, "assists"),
        ("3", "Demo Storm @ Demo Gold", "T. Lane 6+ rebounds", -125, 0.64, 0.31, "rebounds"),
        ("4", "Demo North @ Demo South", "Demo South +4.5", -110, 0.58, 0.34, "spread"),
        ("5", "Demo East @ Demo West", "Under 166.5", -108, 0.57, 0.38, "total"),
        ("6", "Demo Sky @ Demo Sun", "R. Hill 2+ threes", +105, 0.54, 0.48, "threes"),
    ]
    return [
        _base(
            slate_date=slate_date,
            candidate_id=f"demo-{sport}-{key}",
            event_id=f"demo-basketball-event-{key}",
            event_name=event,
            sport=sport,
            league=league,
            market_type=market,
            selection=selection,
            odds=odds,
            probability=probability,
            variance=variance,
            quality=0.92 if key in {"1", "2", "3"} else 0.88,
            thesis_key=f"demo-{sport}-{market}-{key}",
            script_key=f"demo-basketball-script-{key}",
            player_key=f"demo-player-{key}" if market not in {"spread", "total"} else None,
            reason_codes=["ROLE_STABILITY", "L10_CUSHION", "GAME_SCRIPT"],
            reasoning=[
                "Role, recent distribution, matchup, and expected game script are "
                "supplied and verified."
            ],
            team_image_url=(
                f"https://a.espncdn.com/i/teamlogos/wnba/500/"
                f"{['ind', 'lv', 'ny', 'sea', 'min', 'chi'][int(key) - 1]}.png"
            ),
        )
        for key, event, selection, odds, probability, variance, market in rows
    ]


def _demo_soccer(slate_date: date) -> list[CandidateInput]:
    common = [
        ("1", "Demo Albion v Demo City", "Demo Albion or draw", -180, 0.72, 0.22, "double_chance"),
        ("2", "Demo United v Demo Rovers", "Over 1.5 goals", -190, 0.74, 0.24, "game_total_over"),
        (
            "3",
            "Demo Athletic v Demo County",
            "Demo Athletic team over 0.5",
            -210,
            0.77,
            0.25,
            "team_total_over",
        ),
        ("4", "Demo FC v Demo Sporting", "Both teams to score", +105, 0.55, 0.42, "btts"),
        ("5", "Demo Real v Demo Dynamo", "Under 3.5 goals", -150, 0.66, 0.29, "game_total_under"),
    ]
    candidates = [
        _base(
            slate_date=slate_date,
            candidate_id=f"demo-soccer-{key}",
            event_id=f"demo-soccer-event-{key}",
            event_name=event,
            sport="soccer",
            league="Demo Premier",
            market_type=market,
            selection=selection,
            odds=odds,
            probability=probability,
            variance=variance,
            quality=0.91,
            thesis_key=f"demo-soccer-thesis-{key}",
            script_key=f"demo-soccer-script-{key}",
            reason_codes=["CURRENT_FORM", "TACTICAL_MATCHUP", "MARKET_VALUE"],
            reasoning=[
                "Current form, availability, home/away splits, and tactical matchup are verified."
            ],
        )
        for key, event, selection, odds, probability, variance, market in common
    ]
    candidates.append(
        _base(
            slate_date=slate_date,
            candidate_id="demo-soccer-et-trap",
            event_id="demo-soccer-knockout",
            event_name="Demo Kings v Demo Union — knockout",
            sport="soccer",
            league="Demo Cup",
            market_type="moneyline",
            market_period="90_min",
            selection="Demo Kings 90-minute ML",
            odds=-130,
            probability=0.62,
            variance=0.39,
            quality=0.94,
            thesis_key="demo-kings-90-minute-ml",
            script_key="demo-kings-knockout-advance",
            reason_codes=["KNOCKOUT_FAVORITE"],
            reasoning=["The team may advance without winning in regulation."],
            is_knockout=True,
            draw_probability=0.29,
            extra_time_available=True,
            to_qualify_market_available=True,
        )
    )
    return candidates


def _demo_generic(sport: str, slate_date: date) -> list[CandidateInput]:
    return [
        _base(
            slate_date=slate_date,
            candidate_id=f"demo-{sport}-{index}",
            event_id=f"demo-{sport}-event-{index}",
            event_name=f"Demo {sport.title()} Event {index}",
            sport=sport,
            league=f"Demo {sport.title()}",
            market_type="moneyline",
            selection=f"Demo selection {index}",
            odds=-120 + index * 5,
            probability=0.62 - index * 0.01,
            variance=0.27 + index * 0.03,
            quality=0.90,
            thesis_key=f"demo-{sport}-thesis-{index}",
            script_key=f"demo-{sport}-script-{index}",
            reason_codes=["MATCHUP_EDGE", "MARKET_VALUE"],
            reasoning=["Demonstration inputs only; connect a live provider before real use."],
        )
        for index in range(1, 6)
    ]
