# Compas

**A local-first knowledge observatory — the web dashboard for [Navigate](https://github.com/isbak/navigate).**

Compas is the primary user interface for the Navigate knowledge platform. It
reads Navigate's SQLite catalog (the system of record), the Apache Jena Fuseki
graph and the GraphRAG assistant, and presents a single interface to
**discover knowledge, understand relationships, review evidence, govern
knowledge, ask questions and navigate your organisation's collective memory.**

```
Filesystem → Scanner → SQLite → Document Cache → Link Discovery →
Semantic Classification → Knowledge Consolidation → RDF Export →
Jena Fuseki → GraphRAG Assistant → ✦ Compas (this dashboard)
```

## Highlights

- **Local-first.** Binds to `127.0.0.1` and makes **no external network calls**
  unless you explicitly enable Fuseki or a remote GraphRAG endpoint. Source
  documents are never moved or modified.
- **Minimal JavaScript.** FastAPI + Jinja2 + HTMX. The HTMX-style helper and
  the graph renderer are **vendored** (no CDNs), so the app works fully offline.
- **Dark-first, responsive UI** inspired by Obsidian, Linear, GitHub and the
  Neo4j Browser.
- **Runs out of the box.** On first start, if no catalog is found, Compas seeds
  a realistic demo catalog so you can explore immediately.

## Features

| Area | What you get |
| --- | --- |
| **Dashboard** | Totals (artifacts, objects, relationships, evidence), approved/pending/stale counts, knowledge-quality score, growth trend, domain overview, recent changes, notifications |
| **Artifacts** | Filterable, paginated table (type/domain/status/date) with links & knowledge-object counts; per-artifact detail with classification, evidence, links |
| **Knowledge Objects** | Table (confidence, evidence, relationships, owner, review status, quality) and a rich detail view with evidence, relationships, source documents, history & timeline |
| **Relationships** | Subject–predicate–object triples with inline approve/reject |
| **Domains** | Per-domain objects, relationships, quality, freshness, owners |
| **Governance Center** | Review/approval queues, quality/drift/orphan/duplicate alerts, stale objects, knowledge-health metrics |
| **Graph Explorer** | Vendored interactive SVG graph: zoom, pan, drag, expand/collapse, search, neighbours, shortest-path explorer, view modes (Capability/Technology/Decision/Team/Process) |
| **GraphRAG** | Grounded Q&A with answer, confidence, evidence, knowledge objects used and the SPARQL queries — plus "show graph context / evidence / relationships" |
| **Global Search** | Fuzzy search across objects, artifacts, relationships and domains |
| **Observability** | Scanner / link / classification jobs, Fuseki sync status, errors & warnings |
| **Settings** | Catalog, LLM provider, Fuseki, GraphRAG and governance configuration |

## Quick start

```bash
pip install -r requirements.txt
python -m compas                      # http://127.0.0.1:8000
# or: uvicorn compas.main:app --reload
```

A demo catalog is seeded automatically. To point Compas at a real Navigate
catalog, copy `.env.example` to `.env` and set `COMPAS_DATABASE_PATH` to your
`navigate/data/catalog.sqlite`.

## Configuration

All settings are environment variables prefixed `COMPAS_` (see `.env.example`).
Key ones:

| Variable | Default | Purpose |
| --- | --- | --- |
| `COMPAS_DATABASE_PATH` | `./data/catalog.sqlite` | Navigate's catalog |
| `COMPAS_READ_ONLY` | `false` | Open the catalog read-only (disables governance writes) |
| `COMPAS_DEMO_MODE` | `true` | Seed a demo catalog when the database is missing |
| `COMPAS_FUSEKI_ENABLED` | `false` | Enable SPARQL queries against Jena Fuseki |
| `COMPAS_GRAPHRAG_ENABLED` | `false` | Delegate Q&A to Navigate's GraphRAG (else answer locally) |

## REST API

`/api` exposes JSON for everything the UI uses:

```
/api/stats            /api/artifacts        /api/knowledge
/api/relationships    /api/evidence         /api/domains
/api/governance       /api/graphrag         /api/search
/api/graph            /api/graph/path       /api/graph/neighbors/{id}
/api/notifications    /api/observability    /api/fuseki/status
```

Interactive docs at `/docs`.

## Architecture

```
compas/
├── config.py        # COMPAS_* settings (local-first defaults)
├── database.py      # SQLAlchemy engine/session for Navigate's catalog
├── models.py        # ORM mirroring Navigate's catalog schema
├── repository.py    # All catalog queries (paginated, scalable)
├── graphrag.py      # Local-first grounded assistant (+ optional remote)
├── fuseki.py        # Optional SPARQL client
├── sample_data.py   # Demo catalog seeder
├── api/             # REST routers
├── web/             # HTMX page + partial routes
├── templates/       # Jinja2 (base + pages + partials)
└── static/          # Vendored compas.js, graph.js, styles.css
```

Because Compas reads Navigate's catalog directly, the ORM in `models.py` matches
Navigate's tables 1:1 (`artifacts`, `knowledge_objects`, `knowledge_evidence`,
`knowledge_relationships`, `knowledge_lifecycle`, `knowledge_quality`,
`knowledge_alerts`, …).

## Performance

Built for 10,000+ artifacts and 100,000+ relationships: every list is
paginated, the graph loads incrementally (neighbourhood expansion + node
limits), and search is bounded. See `tests/test_performance.py`.

## Tests

```bash
pytest            # backend, API, UI/HTMX, graph and performance tests
```

## License

MIT
