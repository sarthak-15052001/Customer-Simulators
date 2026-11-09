# Customer Simulators (VTF)

Monorepo containing the **frontend simulator** (React/Vite/TypeScript) and the **backend API** (Django/DRF, in development).

## Layout

```
.
├── vtf/
│   ├── front/                      # React + Vite + TS (existing app)
│   │   ├── src/                    # Components, utils, mocks, data, types
│   │   ├── docs/                   # Frontend docs (UI guidelines, API export audit)
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   └── ...
│   └── api/                        # Django + DRF backend (planned)
│       └── docs/                   # Engineering spec & implementation guide
│           ├── README.md           # Doc index
│           ├── CLAUDE.md           # Quick reference for Claude Code
│           ├── 00-overview.md      # Vision, success metrics, phases
│           ├── 01-frontend-source-of-truth.md
│           ├── 02-fixtures-mapping.md          # 32 villages + VTF URL builder
│           ├── 03-data-models.md
│           ├── 04-services.md
│           ├── 05-api-endpoints.md
│           ├── 06-data-collection-strategy.md
│           ├── 07-recommendation-engine.md     # 5-tier waterfall + SVD
│           ├── 08-cache-and-scraping.md        # Phase 3
│           ├── 09-implementation-roadmap.md    # Sprint plan + AI protocol
│           ├── 10-config-and-reference.md      # Env vars, mgmt cmds, glossary
│           └── 11-booking-redirect.md          # Token-based redirect service
└── README.md                       # (this file)
```

## Quick start — Docker (recommended)

Run everything (frontend + API + Redis) with one command:

```bash
docker compose up
```

- Frontend: http://localhost:5173
- API:      http://localhost:8000  (idle until the Django project is bootstrapped — see `vtf/api/docs/09-implementation-roadmap.md`)
- Redis:    redis://localhost:6379

The frontend container ships with **Node 22 + npm + Bun** on Alpine, so you can run any
of: `docker compose exec front npm run lint`, `docker compose exec front bun install`, etc.

All persistent data (node_modules, pip cache, redis data, sqlite db) lives in named
volumes with the local driver — see `docker-compose.yml`.

## Quick start — without Docker

### Frontend

```bash
cd vtf/front
npm install
npm run dev
```

### Backend

The backend is **not yet implemented**. See `vtf/api/docs/` for the full spec, then bootstrap:

```bash
cd vtf/api
# (see vtf/api/docs/09-implementation-roadmap.md)
```

## For Claude Code sessions

Open `vtf/api/docs/CLAUDE.md` first — it contains the project conventions, key paths,
and a starter prompt for backend work.
