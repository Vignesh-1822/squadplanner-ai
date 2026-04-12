# Destinations Database — Data Documentation

## Overview

`destinations_db.json` is the core destination database for SquadPlanner. It contains ~500 US tourist destinations with metadata and 5-dimensional vibe vectors used by the destination-selection algorithm to match group preferences to the best trip destination.

**This file is checked into the repo and is required at runtime.**

---

## How This Data Was Created

### Method: LLM-Generated with Structured Rubric

The database was generated using ChatGPT-5 in a single interactive session, following a structured rubric to ensure consistency and accuracy.

**Why LLM-generated instead of API-sourced:**
- Google Places API would cost ~$300+ to bootstrap 500 destinations
- LLM generation is free (chat interface) and produces comparable quality for this use case
- The rubric constrains the LLM's judgments to explicit, auditable criteria
- Results were validated for consistency, normalization, and sanity in a final review pass

**Why not the Yelp Academic Dataset (original approach):**
- Yelp dataset only covers ~30 US cities, missing most major tourist destinations
- Static CSV couldn't be extended without re-downloading and reprocessing
- Limited to cities in the dataset — no national parks, beach towns, mountain destinations

### Generation Process

**Tool:** ChatGPT-5 (standard mode, no reasoning/thinking enabled)  
**Session:** Single conversation, 7 messages total  
**Date generated:** [INSERT DATE]  
**Prompts used:** See `data/prompts/destinations_generation_prompts.md`

**Batch structure:**
| Batch | Category | Count |
|-------|----------|-------|
| 1 | Major cities + small cities/towns | 100 |
| 2 | National parks + natural attractions | 100 |
| 3 | Beach, coastal, island destinations | 100 |
| 4 | Mountain/ski/adventure + themed/unique | 100 |
| 5 | Gap-fill (underrepresented states, missing icons) | 100 |
| — | Validation pass: duplicates removed, vectors corrected | — |
| **Total** | **After deduplication** | **~500** |

### Validation Steps Performed
1. **Duplicate check** — removed entries appearing in multiple batches
2. **Vibe vector sanity check** — verified national parks are adventure-dominant, nightlife cities have high nightlife scores, etc.
3. **Consistency check** — confirmed similar destinations have similar vectors (e.g., Zion ≈ Grand Canyon, Nashville ≈ Austin)
4. **Normalization check** — confirmed all vibe_tags sum to 1.000 (±0.002)
5. **Geographic coverage check** — ensured every US state has at least 2 entries
6. **Food-bias check** — verified food isn't the top dimension for >40% of city destinations

---

## Schema

```json
{
  "id": "yellowstone_np",
  "name": "Yellowstone National Park",
  "type": "national_park",
  "state": "WY",
  "nearest_airports": [
    {"code": "WYS", "name": "West Yellowstone", "drive_min": 10},
    {"code": "BZN", "name": "Bozeman", "drive_min": 90},
    {"code": "JAC", "name": "Jackson Hole", "drive_min": 120}
  ],
  "lat": 44.428,
  "lng": -110.588,
  "search_radius_km": 50,
  "cost_level": "medium",
  "best_for": ["nature", "hiking", "wildlife", "geysers", "photography"],
  "notes": "Requires car rental. Book lodging months in advance for summer.",
  "vibe_tags": {
    "nightlife": 0.000,
    "adventure": 0.769,
    "shopping": 0.000,
    "food": 0.077,
    "urban": 0.154
  }
}
```

### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique snake_case identifier. State suffix added for ambiguous names (e.g., `portland_or`) |
| `name` | string | Official destination name as commonly known |
| `type` | enum | One of: `major_city`, `small_city`, `town`, `resort_town`, `beach_town`, `mountain_town`, `national_park`, `state_park`, `natural_area`, `island` |
| `state` | string | 2-letter US state code |
| `nearest_airports` | array | 1-3 airports with IATA code, name, and driving time in minutes |
| `lat` | float | Latitude of destination center |
| `lng` | float | Longitude of destination center |
| `search_radius_km` | int | Radius for activity search. Cities: 15-25, Towns: 10-15, Parks: 30-80 |
| `cost_level` | enum | `low`, `medium`, or `high` — general cost of visiting |
| `best_for` | array | 3-6 keywords describing tourist appeal |
| `notes` | string | Critical logistics (car rental, seasonal, booking lead time). Empty string if none |
| `vibe_tags` | object | 5D vector, values sum to 1.000. See Vibe Vector section below |

### Vibe Vector (vibe_tags)

Five dimensions representing what tourists go to this destination for:

| Dimension | What it captures |
|-----------|-----------------|
| `nightlife` | Bars, clubs, live music, cocktail scene, late-night entertainment |
| `adventure` | Outdoor activities, hiking, beaches, water sports, skiing, nature, wildlife, zoos |
| `shopping` | Retail districts, malls, markets, boutiques, outlets |
| `food` | Restaurant scene, food culture, culinary tourism, local cuisine |
| `urban` | Museums, galleries, historical landmarks, theaters, cultural institutions |

**Scoring was done using a rubric with explicit anchoring examples:**
- 0.9-1.0 = internationally famous for this dimension
- 0.7-0.8 = major draw, significant tourist activity
- 0.5-0.6 = good options but not the primary reason to visit
- 0.3-0.4 = some options, limited
- 0.1-0.2 = very limited
- 0.0 = nonexistent

Raw scores were assigned per dimension, then normalized to sum to 1.0.

**Design principle:** The vector reflects what **tourists** visit for, not what exists there. Every big city has restaurants, but `food` is only scored high when the food scene is genuinely a tourist draw (e.g., New Orleans, NYC).

---

## How the Data Is Used

### Destination Selection Algorithm (`choose_destination_tool`)
1. Each traveler's preference weights (nightlife, adventure, shopping, food, urban) are normalized to sum to 1.0
2. Group weights = average of all travelers' normalized weights
3. For each destination: `vibe_score = dot_product(destination.vibe_tags, group_weights)`
4. Cost penalty applied: `combined_score = vibe_score / (1 + λ × cost_index)`
5. Destinations ranked by combined_score; top result recommended

### Activity Fetching
After a destination is chosen, `search_radius_km` and `lat/lng` are used to query Google Places API for activities within that radius. The `nearest_airports` field is used by the flight search tool.

---

## How to Update This Data

### Adding New Destinations
1. Add entries to `destinations_db.json` following the schema above
2. Assign vibe_tags using the rubric (raw scores → normalize to sum to 1.0)
3. Verify airport codes are real IATA codes
4. Verify coordinates by spot-checking on Google Maps
5. Run the validation script: `python scripts/validate_destinations.py` (if available)

### Correcting Vibe Vectors
If a destination's recommendations feel off (e.g., Denver being suggested for shopping trips), adjust its vibe_tags:
1. Re-score using the rubric anchors above
2. Normalize to sum to 1.0
3. Test by running the destination selection with a group profile that should/shouldn't match

### Future: Data-Grounded Vectors
The LLM-generated vectors can be validated and potentially replaced with data-grounded vectors computed from Google Places API review counts. The approach:
1. For each destination, search Google Places for top results in each of the 5 categories
2. Sum review counts per category as a "prominence" signal
3. Normalize prominence scores to get the vibe vector
4. Compare with current LLM-generated vectors and investigate divergences

This would cost ~$50-80 in API calls for 500 destinations and would provide empirically grounded vectors. See `SQUADPLANNER_CURSOR_CONTEXT.md` for detailed algorithm.

---

## Known Limitations

1. **Vibe vectors are LLM-estimated, not data-grounded** — They're based on the LLM's training data about each destination, not on measured tourist behavior. Generally accurate for well-known destinations, less reliable for obscure ones.

2. **Static data** — The database doesn't automatically update. New destinations, changing tourism patterns, or airport changes require manual updates.

3. **US-only** — Currently limited to US destinations. International expansion would require the same generation process for other countries.

4. **Cost level is coarse** — Only three tiers (low/medium/high). Doesn't capture seasonal variation (e.g., Aspen is "high" in winter, "medium" in summer) or specific price ranges.

5. **Airport drive times are estimates** — Generated by LLM, not computed from a routing API. May be off by 10-20 minutes in some cases.
