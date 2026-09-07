/**
 * Mirrors NODE_PROGRESS_MAP in backend/utils/streaming.py, in the order the graph runs them.
 *
 * The backend emits NODE_PROGRESS on node *start*, so the newest message is the step currently
 * running and everything before it has finished.
 */
export const PLANNING_STEPS = [
  { node: "parse_input", label: "Validating trip details..." },
  { node: "extract_preference_constraints", label: "Reading natural-language preferences..." },
  { node: "select_destination", label: "Scoring destinations for your group..." },
  { node: "city_selection_hitl", label: "Waiting for city selection..." },
  { node: "dynamic_tool_selection", label: "Selecting data sources based on group preferences..." },
  { node: "parallel_data_fetch", label: "Fetching flights, activities, and weather..." },
  { node: "budget_analysis", label: "Analysing group budget..." },
  { node: "search_hotel", label: "Finding hotels within budget..." },
  { node: "run_itinerary_node", label: "Building the detailed itinerary..." },
  { node: "cluster_by_neighborhood", label: "Grouping activities by neighbourhood..." },
  { node: "build_itinerary", label: "Building your itinerary..." },
  { node: "align_flight_times", label: "Aligning schedule with flight times..." },
  { node: "plan_routes", label: "Planning routes between activities..." },
  { node: "validation_gate", label: "Validating itinerary..." },
  { node: "compute_fairness", label: "Checking cost fairness across the group..." },
  { node: "assemble_output", label: "Writing your trip pitch..." },
]

/** How many rows the feed shows at once. Older steps fade out past the top edge. */
export const FEED_WINDOW = 4

/**
 * Furthest step reached, and the percentage that implies.
 *
 * Deliberately monotonic. The graph loops back to destination selection under severe budget
 * pressure and retries the hotel on fairness failure, and a bar that jumps backwards reads as
 * a bug rather than as progress. It can stall during a retry, which is the honest trade.
 */
export function planningProgress(nodeEvents) {
  let furthest = -1
  for (const event of nodeEvents) {
    const index = PLANNING_STEPS.findIndex((step) => step.node === event?.data?.node)
    if (index > furthest) furthest = index
  }
  const percent = furthest < 0 ? 0 : Math.round(((furthest + 1) / PLANNING_STEPS.length) * 100)
  return { furthest, percent }
}

/** The slice of steps on screen: the active one, what just finished, and what's next. */
export function feedWindow(furthest) {
  const active = Math.max(furthest, 0)
  const end = Math.min(PLANNING_STEPS.length, Math.max(active + 2, FEED_WINDOW))
  const start = Math.max(0, end - FEED_WINDOW)
  return PLANNING_STEPS.slice(start, end).map((step, offset) => {
    const index = start + offset
    return {
      ...step,
      index,
      state: index < active ? "done" : index === active ? "active" : "upcoming",
    }
  })
}
