# Compas

**A local-first knowledge observatory — the web dashboard for [Navigate](https://github.com/isbak/navigate).**

Compas is the primary user interface for the Navigate knowledge platform. It is
a **pure client of Navigate's REST API** — it builds **no API and no database of
its own**. Every page is rendered from data fetched from a running Navigate API
(`catalog api`), giving a single interface to **discover knowledge, understand
relationships, review evidence, govern knowledge, ask questions and navigate
your organisation's collective memory.**

```
Navigate  (Filesystem → Scanner → SQLite → … → Fuseki → GraphRAG → REST API)
                                                                    │  /api
                                                                    ▼
                                                          ✦ Compas (this UI)
```

## Highlights

- **Pure client.** Compas consumes Navigate's documented REST API
  (`/api/...`). Navigate stays the single source of truth and system of record.
  The contract Compas codes against is captured in [`docs/navigate-api.md`](docs/navigate-api.md).
- **Local-first & safe.** Binds to `127.0.0.1`. The **browser only ever talks to
  Compas**, which proxies to Navigate server-side — so the API key never reaches
  the client. No external calls beyond the configured Navigate endpoint.
- **Minimal JavaScript.** FastAPI + Jinja2 + HTMX. The HTMX-style helper and the
  graph renderer are **vendored** (no CDNs), so the UI works offline.
- **Dark-first, responsive** design inspired by Obsidian, Linear, GitHub and the
  Neo4j Browser. The toolbar theme button cycles **dark → light → Claude** (a
  warm Anthropic-Claude palette); swap in your own tokens from
  [claude.ai/design](https://claude.ai/design) via the `[data-theme="claude"]`
  block in `static/css/styles.css`.

## Features

| Area | What you get |
| --- | --- |
| **Dashboard** | Totals (artifacts, objects, relationships, evidence), approved/pending/stale counts, quality score, review queue, notifications, domain overview |
| **Artifacts** | Filterable, paginated table (type / scan / extraction / classification) with detail (evidence, links) and re-scan/extract/classify actions that enqueue Navigate jobs |
| **Knowledge Objects** | Filterable table (confidence, owner, status, review, quality) and a detail view with relationships (graph neighbours), evidence, source documents and inline approve/reject/archive |
| **Relationships** | Subject–predicate–object triples (names resolved) with inline approve/reject |
| **Domains** | Per-domain health from Navigate's `/governance/domains` (objects, owner, quality, freshness, review backlog) |
| **Governance** | Review queue, pending relationships, quality/drift/orphan/duplicate alerts, stale objects, knowledge-health metrics, drift feed and owner roster |
| **Cost & LLM Usage** | Navigate's token-usage / spend ledger (`/cost/*`): totals, by-model, by-operation, most expensive documents and spend-vs-confidence |
| **Graph Explorer** | Vendored interactive SVG graph (zoom, pan, drag, expand, search, shortest path, view modes) backed by Navigate's `/graph/*` endpoints |
| **GraphRAG** | Navigate's assistant with reasoning modes (`/ask`, `/ask/explain|impact|compare|path-reason`) — answer, confidence band, knowledge objects, relationships and evidence used |
| **Search** | Fans out across Navigate's `search=` filters for knowledge objects and artifacts |
| **Observability** | Navigate pipeline jobs, API health, link statistics, graph analytics (`/graph/health|metrics|domains`) and RDF projection (`/rdf/*`) with GEXF/GraphML/Turtle exports |
| **Settings** | Navigate connection + live health |

## Quick start

```bash
# 1. In your Navigate checkout, start the API:
catalog api                                   # serves http://127.0.0.1:8000

# 2. Run Compas:
pip install -r requirements.txt
python -m compas                              # http://127.0.0.1:8000 → set a different port if needed
# or: uvicorn compas.main:app --reload --port 8500
```

Point Compas at Navigate via `COMPAS_NAVIGATE_API_URL` (default
`http://127.0.0.1:8000/api`). If Navigate isn't reachable, Compas shows a clear
"Navigate API unavailable" page rather than failing opaquely.

## Configuration

Environment variables prefixed `COMPAS_` (see `.env.example`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `COMPAS_NAVIGATE_API_URL` | `http://127.0.0.1:8000/api` | Navigate REST API base |
| `COMPAS_NAVIGATE_API_KEY` | _(empty)_ | Bearer token, if Navigate requires one |
| `COMPAS_PAGE_SIZE` | `50` | Page size (Navigate `limit`) |
| `COMPAS_GRAPH_NODE_LIMIT` | `250` | Max nodes per graph payload |
| `COMPAS_ASK_DEPTH` | `2` | GraphRAG retrieval depth |

## Architecture

```
compas/
├── config.py            # COMPAS_* settings (Navigate connection)
├── navigate_client.py   # The ONLY backend: typed client for Navigate's /api
├── service.py           # Shapes Navigate responses into view-models (Page, etc.)
├── web/routes.py        # HTMX pages + a few JSON view-helpers for the graph widget
├── templates/           # Jinja2 (base + pages + partials)
└── static/              # Vendored compas.js, graph.js, styles.css
docs/navigate-api.md     # The Navigate REST contract Compas consumes
```

Compas exposes **no** REST API and **no** `/openapi.json`; its only HTTP surface
is the server-rendered UI (plus small `/graph/*` JSON helpers that feed its own
graph explorer). Anything the Navigate API doesn't expose is degraded gracefully
rather than invented — e.g. against an older Navigate without the
`/governance/domains` resource, domains fall back to a dashboard derivation. See
the "Gaps" note in `docs/navigate-api.md`.

## Tests

```bash
pytest        # service, client (httpx MockTransport) and UI/HTMX tests
```

Tests inject a `FakeNavigateClient`, so no real Navigate server is required.

## License

MIT
