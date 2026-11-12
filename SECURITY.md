# Security policy

## Reporting a vulnerability

Please **do not open a public issue**. Report it privately through GitHub: **Security → Report a vulnerability** on this repository. Include the affected component, steps to reproduce and the impact you expect.

You can expect an acknowledgement within 7 days. Once a fix is available, the report is disclosed together with it.

## Supported versions

Only the latest commit on `main` receives fixes.

## Security model

This project is designed to run **locally** with Docker Compose and the user's own API keys. Before reporting, please keep its intended scope in mind:

- **No user authentication, by design.** There is a single implicit user. Ports bind to `127.0.0.1`. Exposing the app to a network is outside the supported setup; if you do it, put it behind a reverse proxy with HTTPS and set `ALLOWED_IPS`.
- **Secrets live only in `.env`**, which is git-ignored. `.env.example` documents the variables without values.
- **PostgreSQL Row-Level Security is enforced** (`FORCE ROW LEVEL SECURITY`, non-owner app role). Migrations run with a separate owner role.
- **LLM spend is capped** per evaluation (6 calls / 20k input tokens).
- **Uploads** are limited to 3 files × 5 MB and an allow-list of types (PDF, DOCX, XLSX, CSV, TXT, images).

In scope, for example: RLS bypasses, SQL injection, secrets leaking into logs or responses, path traversal in uploads, prompt-injection paths that escape the spend caps, or bypassing the IP allow-list when it is configured.
