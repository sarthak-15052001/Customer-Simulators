# vtf/front — Node 22 + npm + Bun on Alpine
#
# Why all three? The team can pick any tool:
#   - npm install / npm run dev    (default, works everywhere)
#   - bun install / bun run dev    (faster, optional)
#   - node ...                     (direct invocation)
#
# Bun's binaries link against glibc, so we add `gcompat` + `libstdc++` to
# provide the compatibility shim on Alpine (musl libc).

FROM node:22-alpine

# System deps:
#   - bash, curl, unzip   → bun installer
#   - gcompat, libstdc++  → run bun on musl
#   - git                 → some npm packages need it for postinstall
RUN apk add --no-cache bash curl unzip git gcompat libstdc++

# Install Bun (latest stable). Move to /usr/local/bin so it's on PATH for any user.
RUN curl -fsSL https://bun.sh/install | bash \
 && mv /root/.bun/bin/bun /usr/local/bin/bun \
 && bun --version

# Sanity checks (fail-fast at build time)
RUN node --version && npm --version && bun --version

WORKDIR /app

# Default port for Vite dev server
EXPOSE 5173

# Compose overrides this with `npm run dev -- --host 0.0.0.0`
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
