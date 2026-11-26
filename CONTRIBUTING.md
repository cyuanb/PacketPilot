# Contributing

Use short feat/, fix/ or docs/ branches. PRs describe the concrete problem, final behavior, validation and limitations.

Run scripts/check.ps1. PostgreSQL tests use isolated pp_test_ schemas; the test account needs schema-creation privileges.

Use synthetic documents. Never upload .env, private applications, credentials or database backups. New checks need unknown-input, wrong-version and false-pass tests.

Keep public documentation focused on current product usage, configuration, architecture and supported behavior. Internal research, plans, execution records, raw evaluation output and commercial strategy do not belong in this repository. Commit messages should describe actual changes without internal planning identifiers.

Add migrations for schema changes. Do not edit a released migration. Verify Skill behavior through tool execution rather than prompt text matching.
