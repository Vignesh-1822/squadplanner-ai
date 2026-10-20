# Product feedback — from the Phase 1 calibration labelling

**Provenance.** Manoj hand-labelled 20 calibration itineraries (plus 3 blind repeats) on
2026-09-06 against the three Phase 1 rubrics, recording free-text reasoning on every rating.
This document extracts every distinct concern, idea and question from those 28,860 characters of
notes, checks each against the code, and gives it a stable handle so it can be planned against.

The labels themselves are `backend/evals/calibration/labels.json`. Confirmed defects are recorded
separately in [KNOWN_ISSUES.md](KNOWN_ISSUES.md) as K-006 through K-011; this file is the product
view — what the output should be, not only what is broken.

**Status vocabulary**

| Status | Meaning |
|---|---|
| Verified bug | Reproduced in code or fixture data. Has a K-number. |
| Gap | The product does not do this. Not a defect of an existing feature. |
| Feature | A new capability proposed in the notes. |
| Target state | An example of the output quality being aimed at. |

---

## The single mechanism behind most of the complaints

Most of the itinerary criticism traces to one defect and its collateral damage:

1. The hotel is geocoded to the wrong city. Destination "Surfside Beach" (Texas) books
   `2411 S Ocean Blvd, Myrtle Beach, SC` — the South Carolina Surfside Beach. Ten of the twenty
   calibration itineraries share that hotel; Newport's is 4,981 km from its destination.
2. Every day's first leg is hotel → first activity, so `total_travel_minutes` reaches ~30,000.
3. `check_feasibility` fires above 180 minutes per day. Its only remedy, `apply_feasibility_swap`,
   **deletes an activity** from the busiest day.
4. It is bounded at two attempts, then gives up and ships.

`apply_feasibility_swap` reaches its bound in **all 30 offline cases**. Every trip silently loses
two activities to a repair that cannot work, because the problem is not the activities — it is a
hotel 2,233 km away.

So "impossible walks", "only two activities per day", "no activity between lunch and dinner" and
"the trip is boring" are not four independent complaints. They are one bug and its consequences.
Fixing K-006 is the highest-leverage change available and should precede any judgement about
itinerary quality.

---

## A · Logistics

| # | Finding | Status |
|---|---|---|
| **F-01** | Hotel resolves to the wrong city/state. 14 of 20 itineraries contain a leg over 100 km. | Verified bug — [K-006](KNOWN_ISSUES.md) |
| **F-02** | Every route in every itinerary is `mode: WALK`. No transport mode is ever selected. Matagorda, where the hotel is correct, still shows a 166 km leg. | Verified bug — K-006 |
| **F-03** | Ask the user for the transport mode — own car, rental, rideshare, transit, walking only. Chicago read as acceptable partly because downtown walking is genuinely viable, so the default should also depend on the destination. | Feature |
| **F-04** | Travel time never constrains the schedule. `plan_routes` runs *after* `build_itinerary`, so the planner composes each day blind to distance; routing only reacts afterwards by deleting entries. | Gap — architectural |

> "I feel like we need to establish a mode of transport. Preferably asking the User if they will
> have a car or will they rent a car or Uber there or are they preferring only walks or public
> transports? Huge unanswered question and a serious flaw."

## B · The shape of a day

| # | Finding | Status |
|---|---|---|
| **F-05** | Breakfast missing. It is always present in `meals[]` — the prompt requires three — but inconsistently absent from `schedule[]`. Item 19 schedules it at 08:00; items 01 and 11 never do. `validation_gate` only checks `len(meals) == 3` and never checks the schedule contains them. | Verified bug — [K-010](KNOWN_ISSUES.md) |
| **F-06** | Days end too early (17:30–18:30 dinners); ~20:30–21:00 preferred. Applied consistently: an early end is acceptable when the day starts early. The real criterion is waking-day coverage, not clock time. | Gap |
| **F-07** | Dead gaps with nothing between lunch and dinner. | Consequence of F-01 / [K-007](KNOWN_ISSUES.md) |
| **F-08** | Two activities a day reads as boring — *except* where activities are long and tiring, where two is right. Density should be effort-aware, not a fixed count. | Gap |
| **F-09** | Fill genuine gaps with hotel downtime, group hangout or drinks where the group is up for it; a real activity is still preferable. | Feature |

## C · Activity quality

| # | Finding | Status |
|---|---|---|
| **F-10** | Repetitive scenic walks and viewpoints across every day. Does not capture the character of the destination. | Gap |
| **F-11** | Item 08 (Chicago) is the reference standard: museums, Starbucks Reserve Roastery, skyscrapers, stadiums, aquarium, shopping. Item 12's wine venues also praised for fitting the place. | Target state |
| **F-12** | Hypothesis that retrieval over Wikivoyage would improve this. Correct, and already Phase 3 on the roadmap. | Gap — Phase 3 |
| **F-13** | Repeating the same activity *type* across days is mundane. Variety within a trip matters, not only quality per item. | Gap |

> "Where's fun activities and attractions being included here? Relaxing walks with views are taking
> precedence a lot and its kind of making days boring."

## D · Cost realism

| # | Finding | Status |
|---|---|---|
| **F-14** | Asked repeatedly how activity costs are estimated. **The planner invents them.** `subgraphs/itinerary.py` instructs the model to output "a realistic estimate per person multiplied by number of members". Nothing verifies it. | Verified bug — [K-011](KNOWN_ISSUES.md) |
| **F-15** | `budget_analyzer.py` separately uses a flat `$50 × members × days` for the budget decision — a different number from the per-day one, never reconciled. | Verified bug — K-011 |
| **F-16** | Google Places returns `price_level` for every venue. It is stored in state and used in zero cost calculations. Real signal, discarded. | Verified bug — K-011 |
| **F-17** | Hotel cost for 8 members. `total_price_usd = price_per_night × nights` is one room, then fairness divides by `len(members)`. Eight people share one room's price. No room-count math exists. | Verified bug — [K-008](KNOWN_ISSUES.md) |
| **F-18** | Budget under-utilization — repeated across ~12 items. "People still have a lot left and budget means to use them sometimes." Treated as a quality issue, not a constraint violation. Absent from the fairness rubric. | Gap |
| **F-19** | Over-budget outcomes scored harshly (items 10, 14, 24). Already captured by the Phase 1 budget-compliance scorer. | Covered |

## E · Deciding versus asking

The largest product idea in the notes, and the least specified.

| # | Finding | Status |
|---|---|---|
| **F-20** | The planner silently decides things the user never specified: whether a convenience-store breakfast is acceptable, whether a rental car is fine, when the day should end, who wins when two members conflict. Users cannot state all of this upfront. | Feature |
| **F-21** | Ask clarifying questions the way coding agents do, with the reasoning shown. | Feature |
| **F-22** | Stated tension: too many questions annoys people. Some users want to resolve every conflict; others want a fast first draft to refine later. | Design constraint |
| **F-23** | Proposed resolution: make it a user preference — an interactive mode versus a fast-draft mode. | Feature |
| **F-24** | Item 03: a member asked for no early mornings and every day starts at 08:00. A stated preference was silently dropped. | Needs investigation |
| **F-25** | "We need to start getting more details from the user. Seems insufficient to cater to the person." | Feature — same family as F-20 |

> "Users cannot possibly tell all their preferences... But I am also in a dilemma because, at what
> point would the user gets pissed off at getting prompted to resolve so many conflicts? ... Maybe
> it could be a preference feature?"

## F · The trip pitch

| # | Finding | Status |
|---|---|---|
| **F-26** | Dense, hard to read, not exciting. Wants paragraphs, headings, day-by-day structure. Recorded on all 23 label records, which is why every pitch scored exactly 3 — the rubric grades groundedness, not presentation, so the objection had nowhere to land. | Gap |

## G · Meta — the measurement itself

| # | Finding | Status |
|---|---|---|
| **F-27** | "The test prompts are all bad. Doesn't seem realistic enough. The user's constraints doesn't seem to match the tourist spot chosen." The eval dataset's inputs need review. | Gap — eval quality |
| **F-28** | The geographic scorer reported 96.7% pass on data containing 2,233 km legs, because it measures only activity→activity distance and never the hotel anchor leg. | Verified bug — [K-009](KNOWN_ISSUES.md) |
| **F-29** | Across all three criteria the rubrics measure a narrower thing than was actually graded: coherence missed "is it interesting", fairness missed under-utilization, pitch missed presentation. Rubric v2 must close this before the next calibration cycle. | Gap — see below |

---

## Rubric implications

The labelling exercise showed the rubrics capture a subset of the real quality bar:

| Criterion | What the rubric measures | What was actually graded |
|---|---|---|
| Itinerary coherence | Practicality: walk legs, meal windows, overlaps, pace | That, **plus how interesting the trip is**. Item 08 scored 4 despite a 221-minute walking leg, which the rubric calls a major problem, because the activity mix was strong. |
| Fairness across members | Budget compliance, dietary coverage, hard avoids, top-2 preference coverage, utilization spread | That, **plus under-utilization** (F-18), which appears nowhere in the rubric. |
| Trip-pitch quality | Groundedness: does it cite scheduled venues and member priorities | **Presentation** (F-26) — density, structure, whether it is exciting. Not in the rubric at all. |

This is the direct cause of two measurement problems recorded in the Phase 1 baseline: zero
variance on trip-pitch quality, and inconsistent intra-rater scoring on fairness where the two
passes applied a broad and then a narrow reading of the same word.

Rubric v1 is frozen as the version the committed labels were made against. Rubric v2 should be
written together with the roadmap revision, because a rubric anchor is a product requirement in
different clothing — "5: every travel leg uses a transport mode appropriate to its distance" is
F-03, and "5: every day schedules breakfast, lunch and dinner as timed entries" is F-05.

---

## Coverage against the current roadmap

Checked against [ROADMAP.md](ROADMAP.md) as of 2026-09-07.

| Roadmap phase | Findings it covers |
|---|---|
| Phase 2 — Harden the model boundary | F-05 partially, via the venue-validity and output-guardrail items |
| Phase 3 — Ground it (RAG) | F-10, F-11, F-12, F-13 |
| Phase 4 — Genuinely multi-agent | F-24 partially, via "log every objection" |
| Phase 7 — Product | F-20 adjacently, via group voting at the HITL pause |

**Not covered anywhere:** F-01, F-02, F-03, F-04, F-06, F-07, F-08, F-09, F-14, F-15, F-16, F-17,
F-18, F-21, F-22, F-23, F-25, F-26, F-27.

That is nineteen of twenty-nine findings, including every one of the logistics and cost defects
that make the current output unusable. Executed as written, the roadmap would deliver a
well-engineered, well-observed, retrieval-grounded system that still produces itineraries a human
rater scores 1 or 2. Revising the roadmap to close this gap is the next planning task.
