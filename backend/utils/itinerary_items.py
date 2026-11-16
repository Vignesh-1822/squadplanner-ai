"""One ordered list per day, with each stop's place data inlined.

The agent writes a day as three parallel lists — `schedule` (the clock), `activities` (place
records) and `meals` (prose) — with no key joining them. Anything consuming a day therefore had
to re-join them by matching names as strings, which is fragile in both directions: a meal note
reading "Lunch at California Academy of Sciences" would claim the museum, and a trailing full
stop ("South Unit." vs "South Unit") would stop a row matching at all.

`route_stops` is already the resolved, ordered join — it carries `place_id`, coordinates and
address for activities, meals and the hotel alike, including places resolved by text lookup that
never made it into `activities`. This module merges the richer fields (category, rating, tags)
back onto it and attaches each route leg to the stop it departs from, producing a single list
that needs no matching at all.

Derived on read rather than persisted, so trips generated before this existed gain it for free.
"""

from typing import Any

_STOP_TO_ITEM_TYPE = {
    "restaurant": "meal",
    "activity": "activity",
    "hotel": "hotel",
}

# Fields that live on an `activities` record but not on a route stop.
_RICH_FIELDS = ("category", "rating", "price_level", "tags")


def _normalize(text: Any) -> str:
    """Compare names by their words alone, ignoring case and punctuation."""
    cleaned = "".join(ch if ch.isalnum() else " " for ch in str(text or "").lower())
    return " ".join(cleaned.split())


def _rich_lookup(day: dict) -> dict[str, dict]:
    """Index the day's activity records by place_id and by normalized name."""
    index: dict[str, dict] = {}
    for activity in day.get("activities") or []:
        if not isinstance(activity, dict):
            continue
        if activity.get("place_id"):
            index[str(activity["place_id"])] = activity
        name = _normalize(activity.get("name"))
        if name:
            index.setdefault(name, activity)
    return index


def build_day_items(day: dict) -> list[dict]:
    """Return the day as one ordered list of items, or [] when the day predates route_stops."""
    stops = day.get("route_stops") or []
    if not stops:
        return []

    index = _rich_lookup(day)
    routes = day.get("routes") or []
    items: list[dict] = []

    for stop in stops:
        if not isinstance(stop, dict):
            continue

        # Prefer the place_id match; fall back to the name for stops resolved by text lookup,
        # which may not appear in `activities` at all.
        rich = index.get(str(stop.get("place_id") or "")) or index.get(_normalize(stop.get("label"))) or {}

        place = {
            "place_id": stop.get("place_id"),
            "name": stop.get("label"),
            "address": stop.get("address", ""),
            "lat": stop.get("lat"),
            "lng": stop.get("lng"),
        }
        for field in _RICH_FIELDS:
            if rich.get(field) is not None:
                place[field] = rich[field]

        items.append(
            {
                "order": stop.get("order"),
                "time": stop.get("time"),
                "type": _STOP_TO_ITEM_TYPE.get(str(stop.get("type")), "activity"),
                "label": stop.get("label"),
                "notes": stop.get("notes", ""),
                "source": stop.get("source"),
                "place": place if place.get("lat") is not None else None,
            }
        )

    # plan_stop_routes builds one leg per consecutive pair of stops, so leg i leaves item i.
    for index_, leg in enumerate(routes):
        if index_ < len(items) - 1 and isinstance(leg, dict):
            items[index_]["leg_to_next"] = {
                "distance_meters": leg.get("distance_meters"),
                "duration_seconds": leg.get("duration_seconds"),
                "mode": leg.get("mode"),
                "polyline": leg.get("polyline"),
            }

    return items


def attach_day_items(days: list[dict]) -> list[dict]:
    """Add `items` to every day that can produce one, in place."""
    for day in days or []:
        items = build_day_items(day)
        if items:
            day["items"] = items
    return days
