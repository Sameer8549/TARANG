# TARANG

TARANG is a coastal emergency response platform built for the **Coastal Innovation Hackathon** by **Deploy or Die**. It gives operators a live rescue console for maritime distress cases, vessel tracking, multilingual alerts, and dispatch workflows that stay useful even in patchy-connectivity environments.

The project combines:

- a polished operator-facing frontend for home, dashboard, fleet, stats, and rescue flows
- a full Python backend that represents the original product architecture
- a Catalyst-ready Node AppSail service that powers the current live deployment
- seeded legacy rescue data so the system feels like a working operations center, not an empty demo

## Live Demo

Working deployment:

- [TARANG Live App](https://tarang-50043555806.development.catalystappsail.in)
- [Operations Dashboard](https://tarang-50043555806.development.catalystappsail.in/dashboard)
- [How It Works](https://tarang-50043555806.development.catalystappsail.in/how-it-works)

## Why TARANG

Coastal response tools often break down when they are noisy, slow, or built like a slideshow instead of an operational product. TARANG is designed around the real control-room loop:

1. A distress case appears.
2. The operator opens that profile.
3. The map focuses on the incident.
4. The team dispatches rescue action.
5. The case stays live until it is resolved.

That flow drives the UI, backend routes, alerts, live updates, and voice interactions across the app.

## Highlights

- Live operations dashboard with active, dispatched, and resolved case tracking
- Profile-to-map rescue flow for focused case handling
- Fleet and analytics pages aligned with coastal operations use
- English and Kannada content support
- Voice alert pipeline with per-profile distress playback and post-rescue completion voice
- Real-time updates through API polling and WebSocket support
- Catalyst AppSail deployment already wired
- Groq and Mistral integration hooks in the backend architecture

## Repo Structure

```text
TARANG/
├── index.html                  # Public-facing landing page
├── frontend/                   # Local frontend pages and assets
│   ├── app.html
│   ├── dashboard.html
│   ├── how-it-works.html
│   ├── vessels.html
│   ├── analytics.html
│   ├── shared.css
│   ├── shared.js
│   └── assets/voice/
├── backend/                    # Original FastAPI backend
│   ├── main.py
│   ├── requirements.txt
│   ├── tarang.db
│   ├── models/
│   ├── routes/
│   └── services/
├── catalyst-app/               # Current Zoho Catalyst AppSail bundle
│   ├── app-config.json
│   ├── server.js
│   ├── legacy-data.json
│   └── frontend/
├── catalyst.json               # Catalyst project mapping
└── package.json                # Helpful local scripts and project metadata
```

## Product Surfaces

### Home
The homepage introduces TARANG as a serious coastal rescue system with a cleaner narrative and direct entry into operations.

### Dashboard
The dashboard is the main control room. Operators can:

- review active rescue cases
- open a specific profile
- move directly into map-focused rescue handling
- trigger dispatch and resolution flows
- hear operator feedback and distress audio cues

### Fleet
The fleet page presents tracked vessels and operational status in a more registry-like format rather than a generic gallery.

### Stats
The stats view summarizes rescue volume, activity, and readiness in a way that supports an operator or demo jury quickly.

### How It Works
The `how-it-works` page now explains the full rescue lifecycle as a real operational process rather than a placeholder page.

## Architecture

### 1. Local Product Backend
The original backend lives in [`backend/main.py`](C:/Users/abdul/.gemini/antigravity/scratch/tarang/backend/main.py) and uses FastAPI with modular routes for:

- alerts
- vessels
- weather
- AI triage
- simulation
- operations readiness
- voice features

This backend also uses SQLite through [`backend/tarang.db`](C:/Users/abdul/.gemini/antigravity/scratch/tarang/backend/tarang.db).

### 2. Live Catalyst Backend
The production deployment currently runs through [`catalyst-app/server.js`](C:/Users/abdul/.gemini/antigravity/scratch/tarang/catalyst-app/server.js), a Node AppSail service that mirrors the product behavior and serves the live frontend.

It includes:

- API routes for alerts, vessels, weather, ops, simulation, and voice
- seeded legacy case data from [`catalyst-app/legacy-data.json`](C:/Users/abdul/.gemini/antigravity/scratch/tarang/catalyst-app/legacy-data.json)
- WebSocket support for dashboard updates
- optional Groq and Mistral-based triage integration when keys are configured

## Local Development

### Option A: Run the original FastAPI backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Then open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/dashboard`
- `http://127.0.0.1:8000/how-it-works`

### Option B: Run the Catalyst-compatible Node service locally

```bash
set PORT=8010
node catalyst-app/server.js
```

Then open:

- `http://127.0.0.1:8010/`
- `http://127.0.0.1:8010/dashboard`
- `http://127.0.0.1:8010/how-it-works`

## Deployment

This repository is already structured for **Zoho Catalyst AppSail** deployment.

Key files:

- [`catalyst.json`](C:/Users/abdul/.gemini/antigravity/scratch/tarang/catalyst.json)
- [`catalyst-app/app-config.json`](C:/Users/abdul/.gemini/antigravity/scratch/tarang/catalyst-app/app-config.json)

Typical deploy command:

```bash
npx zcatalyst-cli deploy --only appsail
```

## AI and Integrations

The codebase is prepared for:

- `GROQ_API_KEY`
- `MISTRAL_API_KEY`
- Twilio-based communication hooks in the original backend

If those keys are not configured, the live service still runs with fallback rescue logic and seeded cases.

## Team

**Deploy or Die**  
Built for the **Coastal Innovation Hackathon**

## Current Status

The repo now reflects the latest working TARANG app direction:

- refined operations-centered UX
- repaired `how-it-works` route
- improved message dismissal behavior
- rescue completion voice conflict reduced to a single completion path
- Catalyst deployment flow kept intact

## License

MIT
