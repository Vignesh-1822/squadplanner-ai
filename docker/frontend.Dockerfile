# SquadPlanner frontend image: builds the Vite app, then serves it with nginx, which also
# reverse-proxies /api to the backend so the browser only ever talks to one origin.
#
# Build context is the repo root (so frontend/ stays untouched); the allowlist lives in
# frontend.Dockerfile.dockerignore next to this file.

# ---- build ----
FROM node:22-alpine AS build
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# Vite bakes VITE_* values into the public JS bundle, so only non-secret values belong here.
# A relative API base keeps the image portable: nginx proxies /api to the backend.
ARG VITE_API_BASE_URL=/api
# Public OAuth client identifier (visible to every browser). Empty disables Google sign-in.
ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

RUN npm run build

# ---- serve ----
FROM nginx:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
