export const PREFERENCE_KEYS = ["outdoor", "food", "nightlife", "urban", "shopping"];

export const demoTrip = {
  group_notes:
    "Keep the trip relaxed, avoid rushed mornings, and make sure the plan respects everyone's must-haves.",
  start_date: "2026-07-10",
  end_date: "2026-07-13",
  members: [
    {
      member_id: "alice",
      name: "Alice",
      origin_city: "ORD",
      budget_usd: 1500,
      food_restrictions: ["vegetarian"],
      preference_notes: "Hates early mornings, no clubs, wants Italian food at least once.",
      preference_vector: {
        outdoor: 0.8,
        food: 0.7,
        nightlife: 0.2,
        urban: 0.6,
        shopping: 0.1,
      },
      is_leader: true,
    },
    {
      member_id: "bob",
      name: "Bob",
      origin_city: "ATL",
      budget_usd: 1200,
      food_restrictions: [],
      preference_notes:
        "Likes relaxed days with good meals and urban neighborhoods, but does not want an overpacked schedule.",
      preference_vector: {
        outdoor: 0.5,
        food: 0.8,
        nightlife: 0.6,
        urban: 0.4,
        shopping: 0.3,
      },
      is_leader: false,
    },
    {
      member_id: "carol",
      name: "Carol",
      origin_city: "LAX",
      budget_usd: 2000,
      food_restrictions: [],
      preference_notes: "Interested in scenic walks and museums, but not late-night clubbing.",
      preference_vector: {
        outdoor: 0.6,
        food: 0.6,
        nightlife: 0.4,
        urban: 0.7,
        shopping: 0.5,
      },
      is_leader: false,
    },
  ],
};

export function createBlankMember(index) {
  const next = index + 1;
  return {
    member_id: `traveler_${next}`,
    name: `Traveler ${next}`,
    origin_city: "",
    budget_usd: 1200,
    food_restrictions: [],
    preference_notes: "",
    preference_vector: {
      outdoor: 0.5,
      food: 0.5,
      nightlife: 0.3,
      urban: 0.5,
      shopping: 0.3,
    },
    is_leader: false,
  };
}
