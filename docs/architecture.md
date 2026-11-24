# Architecture

## Runtime

The React/TypeScript browser application calls a same-origin FastAPI service. A separate Python Worker claims durable PostgreSQL jobs. Private files remain outside the static web root.

API and Worker share domain services and transactional state. The Agent uses restricted tools; it has no arbitrary shell, filesystem or SQL tool.

## Documents and review

Materials and requirement sets are versioned. Each review has an input snapshot. Updating materials or confirmed facts invalidates earlier findings. User confirmation is separate from machine verification.

Evidence identifies its document version, page or paragraph and source excerpt. Anchoring an excerpt does not prove that every semantic conclusion is correct.

## Tasks and events

Jobs use short transactions, leases, fencing values and idempotent writes. Execution is at least once. Persistent SSE events support progress replay; browser disconnection does not cancel a job.

Cancellation is cooperative. An inference request may finish before cancellation takes effect.

## Access and storage

Cookie sessions are HttpOnly and SameSite Strict. Resources are authorized through their owning case. Upload filenames do not become storage paths. Runtime configuration is never sent to the browser.

Parser subprocesses have time and output limits, but are not a hardened sandbox. External deployment requires an appropriate TLS and access configuration.
