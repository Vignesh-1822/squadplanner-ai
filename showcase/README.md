# SquadPlanner AI App

Temporary hosted product app for the live SquadPlanner backend. This app is isolated from the main `frontend/` and `backend/` folders.

## Local Development

```powershell
cd showcase
npm install
npm run dev
```

By default, the app calls:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Create `showcase/.env.local` to point at a deployed backend:

```env
VITE_API_BASE_URL=https://your-render-service.onrender.com
```

## Vercel Frontend Hosting

1. Create a new Vercel project.
2. Set the project root to `showcase`.
3. Set `VITE_API_BASE_URL` to the Render backend URL.
4. Deploy.

The included `vercel.json` rewrites direct SPA links like `/trip/:tripId` to `index.html`.

## Render Backend Hosting

Deploy the existing `backend/` folder as a Render web service.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Required environment variables:

```env
MONGODB_URI=
ANTHROPIC_API_KEY=
SERPAPI_KEY=
GOOGLE_PLACES_API_KEY=
GOOGLE_ROUTES_API_KEY=
LLM_PROVIDER=anthropic
SERPAPI_MONTHLY_HARD_LIMIT=200
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=squadplanner
```
