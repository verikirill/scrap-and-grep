# syntax=docker/dockerfile:1

# Remotion render service. Node 24 runs the TypeScript server directly (type
# stripping), so there is no compile step; the compositions are bundled once
# here, and Chrome Headless Shell is downloaded here too.
FROM node:24-bookworm-slim

# Shared libraries of Chrome Headless Shell, as listed by Remotion, and one
# fallback font for characters the bundled subsets lack.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 libxrandr2 \
       libxkbcommon-dev libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 \
       libpango-1.0-0 libcairo2 libcups2 \
       fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN chown node:node /app
USER node

COPY --chown=node:node package.json package-lock.json ./
RUN --mount=type=cache,target=/home/node/.npm,uid=1000,gid=1000 \
    npm ci --omit=dev --no-audit --no-fund

COPY --chown=node:node public ./public
COPY --chown=node:node src ./src
COPY --chown=node:node server ./server

RUN npx remotion browser ensure \
    && node server/prebundle.ts

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000

EXPOSE 3000
CMD ["node", "server/server.ts"]
