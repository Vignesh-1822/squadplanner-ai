"""Natural-language preference extraction node."""

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from agent.state import DecisionLogEntry, TripState
from config import get_llm


DEFAULT_CONSTRAINTS = {
    "raw_member_notes": [],
    "raw_group_notes": "",
    "hard_constraints": [],
    "soft_preferences": [],
    "schedule": {
        "avoid_early_mornings": False,
        "earliest_start_time": None,
        "pace": "balanced",
    },
    "activity_filters": {
        "avoid_tags": [],
        "prefer_tags": [],
        "required_tags": [],
    },
    "meal_requirements": {
        "must_include": [],
        "avoid_terms": [],
    },
    "destination_intent": {
        "styles": [],
        "landmarks": [],
        "preferred_types": [],
        "iconic_preference": False,
    },
}

CLUB_TERMS = ["club", "clubs", "nightclub", "nightclubs", "night_club", "nightlife"]
DESTINATION_STYLE_TERMS = {
    "big_city": ("big city", "big cities", "urban exploration", "dense downtown", "city energy"),
    "skyscrapers": ("skyscraper", "skyscrapers", "tall buildings", "high rises", "high-rises"),
    "skyline": ("skyline",),
    "architecture": ("architecture", "architectural"),
    "museums": ("museum", "museums", "gallery", "galleries"),
    "food_city": ("food city", "food halls", "restaurants", "culinary"),
    "nightlife_city": ("nightlife", "nightclubs", "clubs", "late-night"),
    "beach": ("beach", "beaches", "waterfront", "water"),
    "national_park": ("national park", "national parks", "wildlife", "hiking"),
    "theme_parks": ("theme park", "theme parks", "disney", "universal"),
    "mountains": ("mountain", "mountains", "ski", "skiing"),
    "small_town": ("small town", "small towns", "quaint town"),
    "scenic_drives": ("scenic drive", "scenic drives", "road trip"),
    "shopping": ("shopping", "boutiques", "markets"),
    "quiet_escape": ("quiet", "calm", "relaxed", "peaceful"),
}
STYLE_TO_TYPES = {
    "big_city": ["major_city"],
    "skyscrapers": ["major_city"],
    "skyline": ["major_city"],
    "beach": ["beach_town", "island"],
    "national_park": ["national_park"],
    "theme_parks": ["resort_town", "major_city"],
    "mountains": ["mountain_town", "national_park", "natural_area"],
    "small_town": ["town", "small_city"],
}
ICONIC_STYLE_TERMS = {"big_city", "skyscrapers", "skyline", "national_park", "beach", "theme_parks"}


def _decision(decision: str, reason: str) -> DecisionLogEntry:
    return DecisionLogEntry(
        node="extract_preference_constraints",
        decision=decision,
        reason=reason,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _message_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "".join(str(part.get("text", part)) if isinstance(part, dict) else str(part) for part in content)
    return str(content)


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    if not cleaned.startswith("{") and "{" in cleaned and "}" in cleaned:
        return cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]
    return cleaned


def _empty_constraints(state: TripState) -> dict:
    constraints = deepcopy(DEFAULT_CONSTRAINTS)
    constraints["raw_group_notes"] = str(state.get("group_notes") or "").strip()
    constraints["raw_member_notes"] = [
        {
            "member_id": member.get("member_id", ""),
            "name": member.get("name", ""),
            "notes": str(member.get("preference_notes") or "").strip(),
        }
        for member in state.get("members", [])
        if str(member.get("preference_notes") or "").strip()
    ]
    return constraints


def _has_notes(constraints: dict) -> bool:
    return bool(
        str(constraints.get("raw_group_notes") or "").strip()
        or any(str(entry.get("notes") or "").strip() for entry in constraints.get("raw_member_notes", []))
    )


def _dedupe_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _ensure_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _normalize_constraints(raw: Any, base: dict) -> dict:
    constraints = deepcopy(DEFAULT_CONSTRAINTS)
    constraints["raw_member_notes"] = base.get("raw_member_notes", [])
    constraints["raw_group_notes"] = base.get("raw_group_notes", "")
    if not isinstance(raw, dict):
        return constraints

    constraints["hard_constraints"] = [
        constraint for constraint in _ensure_list(raw.get("hard_constraints")) if isinstance(constraint, dict)
    ]
    constraints["soft_preferences"] = _ensure_list(raw.get("soft_preferences"))

    schedule = raw.get("schedule") if isinstance(raw.get("schedule"), dict) else {}
    constraints["schedule"] = {
        "avoid_early_mornings": bool(schedule.get("avoid_early_mornings", False)),
        "earliest_start_time": schedule.get("earliest_start_time"),
        "pace": str(schedule.get("pace") or "balanced").lower(),
    }

    activity_filters = raw.get("activity_filters") if isinstance(raw.get("activity_filters"), dict) else {}
    constraints["activity_filters"] = {
        "avoid_tags": _dedupe_strings(_ensure_list(activity_filters.get("avoid_tags"))),
        "prefer_tags": _dedupe_strings(_ensure_list(activity_filters.get("prefer_tags"))),
        "required_tags": _dedupe_strings(_ensure_list(activity_filters.get("required_tags"))),
    }

    meal_requirements = raw.get("meal_requirements") if isinstance(raw.get("meal_requirements"), dict) else {}
    constraints["meal_requirements"] = {
        "must_include": [
            item for item in _ensure_list(meal_requirements.get("must_include")) if isinstance(item, dict)
        ],
        "avoid_terms": _dedupe_strings(_ensure_list(meal_requirements.get("avoid_terms"))),
    }

    destination_intent = raw.get("destination_intent") if isinstance(raw.get("destination_intent"), dict) else {}
    constraints["destination_intent"] = {
        "styles": _dedupe_strings(_ensure_list(destination_intent.get("styles"))),
        "landmarks": _dedupe_strings(_ensure_list(destination_intent.get("landmarks"))),
        "preferred_types": _dedupe_strings(_ensure_list(destination_intent.get("preferred_types"))),
        "iconic_preference": bool(destination_intent.get("iconic_preference", False)),
    }
    return constraints


def _mentions_clubs(text: str) -> bool:
    return bool(
        re.search(
            r"\b(no|avoid|don'?t want|do not want|not into|hate|hates|skip)\b.{0,40}\b(club|clubs|nightclub|nightclubs)\b",
            text,
        )
        or re.search(
            r"\b(club|clubs|nightclub|nightclubs)\b.{0,40}\b(no|avoid|hate|hates|skip)\b",
            text,
        )
    )


def _mentions_early_morning_avoidance(text: str) -> bool:
    return bool(
        re.search(
            r"\b(no|avoid|don'?t want|do not want|hate|hates|skip|not)\b.{0,45}\b(early morning|early mornings|rushed mornings)\b",
            text,
        )
        or "sleep in" in text
    )


def _mentions_italian_requirement(text: str) -> bool:
    return "italian" in text and bool(
        re.search(r"\b(at least once|must|have to|need to|wants?|required)\b", text)
    )


def _mentions_relaxed_pace(text: str) -> bool:
    return any(term in text for term in ("relaxed", "not packed", "not overpacked", "slow pace", "chill"))


def _destination_intent_from_text(text: str) -> dict:
    styles: list[str] = []
    landmarks: list[str] = []
    preferred_types: list[str] = []

    for style, terms in DESTINATION_STYLE_TERMS.items():
        if any(term in text for term in terms):
            styles.append(style)
            preferred_types.extend(STYLE_TO_TYPES.get(style, []))

    if any(term in text for term in ("first time", "first-time", "iconic", "famous", "must-see", "classic")):
        styles.append("first_time")

    for landmark in ("skyscrapers", "skyline", "museums", "architecture", "beach", "national park"):
        if landmark in text:
            landmarks.append(landmark)

    styles = _dedupe_strings(styles)
    return {
        "styles": styles,
        "landmarks": _dedupe_strings(landmarks),
        "preferred_types": _dedupe_strings(preferred_types),
        "iconic_preference": bool(set(styles).intersection(ICONIC_STYLE_TERMS)),
    }


def _fallback_constraints(base: dict) -> dict:
    fallback = deepcopy(DEFAULT_CONSTRAINTS)
    fallback["raw_member_notes"] = base.get("raw_member_notes", [])
    fallback["raw_group_notes"] = base.get("raw_group_notes", "")

    entries = list(base.get("raw_member_notes", []))
    if base.get("raw_group_notes"):
        entries.append({"member_id": "group", "name": "Group", "notes": base.get("raw_group_notes", "")})

    intent_parts = []
    for entry in entries:
        source = entry.get("member_id") or entry.get("name") or "unknown"
        text = str(entry.get("notes") or "").lower()
        intent_parts.append(_destination_intent_from_text(text))

        if _mentions_clubs(text):
            fallback["hard_constraints"].append(
                {
                    "source": source,
                    "type": "avoid",
                    "applies_to": "activities",
                    "target": "nightlife",
                    "terms": CLUB_TERMS,
                    "text": entry.get("notes", ""),
                }
            )
            fallback["activity_filters"]["avoid_tags"].extend(["nightlife", "night_club", "club"])

        if _mentions_early_morning_avoidance(text):
            fallback["hard_constraints"].append(
                {
                    "source": source,
                    "type": "schedule",
                    "applies_to": "schedule",
                    "target": "earliest_start_time",
                    "terms": ["early morning", "early mornings"],
                    "text": entry.get("notes", ""),
                }
            )
            fallback["schedule"]["avoid_early_mornings"] = True
            fallback["schedule"]["earliest_start_time"] = "10:00"

        if _mentions_italian_requirement(text):
            fallback["hard_constraints"].append(
                {
                    "source": source,
                    "type": "must_include",
                    "applies_to": "meals",
                    "target": "italian",
                    "terms": ["italian"],
                    "text": entry.get("notes", ""),
                }
            )
            fallback["meal_requirements"]["must_include"].append(
                {"cuisine": "italian", "min_count": 1, "source": source}
            )

        if _mentions_relaxed_pace(text):
            fallback["schedule"]["pace"] = "relaxed"
            fallback["soft_preferences"].append(
                {
                    "source": source,
                    "type": "pace",
                    "target": "relaxed",
                    "text": entry.get("notes", ""),
                }
            )

    fallback["activity_filters"]["avoid_tags"] = _dedupe_strings(fallback["activity_filters"]["avoid_tags"])
    fallback["destination_intent"] = _merge_destination_intents(intent_parts)
    return fallback


def _merge_destination_intents(intents: list[dict]) -> dict:
    styles: list[str] = []
    landmarks: list[str] = []
    preferred_types: list[str] = []
    iconic_preference = False
    for intent in intents:
        styles.extend(intent.get("styles", []))
        landmarks.extend(intent.get("landmarks", []))
        preferred_types.extend(intent.get("preferred_types", []))
        iconic_preference = iconic_preference or bool(intent.get("iconic_preference"))
    styles = _dedupe_strings(styles)
    return {
        "styles": styles,
        "landmarks": _dedupe_strings(landmarks),
        "preferred_types": _dedupe_strings(preferred_types),
        "iconic_preference": iconic_preference or bool(set(styles).intersection(ICONIC_STYLE_TERMS)),
    }


def _merge_constraints(parsed: dict, fallback: dict) -> dict:
    merged = deepcopy(parsed)
    merged["hard_constraints"] = _dedupe_constraints(
        list(parsed.get("hard_constraints", [])) + list(fallback.get("hard_constraints", []))
    )
    merged["soft_preferences"] = list(parsed.get("soft_preferences", [])) + list(fallback.get("soft_preferences", []))

    parsed_schedule = parsed.get("schedule", {})
    fallback_schedule = fallback.get("schedule", {})
    if fallback_schedule.get("avoid_early_mornings"):
        parsed_schedule["avoid_early_mornings"] = True
        parsed_schedule["earliest_start_time"] = fallback_schedule.get("earliest_start_time", "10:00")
    if fallback_schedule.get("pace") != "balanced":
        parsed_schedule["pace"] = fallback_schedule.get("pace")
    merged["schedule"] = parsed_schedule

    for key in ("avoid_tags", "prefer_tags", "required_tags"):
        merged["activity_filters"][key] = _dedupe_strings(
            list(parsed.get("activity_filters", {}).get(key, []))
            + list(fallback.get("activity_filters", {}).get(key, []))
        )

    parsed_must = list(parsed.get("meal_requirements", {}).get("must_include", []))
    fallback_must = list(fallback.get("meal_requirements", {}).get("must_include", []))
    merged["meal_requirements"]["must_include"] = _dedupe_meal_requirements(parsed_must + fallback_must)
    merged["meal_requirements"]["avoid_terms"] = _dedupe_strings(
        list(parsed.get("meal_requirements", {}).get("avoid_terms", []))
        + list(fallback.get("meal_requirements", {}).get("avoid_terms", []))
    )
    merged["destination_intent"] = _merge_destination_intents(
        [
            parsed.get("destination_intent", {}),
            fallback.get("destination_intent", {}),
        ]
    )
    return merged


def _dedupe_constraints(constraints: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    result: list[dict] = []
    for constraint in constraints:
        key = (
            str(constraint.get("source", "")),
            str(constraint.get("type", "")),
            str(constraint.get("applies_to", "")),
            str(constraint.get("target", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(constraint)
    return result


def _dedupe_meal_requirements(requirements: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    result: list[dict] = []
    for requirement in requirements:
        cuisine = str(requirement.get("cuisine") or requirement.get("target") or "").strip().lower()
        if not cuisine:
            continue
        source = str(requirement.get("source") or "group")
        key = (source, cuisine)
        if key in seen:
            continue
        seen.add(key)
        try:
            min_count = int(requirement.get("min_count") or 1)
        except (TypeError, ValueError):
            min_count = 1
        result.append(
            {
                "cuisine": cuisine,
                "min_count": min_count,
                "source": source,
            }
        )
    return result


def _prompt(base: dict) -> str:
    return (
        "Extract group trip planning constraints from natural-language preference notes.\n"
        "Return ONLY raw JSON, no markdown, no backticks. Use this exact top-level shape:\n"
        "{raw_member_notes: list, raw_group_notes: string, hard_constraints: list, "
        "soft_preferences: list, schedule: object, activity_filters: object, "
        "meal_requirements: object, destination_intent: object}.\n"
        "Classify explicit must/avoid/timing requirements as hard_constraints. "
        "Classify general likes, vibes, and pacing as soft_preferences unless they are phrased as must/avoid.\n"
        "Use schedule.earliest_start_time as HH:MM when users avoid early mornings. "
        "Use activity_filters.avoid_tags for avoided activity categories. "
        "Use meal_requirements.must_include for cuisine or meal requirements. "
        "Use destination_intent.styles for destination-level intent like big_city, skyscrapers, skyline, "
        "architecture, museums, food_city, nightlife_city, beach, national_park, theme_parks, mountains, "
        "small_town, scenic_drives, shopping, quiet_escape. "
        "Use destination_intent.preferred_types for preferred destination types, and set "
        "destination_intent.iconic_preference true when users ask for iconic, famous, big-city, skyline, "
        "national-park, beach, or theme-park destinations.\n\n"
        f"Preference notes JSON:\n{json.dumps(base)}"
    )


async def extract_preference_constraints(state: TripState) -> dict:
    base = _empty_constraints(state)
    if not _has_notes(base):
        return {
            "preference_constraints": base,
            "constraint_satisfaction": {"passed": True, "satisfied": [], "unmet": [], "warnings": []},
            "decision_log": [_decision("No natural-language preferences supplied", "Using slider preferences only")],
        }

    fallback = _fallback_constraints(base)
    parsed = None
    llm_error = None
    try:
        response = await get_llm().ainvoke(_prompt(base))
        parsed = json.loads(_strip_json_fences(_message_text(response)))
    except Exception as exc:  # noqa: BLE001
        llm_error = str(exc)

    normalized = _normalize_constraints(parsed, base) if parsed is not None else _normalize_constraints(None, base)
    constraints = _merge_constraints(normalized, fallback)
    hard_count = len(constraints.get("hard_constraints", []))
    soft_count = len(constraints.get("soft_preferences", []))
    reason = f"{hard_count} hard constraints, {soft_count} soft preferences"
    if llm_error:
        reason += f"; LLM parse fallback used: {llm_error}"

    return {
        "preference_constraints": constraints,
        "constraint_satisfaction": {"passed": None, "satisfied": [], "unmet": [], "warnings": []},
        "decision_log": [_decision("Natural-language constraints extracted", reason)],
    }
