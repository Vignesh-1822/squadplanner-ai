```text
backend/
├── main.py                        # FastAPI app entry point
├── requirements.txt
├── .env
│
├── agent/
│   ├── __init__.py
│   ├── graph.py                   # LangGraph StateGraph definition
│   ├── state.py                   # TripState TypedDict + Pydantic models
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── parse_input.py         # Input validation + date consensus
│   │   ├── select_destination.py  # Destination scoring + selection
│   │   ├── search_flights.py      # SerpAPI flight search
│   │   ├── search_hotel.py        # SerpAPI hotel search
│   │   ├── fetch_activities.py    # Google Places activities + restaurants
│   │   ├── build_itinerary.py     # LLM-powered slot assignment
│   │   ├── plan_routes.py         # Google Maps Directions
│   │   ├── check_weather.py       # Open-Meteo API
│   │   ├── compute_fairness.py    # Cost + fairness analysis
│   │   ├── assemble_output.py     # Final JSON assembly
│   │   └── parse_refinement.py    # Refinement request classification
│   └── tools/
│       ├── __init__.py
│       ├── google_places.py       # Places API wrapper + caching
│       ├── google_maps.py         # Directions API wrapper
│       ├── serpapi_flights.py     # Flight search wrapper
│       ├── serpapi_hotels.py      # Hotel search wrapper
│       ├── weather.py             # Open-Meteo wrapper
│       └── llm.py                 # Gemini LLM wrapper
│
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── trip.py                # Trip generation + retrieval + refinement
│   │   ├── auth.py                # Auth endpoints
│   │   └── user.py                # User profile endpoints
│   └── middleware/
│       └── auth.py                # JWT/session validation
│
├── data/
│   ├── destinations_db.json       # 500 destinations
│   └── scoring.py                 # Preference matching algorithms
│
├── db/
│   ├── __init__.py
│   ├── connection.py              # MongoDB connection
│   └── models.py                  # DB models (users, trips, cache)
│
└── tests/
    ├── test_agent.py
    ├── test_tools.py
    └── test_scoring.py
```