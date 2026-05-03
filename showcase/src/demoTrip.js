export const PREFERENCE_KEYS = ["outdoor", "food", "nightlife", "urban", "shopping"];

export const demoTrip = {
  group_notes:
    "Prioritize a major walkable city with iconic neighborhoods, excellent restaurants, museums, skyline views, transit-friendly routes, and a polished urban itinerary. Avoid remote nature-first destinations.",
  start_date: "2026-09-18",
  end_date: "2026-09-21",
  members: [
    {
      member_id: "maya",
      name: "Maya",
      origin_city: "ORD",
      budget_usd: 1900,
      food_restrictions: ["vegetarian"],
      preference_notes:
        "Wants a big-city trip with art museums, skyline views, vegetarian-friendly restaurants, boutique neighborhoods, and no remote outdoor destinations.",
      preference_vector: {
        outdoor: 0.2,
        food: 0.9,
        nightlife: 0.5,
        urban: 1.0,
        shopping: 0.8,
      },
      is_leader: true,
    },
    {
      member_id: "dev",
      name: "Dev",
      origin_city: "JFK",
      budget_usd: 2100,
      food_restrictions: [],
      preference_notes:
        "Prefers dense urban neighborhoods, public transit or short rideshares, famous food spots, architecture, markets, and a lively evening scene.",
      preference_vector: {
        outdoor: 0.1,
        food: 1.0,
        nightlife: 0.8,
        urban: 1.0,
        shopping: 0.7,
      },
      is_leader: false,
    },
    {
      member_id: "sofia",
      name: "Sofia",
      origin_city: "LAX",
      budget_usd: 2200,
      food_restrictions: [],
      preference_notes:
        "Wants iconic city landmarks, museums, shopping streets, rooftop or waterfront views, excellent coffee, and a premium hotel in a central neighborhood.",
      preference_vector: {
        outdoor: 0.2,
        food: 0.8,
        nightlife: 0.6,
        urban: 1.0,
        shopping: 0.9,
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
