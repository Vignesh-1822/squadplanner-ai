# SquadPlanner Destinations Database — Generation Prompts
# Model: ChatGPT-5 (standard, no reasoning/thinking mode)
# Process: 1 setup message + 5 batch messages + 1 validation message = 7 total messages
# Expected output: ~500 destinations with metadata + 5D vibe vectors


# ============================================================================
# MESSAGE 1: SETUP (send this first)
# ============================================================================

I'm building a trip planning app. I need a database of ~500 US tourist destinations in JSON format. For each destination, I need metadata AND a 5-dimensional vibe vector.

Here's the exact schema for each entry:

```json
{
  "id": "snake_case_unique_id",
  "name": "Destination Name",
  "type": "major_city | small_city | town | resort_town | beach_town | mountain_town | national_park | state_park | natural_area | island",
  "state": "XX",
  "nearest_airports": [
    {"code": "XXX", "name": "Airport Name", "drive_min": 0}
  ],
  "lat": 00.000,
  "lng": -00.000,
  "search_radius_km": 15,
  "cost_level": "low | medium | high",
  "best_for": ["keyword1", "keyword2", "keyword3"],
  "notes": "",
  "vibe_tags": {
    "nightlife": 0.000,
    "adventure": 0.000,
    "shopping": 0.000,
    "food": 0.000,
    "urban": 0.000
  }
}
```

FIELD RULES:
- id: unique snake_case. Add state suffix if ambiguous (portland_or, portland_me)
- type: most specific fit from the enum above
- nearest_airports: 1-3 airports, real IATA codes, realistic drive times in minutes
- lat/lng: accurate coordinates for destination center or park main entrance
- search_radius_km: 15-25 for cities, 10-15 for towns, 30-80 for national parks
- cost_level: low (budget-friendly), medium (moderate), high (expensive)
- best_for: 3-6 tourist keywords
- notes: critical logistics only ("requires car rental", "seasonal closure Nov-Mar", etc). Empty string if none.
- vibe_tags: 5 scores that MUST sum to exactly 1.000

VIBE VECTOR RUBRIC — score each dimension 0.0-1.0 RAW, then normalize to sum to 1.0:

NIGHTLIFE:
  0.9-1.0 = internationally famous (Vegas, Miami Beach, New Orleans, Nashville Broadway)
  0.7-0.8 = major scene (NYC, LA, Austin 6th St, Scottsdale)
  0.5-0.6 = good but not the draw (Denver, Portland, Memphis)
  0.3-0.4 = limited options (Asheville, Santa Fe, small towns)
  0.1-0.2 = very quiet (park gateway towns, rural areas)
  0.0 = nothing (remote wilderness)

ADVENTURE/OUTDOORS:
  0.9-1.0 = destination IS the outdoors (Yellowstone, Yosemite, Grand Canyon, Zion)
  0.7-0.8 = primary draw is nature (Jackson Hole, Maui, Sedona, Lake Tahoe)
  0.5-0.6 = strong outdoor component (Denver, San Diego, Asheville)
  0.3-0.4 = some parks/beaches (Nashville, Savannah, most mid-cities)
  0.1-0.2 = minimal (NYC, Chicago, Vegas)
  0.0 = none

SHOPPING:
  0.9-1.0 = world-class shopping destination (NYC 5th Ave/SoHo, LA Rodeo Drive)
  0.7-0.8 = excellent, significant tourist activity (Miami, Chicago Mag Mile)
  0.5-0.6 = notable districts/markets (Charleston King St, Nashville, Santa Fe)
  0.3-0.4 = decent but not a draw (Denver, Portland, Austin)
  0.1-0.2 = basic retail only (small towns, park areas)
  0.0 = none

FOOD:
  0.9-1.0 = culinary pilgrimage (New Orleans, NYC, SF, Charleston)
  0.7-0.8 = excellent scene, major draw (Austin, Portland OR, Chicago, Philly)
  0.5-0.6 = good restaurants, some local cuisine (Denver, San Diego, Memphis, Honolulu)
  0.3-0.4 = adequate dining (most mid-cities, ski towns)
  0.1-0.2 = limited options (national park areas, remote towns)
  0.0 = none

URBAN/CULTURE:
  0.9-1.0 = world-class museums/landmarks (NYC, DC Smithsonian, Chicago)
  0.7-0.8 = rich cultural scene (Philadelphia, Boston, SF, New Orleans, Savannah)
  0.5-0.6 = good cultural offerings (Nashville, Austin, Denver, Santa Fe)
  0.3-0.4 = some museums/history (most small cities, beach towns with history)
  0.1-0.2 = minimal (beach resorts, ski towns, small mountain towns)
  0.0 = none (remote wilderness)

CRITICAL:
- Normalize so all 5 vibe_tags sum to exactly 1.000
- National parks: adventure should almost always dominate
- Don't let food be the top dimension for every city — only where the food scene is genuinely a tourist draw
- Similar destinations should have similar vectors (Zion ≈ Grand Canyon, Nashville ≈ Austin)
- Major cities should be more balanced (no single dim > 0.35), parks should be heavily skewed to adventure

I'll request destinations in batches of 100. Return ONLY the raw JSON array each time — no explanations, no markdown code fences, just the JSON. Ready?


# ============================================================================
# MESSAGE 2: BATCH 1 — Major Cities + Small Cities (100 destinations)
# ============================================================================

BATCH 1: Generate 100 US city destinations.

First 50: Major cities that are significant tourist destinations. Include all the obvious ones (NYC, LA, Miami, Chicago, SF, Seattle, DC, Boston, etc.) plus cities with meaningful tourism (Memphis, Milwaukee, Pittsburgh, San Antonio, Albuquerque, etc.)

Next 50: Smaller cities and culturally significant towns popular with tourists. Think Savannah, Charleston, Asheville, Santa Fe, Sedona, Napa, St. Augustine, Annapolis, Newport RI, Fredericksburg TX, Taos, Mystic CT, Carmel, etc.

Return as one JSON array of 100 objects with the full schema including vibe_tags. No duplicates.


# ============================================================================
# MESSAGE 3: BATCH 2 — National Parks + Natural Attractions (100 destinations)
# ============================================================================

BATCH 2: Generate 100 national parks, state parks, and natural attraction destinations.

Include:
- All major National Parks people travel to visit (Yellowstone, Yosemite, Grand Canyon, Zion, Glacier, Acadia, Rocky Mountain, Great Smoky Mountains, Olympic, Denali, Arches, Bryce Canyon, Joshua Tree, Everglades, Shenandoah, Big Bend, Canyonlands, Death Valley, Sequoia, Crater Lake, Badlands, Mesa Verde, Carlsbad Caverns, Mammoth Cave, Guadalupe Mountains, Capitol Reef, etc.)
- Notable National Monuments and Seashores (White Sands, Monument Valley, Devils Tower, Cape Hatteras, Sleeping Bear Dunes, etc.)
- Major natural attractions (Niagara Falls, Finger Lakes, Lake Powell, Flaming Gorge, etc.)
- Notable state parks worth traveling for

For each: nearest_airports should list 2-3 options with realistic drive times. search_radius_km should be 30-80 for large parks.

No duplicates with Batch 1. Return JSON array of 100 objects with full schema.


# ============================================================================
# MESSAGE 4: BATCH 3 — Beach, Coastal + Island Destinations (100 destinations)
# ============================================================================

BATCH 3: Generate 100 beach, coastal, and island destinations.

Cover all US coastal regions:
- Florida: Clearwater, Destin, Panama City Beach, Anna Maria Island, Amelia Island, Sanibel, Naples, Siesta Key, Marco Island, etc.
- Hawaii: Maui, Big Island, Kauai, Oahu (each as separate destinations), plus specific areas if notable
- California coast: Monterey, Carmel, Santa Cruz, Laguna Beach, Santa Barbara, Malibu, Half Moon Bay, etc.
- Southeast: Hilton Head, Outer Banks, Tybee Island, Gulf Shores, Orange Beach, Kiawah Island, Jekyll Island, etc.
- Northeast: Cape Cod, Martha's Vineyard, Nantucket, Bar Harbor, Hamptons, Block Island, Newport Beach, Cape May, Rehoboth Beach, etc.
- Pacific NW: Cannon Beach, San Juan Islands, Whidbey Island, Long Beach WA, etc.
- Texas/Gulf: South Padre, Galveston, Port Aransas, Destin, Pensacola Beach, etc.
- US Islands: Catalina Island, Mackinac Island, US Virgin Islands, Puerto Rico (if you want to include territories)

No duplicates with Batches 1-2. Return JSON array of 100 objects with full schema.


# ============================================================================
# MESSAGE 5: BATCH 4 — Mountain, Ski, Adventure + Themed Destinations (100 destinations)
# ============================================================================

BATCH 4: Generate 100 destinations covering mountain/ski/adventure towns AND unique themed destinations.

First ~60 — Mountain & Outdoor Adventure:
- Colorado: Aspen, Vail, Telluride, Breckenridge, Steamboat Springs, Durango, Estes Park, Crested Butte, Ouray, Glenwood Springs, etc.
- Utah: Moab, Park City, Springdale, Kanab, Brian Head, etc.
- Wyoming/Montana: Jackson Hole, Big Sky, Whitefish, Cody, Red Lodge, etc.
- Pacific NW: Bend OR, Leavenworth WA, Mt Hood area, Sun Valley ID, etc.
- Northeast: Stowe VT, Lake Placid NY, White Mountains NH, Killington, North Conway, etc.
- Southeast mountains: Gatlinburg, Pigeon Forge, Blue Ridge GA, Highlands NC, Helen GA, etc.
- California mountains: Lake Tahoe (if not already covered), Mammoth Lakes, Big Bear, Mt Shasta, etc.

Next ~40 — Unique/Themed:
- Wine country: Napa, Sonoma, Willamette Valley, Walla Walla, Finger Lakes wine trail, Texas Hill Country, etc.
- Casino/entertainment: Las Vegas (if not in Batch 1), Atlantic City, Biloxi, Reno, etc.
- Theme parks: Orlando area, Anaheim area, Branson, Wisconsin Dells, Hershey PA, etc.
- Historical: Gettysburg, Plymouth, Colonial Williamsburg, Tombstone AZ, Dodge City, etc.
- Quirky/unique: Marfa TX, Roswell NM, Leavenworth WA (Bavarian village), Helen GA, Solvang CA, etc.
- Lake destinations: Door County WI, Lake George NY, Lake Chelan WA, Coeur d'Alene ID, Put-in-Bay OH, etc.

No duplicates with Batches 1-3. Return JSON array of 100 objects with full schema.


# ============================================================================
# MESSAGE 6: BATCH 5 — Gap Fill (remaining destinations to reach ~500)
# ============================================================================

BATCH 5: Generate 100 more destinations to fill gaps.

Looking at Batches 1-4, fill these gaps:
1. Any MAJOR tourist destinations we somehow missed
2. US states with fewer than 3 entries — add destinations to underrepresented states
3. Road trip stops and scenic byway towns we missed
4. Desert destinations (beyond what's covered): White Sands area towns, Palm Desert, Death Valley gateway, etc.
5. Emerging/trending destinations popular in the last 5 years
6. College towns that attract visitors (beyond football): Ann Arbor, Boulder, Madison, Athens GA, etc.
7. Any iconic American destinations that don't fit other categories

Prioritize places real tourists actually visit. No duplicates with Batches 1-4.

Return JSON array of 100 objects with full schema.


# ============================================================================
# MESSAGE 7: VALIDATION (send after all 5 batches)
# ============================================================================

Review all ~500 destinations we've generated across Batches 1-5 and check:

1. DUPLICATES: List any destination that appears in more than one batch (same place, possibly different ID or slight name variation)

2. VIBE VECTOR SANITY:
   - Any national park where adventure is NOT the dominant dimension?
   - Any famous nightlife city (Vegas, Miami, Nashville, NOLA) where nightlife is below 0.20?
   - Any famous food city (NOLA, NYC, SF, Charleston) where food is below 0.15?
   - Any destination where all 5 dimensions are nearly equal (~0.20 each)?
   - Is food the top dimension for more than 40% of city-type destinations? If so, which ones should be recalibrated?

3. CONSISTENCY: Find pairs of similar destinations with very different vectors. Examples to check:
   - Zion vs Grand Canyon vs Arches (should all be adventure-dominant)
   - Nashville vs Austin (similar vibes, should have similar vectors)
   - Aspen vs Vail vs Telluride (all ski/mountain towns)
   - Savannah vs Charleston (similar charming Southern cities)

4. GEOGRAPHIC COVERAGE: List any US states with fewer than 2 entries

5. MISSING ICONS: Any truly iconic destinations we missed entirely?

For each issue, provide the corrected entry or entries as JSON objects I can use to replace the originals.
