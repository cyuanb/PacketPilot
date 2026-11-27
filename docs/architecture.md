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

## Frontend modules and state

`App.tsx` handles startup, the session gate and the render error boundary. `app/AuthenticatedWorkspace` owns a session-local query cache and notifications. Its child workspace is keyed by the selected case (or list view), so switching cases releases subscriptions and resets dialogs and drafts. Tabs within the same case preserve that case's editing state.

| Module | Responsibility |
| --- | --- |
| `api/client.ts`, `api/types.ts` | Same-origin HTTP transport and response types |
| `app/routes.ts`, `app/useWorkspaceRoute.ts` | Explicit URL parsing and browser history synchronization |
| `app/queryClient.ts` | Resource-keyed cache, request deduplication, cancellation and fencing of superseded responses |
| `app/useWorkspace.ts`, `app/useEditors.ts` | Workspace action coordination and scoped editing state |
| `features/cases`, `documents`, `requirements`, `review`, `chat`, `runs`, `settings`, `identity` | Feature views, editors and specialized hooks |
| `components` | Shared dialogs, status badges, empty views and the render error boundary |

Routes use `#/cases`, `#/archive`, and `#/cases/{id}/{tab}`. Tabs are `overview`, `documents`, `rules`, `chat` and `history`. Existing `#case/{id}` links normalize to the overview route without adding a history entry. User navigation adds history entries, allowing back/forward navigation and refresh to restore the selected view.

Mutations force fresh list/detail reads or publish their returned case revision. Superseded responses cannot overwrite newer cached data. Logout clears the session cache. Run subscriptions clean up EventSource connections and polling timers when a view leaves; a terminal event forces a fresh read to supersede an earlier poll. These browser mechanisms supplement server-side ownership and revision checks.

Request failures stay visible with retry controls or within the active editor. Unexpected rendering failures show a reload action; they do not delete stored materials or cancel background work.

## Independent document library

Assets belong to a workspace and may have a subject; assets without a subject form the inbox. Asset metadata has an optimistic revision, while each asset revision captures its own filename, original blob and optional text snapshot. Blob hashes identify original bytes, not the identity of an applicant or the meaning of corrected text. Equal hashes and sizes produce workspace-scoped duplicate hints without suppressing a submission.

Asset and blob ownership are protected by composite foreign keys. PostgreSQL triggers reject updates to persisted blobs and asset revisions. Application writes append versions under an asset lock; stale metadata or version requests are rejected. Upload failures roll back database changes and remove the staged file.

Library listings, version catalogs and usage queries defer original bytes and text snapshots; full content is loaded only for an explicit preview or download. Cleanup checks database persistence after a failed commit so a lost acknowledgement cannot delete an already committed original. If persistence cannot be confirmed, the file is retained for recovery.

Migration `0003` groups existing document versions by workspace and logical material, preserving their identifiers, original hashes and text snapshots. Pasted originals are reconstructed only when their bytes match the recorded hash and size. An unavailable original is not fabricated from corrected text. Contradictory metadata for a shared file aborts the migration. The migration performs no file moves or rewrites and refuses a downgrade that would discard library data.

CaseDocumentLink pins each case-local document version to an asset revision. Composite foreign keys enforce case, document, revision and workspace agreement. Migration `0004` backfills these links without changing existing inputs. Selecting another revision creates a new case document version; accepting an update affects only that case. Corrections append to the linked asset while other cases retain their previous selections.

Case parsing updates its own derived text; library snapshots remain immutable. Removing a case/document retains library originals. Library metadata and version updates do not automatically change case inputs. Original downloads use the pinned blob even when the case displays corrected text.

## Scenario and amendment workflow

Five declarative starter scenarios provide roles, background fields, material suggestions and stages. A case snapshots the chosen configuration at creation. These suggestions are not requirements: enabled rules must cite case-owned source documents. Existing cases remain generic; migration does not infer a scenario or applicant identity.

The explicit rules-only check completes deterministic checks without a model call and leaves semantic findings unknown. Both current complete background checks and rules-only checks synchronize issues. Issues are keyed by case and requirement, with optimistic revisions and an event history. Resolution depends on current complete findings, non-applicability or a version-bound manual attestation. Workflow actions cannot set resolved directly or alter verdicts. Rechecks can reopen issues; exceptions are bound to the current check and do not modify readiness. Incomplete/stale checks never close issues.

## Documents and review

Materials and requirement sets are versioned. Each review has an input snapshot. Updating materials or confirmed facts invalidates earlier findings. User confirmation is separate from machine verification.

Evidence identifies its document version, page or paragraph and source excerpt. Anchoring an excerpt does not prove that every semantic conclusion is correct.

## Tasks and events

Jobs use short transactions, leases, fencing values and idempotent writes. Execution is at least once. Persistent SSE events support progress replay; browser disconnection does not cancel a job.

Cancellation is cooperative. An inference request may finish before cancellation takes effect.

## Access and storage

Each account owns one workspace and an owner membership. Cases retain their original owner and carry a workspace ID. Subject profiles have independent IDs, a fixed person/organization kind and an optimistic revision; names are not unique identity keys. Case-subject roles use composite foreign keys so a case and its linked profile must belong to the same workspace. Owner and membership checks apply to case access, including documents, runs and event streams through their owning case.

Workspace provisioning serializes on the account row. Profile and role mutations serialize on the workspace, then lock affected cases in a stable order. Editing a linked profile bumps those case revisions; earlier run snapshots retain their original subject identities. Contact attributes are stored in profiles and are not automatically included in model context or confirmed case facts.

Migration `0002` creates owner workspaces and memberships and backfills existing cases without inferring applicant identities. Existing document contents, versions and run snapshots are preserved. A rollback refuses to silently discard profiles or edited workspace names.

Cookie sessions are HttpOnly and SameSite Strict. Resources are authorized through their owning case. Upload filenames do not become storage paths. Runtime configuration is never sent to the browser.

Parser subprocesses have time and output limits, but are not a hardened sandbox. External deployment requires an appropriate TLS and access configuration.

## Readiness contract

Results include engine_version, rules_id, a canonical requirement fingerprint and coverage summary. Aggregation validates the expected result set, duplicates, applicability and verification method.

Field/date coverage is recorded for each candidate material. Presence checks use limited structural profiles and preserve unknown results for unsupported layouts. Legacy or incomplete results cannot be treated as current readiness.
