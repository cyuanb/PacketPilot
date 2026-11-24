# Contributing

Use short feat/, fix/ or docs/ branches. PRs describe the concrete problem, final behavior, validation and limitations.

Run scripts/check.ps1. PostgreSQL tests use isolated pp_test_ schemas; the test account needs schema-creation privileges.

Use synthetic documents. Never upload .env, private applications, credentials or database backups. New checks need unknown-input, wrong-version and false-pass tests.

Add migrations for schema changes. Do not edit a released migration. Verify Skill behavior through tool execution rather than prompt text matching.
