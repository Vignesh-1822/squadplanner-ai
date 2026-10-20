"""Deterministic and trajectory scorer unit tests."""

from evals.scorers.deterministic import budget_metrics, dates, dietary, flight_alignment, radius
from evals.scorers.trajectory import retry_routes


def test_budget_compliance_and_fairness_are_separate():
    state = {
        "members": [
            {"member_id": "a", "budget_usd": 100},
            {"member_id": "b", "budget_usd": 100},
        ],
        "flights": [
            {"member_id": "a", "price_usd": 150},
            {"member_id": "b", "price_usd": 150},
        ],
        "hotel": {"total_price_usd": 0},
        "days": [],
    }
    result = budget_metrics(state)
    assert result["budget_compliance"]["passed"] is False
    assert result["fairness_spread"]["passed"] is True


def test_fairness_matches_production_by_excluding_itinerary_costs():
    state = {
        "members": [
            {"member_id": "a", "budget_usd": 100},
            {"member_id": "b", "budget_usd": 200},
        ],
        "flights": [
            {"member_id": "a", "price_usd": 50},
            {"member_id": "b", "price_usd": 50},
        ],
        "hotel": {"total_price_usd": 0},
        "days": [{"estimated_day_cost_usd": 200}],
    }
    result = budget_metrics(state)
    assert result["budget_compliance"]["passed"] is False
    assert result["fairness_spread"]["passed"] is True


def test_date_scorer_requires_contiguous_window():
    state = {
        "start_date": "2026-09-08",
        "end_date": "2026-09-11",
        "trip_duration_days": 3,
        "days": [
            {"date": "2026-09-08"},
            {"date": "2026-09-09"},
            {"date": "2026-09-10"},
        ],
    }
    assert dates(state)["passed"] is True
    state["days"][1]["date"] = "2026-09-10"
    assert dates(state)["passed"] is False


def test_radius_joins_destination_catalog():
    state = {
        "selected_destination": "New York City",
        "candidate_destinations": [{"id": "new_york_city", "name": "New York City"}],
        "days": [{"activities": [{"name": "Nearby", "lat": 40.7128, "lng": -74.006}]}],
    }
    # Catalog IDs evolve independently from display names; use an actual first
    # destination to keep the join itself under test.
    from evals.scorers import deterministic

    destination = next(iter(deterministic._DESTINATIONS.values()))
    state["selected_destination"] = destination["name"]
    state["candidate_destinations"][0] = {"id": destination["id"], "name": destination["name"]}
    state["days"][0]["activities"][0].update({"lat": destination["lat"], "lng": destination["lng"]})
    assert radius(state)["passed"] is True


def test_retry_scorer_compares_case_intent():
    events = [
        {"event": "on_chain_start", "name": "select_destination"},
        {"event": "on_chain_start", "name": "select_destination"},
        {"event": "on_chain_start", "name": "search_hotel"},
    ]
    result = retry_routes(
        {"expect_budget_retry": True, "expect_fairness_retry": False},
        events,
    )
    assert result["passed"] is True


def test_dietary_scorer_uses_boundaries_and_compliant_qualifiers():
    state = {
        "members": [
            {"food_restrictions": ["vegan"]},
            {"food_restrictions": ["gluten_free"]},
        ],
        "days": [
            {
                "day_number": 1,
                "meals": ["Vegan eggplant bowl", "Gluten-free bread with vegetables"],
            }
        ],
    }
    assert dietary(state)["passed"] is True


def test_estimated_flights_are_explicitly_unscorable():
    result = flight_alignment(
        {
            "flights": [{"is_estimated": True}],
            "days": [{"schedule": [{"time": "10:00"}]}],
        }
    )
    assert result["passed"] is False
    assert result["scorable"] is False
