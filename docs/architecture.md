# Architecture

## Runtime

The React/TypeScript browser application calls a same-origin FastAPI service. A separate Python Worker claims durable PostgreSQL jobs. Private files remain outside the static web root.

API and Worker share domain services and transactional state. The Agent uses restricted tools; it has no arbitrary shell, filesystem or SQL tool.

## Backend modules

`app.main` assembles the FastAPI application with `create_app()`. API routers are registered before the optional static frontend mount.

| Module | Responsibility |
| --- | --- |
| `app.api` | Identity, system, case, document, requirement, run and report endpoints; shared authentication and HTTP boundary handling |
| `app.application` | Ownership queries, revisions, document projections, requirement persistence, run snapshots, idempotent enqueueing and current reports |
| `app.review` | Pure applicability evaluation, evidence anchoring, field coverage, material matching, deterministic checks and readiness aggregation |
| `app.agent` / `app.worker` | Restricted model tools and durable job execution |
| `app.models` / `app.db` | Persistence models and database sessions |

Review modules depend on shared schemas and other review modules, without database, HTTP or model-service access. API routes own request transactions; application services are also used by the worker and agent. `app.domain` and `app.services` preserve their existing import names as compatibility facades.

Each SSE polling iteration opens a short-lived session through `app.db.SessionLocal`; it does not reuse the request session for long-lived streaming. Authentication and case ownership are checked before the stream opens.

## Documents and review

Materials and requirement sets are versioned. Each review has an input snapshot. Updating materials or confirmed facts invalidates earlier findings. User confirmation is separate from machine verification.

Evidence identifies its document version, page or paragraph and source excerpt. Anchoring an excerpt does not prove that every semantic conclusion is correct.

## Tasks and events

Jobs use short transactions, leases, fencing values and idempotent writes. Execution is at least once. Persistent SSE events support progress replay; browser disconnection does not cancel a job.

Cancellation is cooperative. An inference request may finish before cancellation takes effect.

## Access and storage

Cookie sessions are HttpOnly and SameSite Strict. Resources are authorized through their owning case. Upload filenames do not become storage paths. Runtime configuration is never sent to the browser.

Parser subprocesses have time and output limits, but are not a hardened sandbox. External deployment requires an appropriate TLS and access configuration.

## Readiness contract

Results include engine_version, rules_id, a canonical requirement fingerprint and coverage summary. Aggregation validates the expected result set, duplicates, applicability and verification method.

Field/date coverage is recorded for each candidate material. Presence checks use limited structural profiles and preserve unknown results for unsupported layouts. Legacy or incomplete results cannot be treated as current readiness.
