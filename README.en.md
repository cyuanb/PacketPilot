# PacketPilot

An open-source, self-hosted document preflight workspace. Current version: 0.1.1.

Import a notice, review extracted requirements, upload documents, inspect evidence-backed findings, amend materials, and export a checklist.

Manage distinct person and organization profiles in an owner-controlled workspace, then associate applicants, recommenders and representatives with a case. Names do not merge identities; profile changes mark linked cases for review. Profile attributes do not automatically become confirmed case facts, and subject-aware field comparison is not yet implemented.

[中文说明](README.md) · [Configuration](docs/configuration.md) · [Architecture](docs/architecture.md) · [Testing](docs/testing.md)

## Local setup

Use nvm-managed Node, Python 3.11+ and PostgreSQL. Copy .env.example to .env and configure the database and compatible tool-calling model.

Run scripts/setup.ps1, then scripts/start.ps1. Open http://localhost:8010 and sign in with the credentials from local .env. Stop with scripts/stop.ps1.

Native Windows processes are supported; no Docker is required. Model providers and hosting resources may charge separately.

## Boundaries

Files remain local, while necessary excerpts are sent to the configured model service. OCR, authenticity verification and automated application submission are not implemented. Unknown inputs require review. The included example uses synthetic data.

Apache-2.0. Never include private documents or credentials in public issues.
