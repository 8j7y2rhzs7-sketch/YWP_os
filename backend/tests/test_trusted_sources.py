from __future__ import annotations

from datetime import date

from app.services.research_searchers import search_market_consensus, search_mlb_park, search_mlb_umpires
from app.services.trusted_sources import trusted_sources_manifest


def test_trusted_sources_manifest_lists_certified_providers() -> None:
    manifest = trusted_sources_manifest()
    ids = {item["id"] for item in manifest["sources"]}
    assert "mlb_stats_api" in ids
    assert "the_odds_api" in ids
    assert "open_meteo" in ids
    assert "ywp_mlb_model" in ids
    assert "schedule" in manifest["category_owners"]
    assert "umpires" in manifest["category_owners"]


def test_umpire_searcher_uses_schedule_officials() -> None:
    officials = [
        {
            "official": {"id": 1, "fullName": "Test Umpire"},
            "officialType": "Home Plate",
        }
    ]
    result = search_mlb_umpires(123, schedule_officials=officials)
    assert result["verified"] is True
    assert result["source_id"] == "mlb_stats_api"
    assert result["home_plate"]["name"] == "Test Umpire"


def test_park_searcher_requires_venue() -> None:
    missing = search_mlb_park({"game_pk": 1}, {})
    assert missing["verified"] is False
    found = search_mlb_park({"game_pk": 1, "venue": "PNC Park", "venue_id": 31}, {})
    assert found["verified"] is True
    assert found["venue"] == "PNC Park"


def test_market_consensus_counts_trusted_quotes() -> None:
    bookmakers = [
        {
            "key": "draftkings",
            "markets": [{"key": "h2h", "outcomes": [{"name": "Home Club", "price": -120}]}],
        },
        {
            "key": "fanduel",
            "markets": [{"key": "h2h", "outcomes": [{"name": "Home Club", "price": -115}]}],
        },
    ]
    result = search_market_consensus(bookmakers, "h2h", "Home Club")
    assert result["verified"] is True
    assert result["book_count"] == 2
    assert result["consensus"] is True
