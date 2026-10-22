# Running SquadPlanner with Docker

Two containers:

| Service | Image | Port | What it does |
|---|---|---|---|
| `frontend` | `squadplanner-frontend` | `5173` | nginx serving the built React app; proxies `/api/*` (including SSE) to the backend |
| `backend` | `squadplanner-backend` | `127.0.0.1:8000` | FastAPI + LangGraph; `/docs` and `/debug` are reachable from your machine only |

The database is **your own MongoDB Atlas cluster**. No database container is included.

**No secrets are in the images or in `docker-compose.yml`.** Every key comes from your local
`backend/.env` when the container starts. That file is gitignored and excluded from the Docker
build.

## What you need

- Docker Desktop (or Docker Engine + Compose v2).
- A MongoDB Atlas cluster. In Atlas, **Network Access** must allow your IP, or the backend logs
  `MongoDB connection failed`.
- Your own API keys. Only `MONGODB_URI` and `JWT_SECRET` are required to start. Trip generation
  needs an LLM key (`ANTHROPIC_API_KEY`, or `GROQ_API_KEY` with `LLM_PROVIDER=groq`). SerpAPI and
  Google keys enable live flights, hotels, places and routes; without them the app falls back to
  estimates.

## Option 1: from source

```bash
git clone https://github.com/Shubham10jain/squadplanner-ai.git
cd squadplanner-ai
cp backend/.env_example backend/.env
# edit backend/.env: MONGODB_URI, JWT_SECRET (openssl rand -hex 32), API keys
docker compose up --build
```

Open http://localhost:5173 and register an account.

## Option 2: prebuilt images from Docker Hub

You only need two files: `docker-compose.yml` and `backend/.env`. Get the template from
`backend/.env_example` in the repo.

```bash
mkdir squadplanner && cd squadplanner
# put docker-compose.yml here, and your filled-in backend/.env in ./backend/
DOCKERHUB_USER=<publisher> docker compose pull
DOCKERHUB_USER=<publisher> docker compose up
```

Add `TAG=<version>` to pin a specific release instead of `latest`.

## Google sign-in

`VITE_GOOGLE_CLIENT_ID` is a **public** identifier and is baked into the frontend bundle at build
time. If you build without it, Google sign-in is disabled and email/password login still works.
To turn it on:

```bash
VITE_GOOGLE_CLIENT_ID=<your-client-id> docker compose up --build
```

Also set the same value as `GOOGLE_CLIENT_ID` in `backend/.env`, and add `http://localhost:5173`
as an authorized JavaScript origin for that client in Google Cloud Console.

## Everyday commands

```bash
docker compose up -d --build      # start in background
docker compose logs -f backend    # follow backend logs
docker compose down               # stop
docker compose run --rm backend python -m pytest tests/ -q --ignore=tests/test_integration.py
```

Do not run `tests/test_integration.py`. It spends real LLM and API quota.

## Publishing to Docker Hub (maintainers)

Images must work on both Apple Silicon and Intel/Linux machines, so build them multi-arch:

```bash
docker login
export DOCKERHUB_USER=<your-dockerhub-username> TAG=<version>
docker buildx create --use --name squadplanner-builder 2>/dev/null || docker buildx use squadplanner-builder
docker buildx bake -f docker-compose.yml --push \
  --set '*.platform=linux/amd64,linux/arm64'
# also publish :latest
TAG=latest docker buildx bake -f docker-compose.yml --push \
  --set '*.platform=linux/amd64,linux/arm64'
```

To bake your Google client ID into the published frontend image, export `VITE_GOOGLE_CLIENT_ID`
before running `bake`.

### Secret checklist: run before every push

```bash
# 1. No env files inside the images (only the blank template is expected)
docker run --rm --entrypoint sh $DOCKERHUB_USER/squadplanner-backend:$TAG \
  -c 'find / -name ".env*" -not -path "/proc/*" 2>/dev/null'
docker run --rm --entrypoint sh $DOCKERHUB_USER/squadplanner-frontend:$TAG \
  -c 'find / -name ".env*" -not -path "/proc/*" 2>/dev/null'

# 2. No key-shaped strings in the shipped code (expect no output)
docker run --rm --entrypoint sh $DOCKERHUB_USER/squadplanner-backend:$TAG \
  -c 'grep -rIlE "sk-ant-|AIza[0-9A-Za-z_-]{20}|gsk_|lsv2_|mongodb\+srv://[^ ]+:[^ ]+@" /app'
docker run --rm --entrypoint sh $DOCKERHUB_USER/squadplanner-frontend:$TAG \
  -c 'grep -rIlE "sk-ant-|AIza[0-9A-Za-z_-]{20}|gsk_|lsv2_|mongodb\+srv://[^ ]+:[^ ]+@" /usr/share/nginx/html'

# 3. No secrets in build metadata
docker history --no-trunc $DOCKERHUB_USER/squadplanner-backend:$TAG
docker history --no-trunc $DOCKERHUB_USER/squadplanner-frontend:$TAG
```

Docker Hub credentials live in your OS keychain via `docker login`. Never put a token in a file
in this repo.

## Before pushing to GitHub

```bash
git check-ignore -v backend/.env frontend/.env   # both must be listed as ignored
git status --short                                # no .env, .venv/, node_modules/, dist/
git diff --cached | grep -E "sk-ant-|AIza|gsk_|lsv2_|mongodb\+srv://[^ ]+:[^ ]+@"   # expect nothing
```

## Troubleshooting

- **`env file backend/.env not found`**: run `cp backend/.env_example backend/.env` and fill it in.
- **Backend exits with a `ValidationError` naming `MONGODB_URI` or `JWT_SECRET`**: those two are
  required.
- **`/health` shows `"db":"unreachable"`**: check the Atlas URI and Atlas Network Access.
- **Port already in use**: something else is on 5173 or 8000. Stop it, or change the left-hand
  port in `docker-compose.yml`.
