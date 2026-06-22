# Navigate REST API (consumed by Compas)

Compas is a **pure client** of the Navigate REST API — it builds no API of its
own. This document is the contract Compas codes against. Source of truth:
[`isbak/navigate`](https://github.com/isbak/navigate) → `src/catalog/api`.

Start the API from Navigate:

```bash
catalog api --host 127.0.0.1 --port 8000     # Swagger at /docs, schema at /openapi.json
```

## Conventions

- **Base path:** `/api` (e.g. `http://127.0.0.1:8000/api`).
- **Auth:** optional. When enabled, send `Authorization: Bearer <key>`.
- **Pagination:** list endpoints take `limit` (default 50, max 500) and
  `offset` (default 0) and return the envelope:
  `{ "items": [...], "limit": int, "offset": int, "total": int }`.
- **Errors:** `{ "error": str, "message": str, "details": {...} }`.

## Endpoints

### Base
- `GET /health` → `HealthResponse { status, database, version }`
- `GET /stats` → `StatsResponse { artifact_count, link_count, knowledge_object_count, relationship_count, evidence_count, pending_review_count, stale_object_count, last_scan? }`

### Artifacts
- `GET /artifacts` — filters: `file_type, scan_status, extraction_status, classification_status, search` → `Paginated[Artifact]`
- `GET /artifacts/{artifact_id}` → `Artifact`
- `GET /artifacts/{artifact_id}/links` → `Paginated[Link]`
- `GET /artifacts/{artifact_id}/evidence` → `Paginated[Evidence]`
- `POST /artifacts/{artifact_id}/rescan|extract|classify` → `Job`

`Artifact { id, path, filename, file_type, size_bytes?, created_at?, modified_at?, sha256?, source_system?, scan_status?, first_seen_at?, last_scanned_at?, extraction_status, classification_status }`

### Links
- `GET /links` — filters: `source_artifact_id, target_system, target_type, link_kind, status` → `Paginated[Link]`
- `GET /links/stats` → `LinkStats { total, by_target_system[], by_target_type[], by_link_kind[] }`
- `GET /links/top-targets?limit=20` → `[TopTarget { url, count }]`

### Knowledge objects  (note: path is `/knowledge-objects`)
- `GET /knowledge-objects` — filters: `object_type, status, review_status, owner, domain, min_confidence, search` → `Paginated[KnowledgeObject]`
- `POST /knowledge-objects/approve-confidence` — body `ConfidenceApprovalRequest { min_confidence, max_confidence, include_reviewed, note }` → `ConfidenceApprovalResponse { min_confidence, max_confidence, objects_approved, relationships_approved, message }`
- `GET /knowledge-objects/{object_id}` → `KnowledgeObject`
- `GET /knowledge-objects/{object_id}/relationships` → `Paginated[Relationship]`
- `GET /knowledge-objects/{object_id}/evidence` → `Paginated[Evidence]`
- `GET /knowledge-objects/{object_id}/mentions` → `Paginated[Mention]`
- `POST /knowledge-objects/{object_id}/approve|reject|archive` → `ActionResponse { id, status, message }`

`KnowledgeObject { id, name, object_type, description?, canonical_name?, confidence?, status?, merge_confidence?, created_at?, updated_at?, review_status?, freshness_state?, quality_score?, owner?, relationship_count?, evidence_count?, mention_count? }`

### Relationships
- `GET /relationships` — filters: `source_object_id, target_object_id, predicate, review_status, min_confidence` → `Paginated[Relationship]`
- `POST /relationships/approve-confidence` — body `ConfidenceApprovalRequest` → `ConfidenceApprovalResponse`
- `GET /relationships/{relationship_id}` → `Relationship`
- `POST /relationships/{relationship_id}/approve|reject|archive` → `ActionResponse`

`Relationship { id, source_object, predicate, target_object, confidence?, evidence?, review_status?, created_at?, updated_at? }`

### Evidence
- `GET /evidence` — filters: `artifact_id, knowledge_object_id, relationship_id` → `Paginated[Evidence]`
- `GET /evidence/{evidence_id}` → `Evidence`

`Evidence { id, knowledge_object_id, artifact_id, quote?, page_number?, slide_number?, confidence?, created_at? }`

### Graph
- `GET /graph/nodes` → `Paginated[GraphNode]`
- `GET /graph/edges` → `Paginated[GraphEdge]`
- `GET /graph/object/{object_id}/neighbors` → `NeighborsResponse { object_id, neighbors: { predicate: [GraphNeighbor{ id, label, type, direction }] } }`
- `GET /graph/object/{object_id}/impact` → `ImpactResponse`
- `GET /graph/path?source=&target=&max_depth=` → `PathResponse { source, target, found, hops: [PathHop{ from, to, predicate, forward }] }`
- `GET /graph/export-json` → `GraphExport { nodes: [GraphNode], edges: [GraphEdge] }`
- `GET /graph/health` → `dict` (islands, untraceable claims, low-confidence objects, duplicates, connectivity)
- `GET /graph/metrics?top=N` → `dict` (density, components, clusters, centrality rankings)
- `GET /graph/domains` → `[GraphDomain { domain, object_count, relationship_count, most_central: [GraphCentralNode{ id, label, degree }] }]`
- `GET /graph/export-gexf` → GEXF XML download (`application/gexf+xml`)
- `GET /graph/export-graphml` → GraphML XML download (`application/graphml+xml`)

`GraphNode { id, label, type, confidence?, status?, documents?, mentions? }`
`GraphEdge { id, source, target, predicate, confidence?, status? }`

Compas surfaces graph analytics + the GEXF/GraphML exports on its **Observability**
page; the exports are proxied server-side so the API key never reaches the browser.

### Governance
- `GET /governance/dashboard` → `dict`
- `GET /governance/review-queue` → `[ReviewQueueItem { object_id, name?, object_type?, review_state?, freshness_state?, last_confidence? }]`
- `GET /governance/stale` → `[StaleItem { object_id, name?, object_type?, freshness_state?, freshness_score?, last_seen_at? }]`
- `GET /governance/orphaned` → `dict`
- `GET /governance/alerts?alert_type=&severity=` → `[GovernanceAlert { id, alert_type, severity, object_id?, message?, status?, created_at?, resolved_at? }]`
- `GET /governance/quality?ascending=false` → `QualityResponse { average_quality, items: [QualityItem{ object_id, canonical_name?, object_type?, quality_score?, evidence_count?, document_count? }] }`
- `GET /governance/domains` → `[DomainHealth { domain, owner?, object_count, avg_quality?, avg_freshness?, review_backlog }]`
- `GET /governance/domains/{name}` → `DomainHealth`
- `GET /governance/changes` — filters: `object_id, change_type` → `Paginated[ChangeLogEntry { id, change_type, target_kind, object_id?, field?, old_value?, new_value?, detail?, detected_at }]`
- `GET /governance/growth?interval=day|week|month&limit=12` → `GrowthTrend { interval, points: [GrowthPoint{ period, artifacts_added, artifacts_total, objects_added, objects_total, relationships_added, relationships_total }] }`
- `GET /governance/drift?limit=N` → `[ChangeLogEntry]` (recent quality/confidence drift)
- `GET /governance/owners` → `[OwnerAssignment { object_id, owner_type, owner_id, assigned_at?, assigned_by? }]`
- `GET /governance/objects/{object_id}/history` → `ObjectHistory { object_id, changes: [ChangeLogEntry], lifecycle?, owner? }`
- `POST /governance/objects/{object_id}/assign-owner` — body `{ owner_type, owner_id }` → `ActionResponse`
- `POST /governance/objects/{object_id}/flag` → `ActionResponse`

Compas surfaces drift + the owner roster on its **Governance** page, and per-object
history / assign-owner / flag on the knowledge-object detail view.

### Cost / LLM usage
The token-usage / spend ledger (`llm_usage`). Compas renders these on its **Cost &
LLM Usage** page; against an older Navigate that lacks them it shows an
"unavailable" panel rather than inventing numbers.

- `GET /cost/summary` → `CostSummary { calls, input_tokens, output_tokens, total_tokens, cache_read_tokens, cache_write_tokens, cost_usd?, unpriced_calls }`
- `GET /cost/by-operation` → `[CostByOperation { operation?, calls, total_tokens, cost_usd? }]`
- `GET /cost/by-model` → `[CostByModel { model?, calls, total_tokens, cost_usd?, unpriced_calls }]`
- `GET /cost/per-document?top=N` → `[CostPerDocument { artifact_id?, calls, total_tokens, cost_usd? }]`
- `GET /cost/vs-quality?top=N` → `[CostVsQuality { artifact_id?, document_type?, type_confidence?, calls, total_tokens, cost_usd? }]`

### RDF projection
Counts + serialisation of the approved graph as RDF. Compas shows the stats +
last-export validation on **Observability** and proxies the export downloads.

- `GET /rdf/stats` → `RdfStats { objects, relationships, evidence, knowledge_triples, relationship_triples, provenance_triples }`
- `GET /rdf/export?fmt=turtle|json-ld|nt` → RDF document download (`text/turtle` / `application/ld+json` / `application/n-triples`)
- `GET /rdf/validate` → `RdfValidation { files: { name: { ok, triples, error? } } }`

### GraphRAG
Gated behind Navigate's `enable_graphrag` setting; returns `501` when disabled.
Compas exposes the reasoning modes as a selector on its **GraphRAG** page.

- `POST /ask` — body `AskRequest { question, depth, show_context, show_evidence }` →
  `AskResponse { answer, confidence (band string), objects_used[], relationships_used[], evidence_used[], context? }`
- `POST /ask/explain` · `POST /ask/impact` — body `ExplainRequest { term, depth, show_context, show_evidence }` → `AskResponse`
- `POST /ask/compare` · `POST /ask/path-reason` — body `CompareRequest { term_a, term_b, depth, show_context, show_evidence }` → `AskResponse`

### Compliance & standards
Navigate ingests standards (Eurocodes, ISO, GDPR…) as `Standard`/`Requirement`
knowledge objects, extracts machine-readable `Equation`s, and tracks coverage,
gaps and assessment records. Standards, Requirements and Equations are knowledge
objects, so their **approve/reject/archive** reuses
`POST /knowledge-objects/{id}/...`; only **Assessments** use the dedicated action
endpoints below.

- `GET /compliance/standards` → `[ComplianceStandard]`
- `GET /compliance/standards/{object_id}` → `ComplianceStandard`
- `GET /compliance/requirements` — filter: `standard` → `Paginated[ComplianceRequirement]`
- `GET /compliance/requirements/{object_id}` → `ComplianceRequirement`
- `GET /compliance/equations` — filter: `standard` → `Paginated[ComplianceEquation]`
- `GET /compliance/equations/{object_id}` → `ComplianceEquation`
- `GET /compliance/coverage` → `ComplianceCoverageResponse`
- `GET /compliance/gaps` → `[ComplianceGap]`
- `GET /compliance/assessments` — filter: `status` → `[ComplianceAssessment]`
- `GET /compliance/prove/{requirement}` → `ComplianceProofResponse`
- `POST /compliance/assessments/{assessment_id}/approve|reject` → `ActionResponse`
- `POST /compliance/assess` → `Job`

`ComplianceStandard { object_id, name, authority, version, jurisdiction, status? }`
`ComplianceRequirement { object_id, name, standard_object_id, clause_ref, title, requirement_text, obligation_level, status? }`
`ComplianceEquation { object_id, name, standard_object_id, requirement_object_id, clause_ref, symbol, title, expression, python_code, ast_json, variables: [ComplianceEquationVariable{ symbol, description, unit }], latex, valid, validation_note, status? }`
`ComplianceCoverageResponse { overall, standards: [ComplianceCoverageStandard{ standard_object_id, standard_name, total, satisfied, partial, coverage }] }`
`ComplianceGap { object_id, requirement_name, clause_ref, title, obligation_level, standard_object_id, standard_name }`
`ComplianceAssessment { id, requirement_object_id, requirement_name?, control_object_id?, control_name?, status, review_status, assessed_against_version, rationale }`
`ComplianceProofResponse { found, proven, term, message, requirement{}, assessments[] }`

### Jobs (async pipeline)
- `POST /jobs/scan|extract|discover-links|classify|consolidate` → `Job`
- `GET /jobs?job_type=&status=` → `Paginated[Job]`
- `GET /jobs/{job_id}` → `Job`

`Job { id, job_type, status, started_at?, completed_at?, error_message?, result_summary?, created_at? }`

## Gaps Compas works around

The previous gaps — a distinct **domains** resource, a knowledge **growth
trend**, a **change-log / recent-changes** feed, per-row **counts** in
knowledge-object list responses, and the LLM **token-usage / cost ledger**
(once CLI/MCP-only via `catalog cost-report`) — are now all served by the API
(`/governance/domains`, `/governance/growth`, `/governance/changes`, the
`relationship_count`/`evidence_count`/`mention_count` fields, and the `/cost/*`
endpoints). Likewise the graph-analytics (`/graph/health|metrics|domains` +
GEXF/GraphML exports), governance extras (`/governance/drift|owners`, per-object
history / assign-owner / flag), RDF projection (`/rdf/*`) and the extended
GraphRAG reasoning modes (`/ask/explain|impact|compare|path-reason`) are now
consumed. Compas still degrades gracefully against an older Navigate that
predates any of them (e.g. domains fall back to a `/governance/dashboard`
derivation, and the cost / analytics / RDF panels show an "unavailable" state).
