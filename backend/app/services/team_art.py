"""Public team-logo URLs used as sports graphics when player photos are unavailable."""
from __future__ import annotations

from app.services.mlb_provider import team_logo_url

ESPN = "https://a.espncdn.com/i/teamlogos"

# Odds API / display names -> ESPN slug.
TEAM_SLUGS: dict[str, dict[str, str]] = {
    "wnba": {
        "atlanta dream": "atl",
        "chicago sky": "chi",
        "connecticut sun": "conn",
        "dallas wings": "dal",
        "golden state valkyries": "gs",
        "indiana fever": "ind",
        "las vegas aces": "lv",
        "los angeles sparks": "la",
        "minnesota lynx": "min",
        "new york liberty": "ny",
        "phoenix mercury": "phx",
        "seattle storm": "sea",
        "washington mystics": "wsh",
    },
    "nba": {
        "atlanta hawks": "atl",
        "boston celtics": "bos",
        "brooklyn nets": "bkn",
        "charlotte hornets": "cha",
        "chicago bulls": "chi",
        "cleveland cavaliers": "cle",
        "dallas mavericks": "dal",
        "denver nuggets": "den",
        "detroit pistons": "det",
        "golden state warriors": "gs",
        "houston rockets": "hou",
        "indiana pacers": "ind",
        "los angeles clippers": "lac",
        "la clippers": "lac",
        "los angeles lakers": "lal",
        "la lakers": "lal",
        "memphis grizzlies": "mem",
        "miami heat": "mia",
        "milwaukee bucks": "mil",
        "minnesota timberwolves": "min",
        "new orleans pelicans": "no",
        "new york knicks": "ny",
        "oklahoma city thunder": "okc",
        "orlando magic": "orl",
        "philadelphia 76ers": "phi",
        "phoenix suns": "phx",
        "portland trail blazers": "por",
        "sacramento kings": "sac",
        "san antonio spurs": "sa",
        "toronto raptors": "tor",
        "utah jazz": "utah",
        "washington wizards": "wsh",
    },
    "nfl": {
        "arizona cardinals": "ari",
        "atlanta falcons": "atl",
        "baltimore ravens": "bal",
        "buffalo bills": "buf",
        "carolina panthers": "car",
        "chicago bears": "chi",
        "cincinnati bengals": "cin",
        "cleveland browns": "cle",
        "dallas cowboys": "dal",
        "denver broncos": "den",
        "detroit lions": "det",
        "green bay packers": "gb",
        "houston texans": "hou",
        "indianapolis colts": "ind",
        "jacksonville jaguars": "jax",
        "kansas city chiefs": "kc",
        "las vegas raiders": "lv",
        "los angeles chargers": "lac",
        "los angeles rams": "lar",
        "miami dolphins": "mia",
        "minnesota vikings": "min",
        "new england patriots": "ne",
        "new orleans saints": "no",
        "new york giants": "nyg",
        "new york jets": "nyj",
        "philadelphia eagles": "phi",
        "pittsburgh steelers": "pit",
        "san francisco 49ers": "sf",
        "seattle seahawks": "sea",
        "tampa bay buccaneers": "tb",
        "tennessee titans": "ten",
        "washington commanders": "wsh",
    },
    "nhl": {
        "anaheim ducks": "ana",
        "boston bruins": "bos",
        "buffalo sabres": "buf",
        "calgary flames": "cgy",
        "carolina hurricanes": "car",
        "chicago blackhawks": "chi",
        "colorado avalanche": "col",
        "columbus blue jackets": "cbj",
        "dallas stars": "dal",
        "detroit red wings": "det",
        "edmonton oilers": "edm",
        "florida panthers": "fla",
        "los angeles kings": "la",
        "minnesota wild": "min",
        "montreal canadiens": "mtl",
        "nashville predators": "nsh",
        "new jersey devils": "nj",
        "new york islanders": "nyi",
        "new york rangers": "nyr",
        "ottawa senators": "ott",
        "philadelphia flyers": "phi",
        "pittsburgh penguins": "pit",
        "san jose sharks": "sj",
        "seattle kraken": "sea",
        "st. louis blues": "stl",
        "st louis blues": "stl",
        "tampa bay lightning": "tb",
        "toronto maple leafs": "tor",
        "utah hockey club": "utah",
        "vancouver canucks": "van",
        "vegas golden knights": "vgk",
        "washington capitals": "wsh",
        "winnipeg jets": "wpg",
    },
}

MLB_TEAM_IDS: dict[str, int] = {
    "arizona diamondbacks": 109,
    "atlanta braves": 144,
    "baltimore orioles": 110,
    "boston red sox": 111,
    "chicago cubs": 112,
    "chicago white sox": 145,
    "cincinnati reds": 113,
    "cleveland guardians": 114,
    "colorado rockies": 115,
    "detroit tigers": 116,
    "houston astros": 117,
    "kansas city royals": 118,
    "los angeles angels": 108,
    "los angeles dodgers": 119,
    "miami marlins": 146,
    "milwaukee brewers": 158,
    "minnesota twins": 142,
    "new york mets": 121,
    "new york yankees": 147,
    "oakland athletics": 133,
    "athletics": 133,
    "philadelphia phillies": 143,
    "pittsburgh pirates": 134,
    "san diego padres": 135,
    "san francisco giants": 137,
    "seattle mariners": 136,
    "st. louis cardinals": 138,
    "st louis cardinals": 138,
    "tampa bay rays": 139,
    "texas rangers": 140,
    "toronto blue jays": 141,
    "washington nationals": 120,
}

ESPN_LEAGUE = {
    "wnba": "wnba",
    "nba": "nba",
    "nfl": "nfl",
    "nhl": "nhl",
    "ncaaf": "ncaa/500",
    "ncaab": "ncaa/500",
}


def _norm(value: str) -> str:
    return " ".join(value.lower().replace(".", "").split())


def team_logo(sport: str, team_name: str | None) -> str | None:
    if not team_name:
        return None
    key = _norm(team_name)
    sport_key = sport.lower()
    if sport_key in {"mlb", "kbo"}:
        team_id = MLB_TEAM_IDS.get(key)
        return team_logo_url(team_id) if team_id else None
    slugs = TEAM_SLUGS.get(sport_key, {})
    slug = slugs.get(key)
    if not slug:
        for name, code in slugs.items():
            if name in key or key in name:
                slug = code
                break
    league = ESPN_LEAGUE.get(sport_key)
    if not slug or not league:
        return None
    return f"{ESPN}/{league}/{slug}.png"


def logo_for_play(sport: str, selection: str, event_name: str | None = None) -> str | None:
    """Best logo for a market: named team first, otherwise home side of the event."""
    haystack = f"{selection} {event_name or ''}"
    sport_key = sport.lower()
    names = list(TEAM_SLUGS.get(sport_key, {})) + list(MLB_TEAM_IDS)
    for name in sorted(names, key=len, reverse=True):
        if name in _norm(haystack):
            return team_logo(sport_key, name)
    if event_name and "@" in event_name:
        home = event_name.split("@")[-1].strip()
        return team_logo(sport_key, home)
    return None
