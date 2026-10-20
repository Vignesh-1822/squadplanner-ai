# Known Issues

Findings recorded while measuring the current product. Phase 1 does not repair
product behaviour; its baseline intentionally makes these defects visible.

## K-001 — Severe-budget retries duplicate flights and activities

`TripState.flights` and `TripState.activities` use additive reducers. A severe
budget result loops back through destination selection and data fetching without
clearing the prior destination's values, so both sets remain in state. Budget,
fairness and itinerary calculations then consume duplicated data.

Offline budget-retry cases preserve this behaviour as the Phase 1 baseline.

## K-002 — Flight searches pass a city name as `arrival_id`

`parallel_data_fetch` passes `selected_destination` (for example,
`"New York City"`) into `search_flights`. SerpAPI's Google Flights engine
requires an uppercase three-letter airport code or a Google location ID and
returns HTTP 400. Production therefore degrades every flight to the fixed $300
estimate.

The Phase 1 baseline records this estimated flight response as an explicit,
labelled exception to the general anti-fallback fixture rule. Fixing the airport
mapping belongs to a later behaviour-changing phase.

## K-003 — HTTP exception text exposed the SerpAPI query URL

The safe SerpAPI response logger omitted the API key, but the outer exception
handler subsequently logged `HTTPStatusError.__str__`, whose request URL
contained the query-string key. Phase 1 changed that outer log to emit only the
HTTP status. This is a security-only logging correction, not product behaviour.

The SerpAPI key that appeared in development output should be rotated.

## K-004 — Production SSE handles only one city-selection pause

The severe-budget route can return to destination selection and interrupt for a
second city choice. The production SSE helper resumes once and then returns to
its caller without looping over a second interrupt, so the stream can end while
the graph remains paused. The evaluation runner does loop until completion and
therefore measures the graph itself correctly. Repairing the product stream is
behaviour-changing and remains out of Phase 1.

## K-005 — Flight schema cannot support arrival-alignment scoring

`FlightResult.depart_time` is the outbound departure from the member's origin,
while `return_time` is populated from the final leg's arrival. The state does
not retain destination arrival or return departure timestamps. The Phase 1
alignment scorer therefore marks estimated or legacy-schema flights
`scorable: false` instead of presenting a misleading pass/fail result.

---

Issues K-006 onward were found by hand-labelling 20 generated itineraries during the Phase 1
calibration handoff. Every automated scorer passed the data that contains them. The product view
of the same exercise is in [PRODUCT_FEEDBACK.md](PRODUCT_FEEDBACK.md).

## K-006 — Hotel search resolves an ambiguous city name to the wrong state

`search_hotels` queries SerpAPI with `q = f"hotels in {destination}"` where `destination` is a bare
city name. Google Hotels resolves "Surfside Beach" to the South Carolina town near Myrtle Beach
rather than the Texas one the graph selected, so the trip books a hotel roughly 2,233 km from its
own destination. Ten of the twenty calibration itineraries share that Myrtle Beach hotel; the
Newport case is 4,981 km out. Fourteen of twenty contain a leg over 100 km.

`search_hotels` already receives `coords=state["selected_destination_coords"]`, but those
coordinates are passed only to the downstream Places enrichment and never constrain the hotel
query itself. This is the same defect family as K-002: an ambiguous place name handed to an
external API with no disambiguation.

Consequences reach further than the hotel — see K-007.

## K-007 — The feasibility loop deletes activities and can never succeed

`check_feasibility` routes to `apply_feasibility_swap` when any day exceeds 180 total travel
minutes. That node's only remedy is to **delete an activity** from the most travel-heavy day, and
the loop is bounded at two attempts before it gives up and ships.

Because K-006 puts the hotel thousands of kilometres away, the first leg of every day dominates the
day's travel time and no amount of activity deletion can bring it under the threshold. Counting the
recorded event artifacts, `apply_feasibility_swap` reaches its bound in **all 30 offline cases**.
Every generated trip therefore loses two activities to a repair that cannot work, and still ships
with the original travel problem.

This is the mechanism behind the sparse days, the empty afternoons between lunch and dinner, and
much of the "boring" quality judgement recorded during labelling. It is a real defect independent
of K-006 — a repair loop whose remedy does not address the failure it detects should stop and
report rather than silently degrade the plan.

## K-008 — Hotel cost is one room's price divided across the whole group

`search_hotels` sets `total_price_usd = price_per_night × nights`, which is the price of a single
room. `compute_fairness` then divides that by `len(members)`. An eight-person group is therefore
charged one room split eight ways. No room-count calculation exists anywhere in the graph, and
group size never affects lodging cost.

## K-009 — The geographic scorer never checks the hotel anchor leg

`geographic_plausibility` measures the haversine distance between consecutive *activities* only. The
hotel is `route_stops` order 1 and is never one of the pair, so the hotel → first-activity leg is
invisible to it. The scorer reported a 96.7% pass rate on data whose first leg every day is 2,233 km.

The Phase 1 baseline records that pass rate as measured. It is accurate about what the scorer
checks and misleading about what it implies, which is why the finding is recorded here rather than
silently corrected.

## K-010 — Breakfast is required in `meals[]` but never required in `schedule[]`

The itinerary prompt requires exactly three meal strings per day and `validation_gate` enforces
`len(meals) == 3`. Nothing requires those meals to appear as timed entries in `schedule[]`, and the
model is inconsistent: case 19 schedules breakfast at 08:00 on every day, while cases 01 and 11
never schedule it at all despite listing it in `meals[]`.

The rendered day therefore begins at lunch, and no validator can detect it because the check counts
strings in a different field from the one the user reads.

## K-011 — Two unreconciled cost models, and real price data is discarded

Three separate things claim to represent activity cost:

- `budget_analyzer.py` uses a flat `$50 × members × days` to decide budget status and to route the
  severe-budget retry.
- `estimated_day_cost_usd` is produced by the planner LLM, instructed only to output "a realistic
  estimate per person multiplied by number of members". Nothing validates it against anything.
- Google Places returns `price_level` for every venue. It is stored in `ActivityResult` and used in
  **zero** cost calculations.

The number the user sees and the number the budget decision uses are unrelated, and the only real
price signal the system fetches is ignored by both.
