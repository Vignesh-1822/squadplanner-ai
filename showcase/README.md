# SquadPlanner AI App

Temporary hosted product app for the live SquadPlanner backend. This app is isolated from the main `frontend/` and `backend/` folders.

The showcase app now supports post-generation itinerary refinement. After a trip completes, the
itinerary page shows an "Ask for a change" box. Requests like `Make Day 2 cheaper` or
`Swap the museum for something outdoors` call the backend refinement endpoint, open an SSE stream,
and replace the displayed itinerary with the updated graph result.

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

1. Create or open the Vercel project connected to this GitHub repo.
2. Set the project root to `showcase`.
3. Set `VITE_API_BASE_URL` to the Render backend URL.
4. Deploy. If GitHub auto-deploy is enabled, `git push origin main` redeploys the showcase app.

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

If the Render service is connected to this GitHub repo with auto-deploy enabled, `git push origin main`
redeploys the backend. Otherwise, push the commit and click "Manual Deploy" or "Redeploy latest
commit" in Render.

## Production Demo Checklist

1. Push the latest commit:

```powershell
git add backend showcase README.md
git commit -m "Add stateful itinerary refinement endpoint"
git push origin main
```

2. Confirm the backend deploy is healthy:

```text
https://your-render-service.onrender.com/health
```

3. Confirm Vercel has this environment variable:

```env
VITE_API_BASE_URL=https://your-render-service.onrender.com
```

4. Open the Vercel app, create a trip, wait for completion, then test a refinement from the itinerary page:

```text
Make Day 2 cheaper
Swap the museum for something outdoors
Keep the pace more relaxed
```
