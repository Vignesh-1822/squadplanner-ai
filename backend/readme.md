```text
backend/
├── main.py
├── config.py
├── requirements.txt
│
├── agent/
│   ├── graph.py                    # Orchestrator StateGraph
│   ├── state.py                    # TripState + ItineraryState TypedDicts
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── input_parser.py         # parse_input node
│   │   ├── destination_selector.py # select_destination node (LLM)
│   │   ├── tool_selector.py        # dynamic_tool_selection node
│   │   ├── budget_analyzer.py      # budget_analysis node (deterministic)
│   │   ├── hotel_searcher.py       # search_hotel node
│   │   ├── fairness_scorer.py      # compute_fairness + score_compatibility (merged, deterministic)
│   │   └── output_assembler.py     # assemble_output node (LLM)
│   └── subgraphs/
│       ├── __init__.py
│       └── itinerary.py            # Full itinerary agent subgraph
│
├── tools/
│   ├── __init__.py
│   ├── serpapi.py                  # Flights + hotels, budget gate
│   ├── google_places.py            # Dynamic category fetch
│   ├── google_routes.py            # Routes API wrapper
│   └── open_meteo.py               # Weather (no key)
│
├── db/
│   ├── __init__.py
│   ├── client.py                   # Motor async MongoDB client
│   ├── checkpointer.py             # MongoDBCheckpointer for LangGraph HITL
│   └── models.py                   # Pydantic models for DB documents
│
├── api/
│   ├── __init__.py
│   ├── trips.py                    # POST /trips, GET /trips/{id}/stream (SSE)
│   ├── hitl.py                     # POST /trips/{id}/confirm-city
│   └── admin.py                    # GET /admin/serpapi-usage
│
└── utils/
    ├── __init__.py
    ├── preference_vectors.py       # 5D vector math, dot product scoring
    ├── neighborhood_cluster.py     # Proximity-based activity clustering
    └── streaming.py                # SSE formatting, NODE_PROGRESS_MAP
```

Run from this directory:

`uvicorn main:app --reload`
