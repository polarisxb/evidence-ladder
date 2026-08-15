FROM node:20-slim AS build
# better-sqlite3 is a native module. prebuild-install fetches its binary from
# GitHub releases, which is slow or unreachable on some networks, and node-gyp
# then needs a real toolchain to build from source. Kept to this stage so the
# runtime image below stays slim.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 make g++ \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
RUN npx tsc
# After tsc, since typescript is a devDependency. Drops devDependencies while
# keeping the native binary just compiled above.
RUN npm prune --omit=dev

FROM node:20-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY src/prompts ./src/prompts
EXPOSE 8002
CMD ["node", "dist/index.js"]
