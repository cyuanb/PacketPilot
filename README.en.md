# PacketPilot

An open-source, self-hosted document preflight workspace. Current version: 0.6.0.

Import a notice, review extracted requirements, upload documents, inspect evidence-backed findings, amend materials, and export a checklist.

Manage distinct person and organization profiles in an owner-controlled workspace, then associate applicants, recommenders and representatives with a case. Names do not merge identities; profile changes mark linked cases for review. Profile attributes do not automatically become confirmed case facts, and subject-aware field comparison is not yet implemented.

The independent document library accepts uploads before a case exists. Organize an inbox by subject and category, inspect originals and immutable versions, and pin a selected revision to each case. Updates require an explicit choice per case. Removing case materials retains library originals; permanent library deletion is not yet available.

Starter workflows cover education exchange, job applications, onboarding, business entry and supplier intake. They suggest roles and context, not official requirements. A source-backed form creates requirement drafts; a model-free check preserves unknown semantic findings. Issues track requested/submitted amendments, resolve only from current checks or valid manual attestations, and reopen when rechecks find a problem. Exceptions never change the check verdict.

[中文说明](README.md) · [Configuration](docs/configuration.md) · [Architecture](docs/architecture.md) · [Testing](docs/testing.md)

## Local setup

Use nvm-managed Node, Python 3.11+ and PostgreSQL. Copy .env.example to .env and configure the database and compatible tool-calling model.

Run scripts/setup.ps1, then scripts/start.ps1. Open http://localhost:8010 and sign in with the credentials from local .env. Stop with scripts/stop.ps1.

Native Windows processes are supported; no Docker is required. Model providers and hosting resources may charge separately.

## Boundaries

Files remain local, while necessary excerpts are sent to the configured model service. Optional local CPU OCR supports clear printed Chinese/English images and scanned PDFs after explicit model provisioning. Authenticity verification and automated submission are not provided. Unknown inputs require review. The included example uses synthetic data.

Apache-2.0. Never include private documents or credentials in public issues.

## Material review and delivery

Frozen ZIP packets include selected original files (or explicitly chosen derived text), ordered paths, a contents index and SHA256 manifest. Downloading does not send a submission: users separately record delivery and acknowledgements. Changes to current inputs are shown without rewriting frozen packets.

Page/field corrections and repeated OCR append parse revisions. Evidence can open the historical parser projection. Explicit subject/slot/type assignments support requirement groups, independent quantities, original/translation pairs and date windows. The visual editor offers dry runs and source-conflict handling. Nine starter scenarios provide roles and output suggestions, not official institutional requirements.

Run `.venv\Scripts\python.exe scripts/setup_ocr.py` to provision checksum-pinned PP-OCRv4 weights. Recognition runs on the CPU without network access or implicit model downloads. See [scope and usage](docs/material-review.md).
