# Installation, testing and deployment

## Requirements

Python 3.13, Node.js 22, PostgreSQL 16 with the `btree_gist` and `citext` extensions (both ship with the standard contrib package), and optionally Docker.

## Run it locally without Docker

Create a database and role.

```
createuser --createdb --pwprompt roanwick
createdb --owner roanwick roanwick
createdb --owner roanwick roanwick_test
```

Start the API.

```
cd backend
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env              # then edit: DATABASE_URL, JWT_SECRET (32+ random characters)
alembic upgrade head              # creates the schema and the required extensions
SEED_DEMO=1 SEED_ADMIN_PASSWORD='choose-a-long-password' python -m app.seed
uvicorn app.main:app --reload --port 8000
```

The seed command is safe to repeat, and is also how new reference data (such as bundles) reaches an existing installation after an upgrade, so run it after `alembic upgrade head` on every release. Without `SEED_DEMO=1` it loads only reference data: roles, permissions, business settings, feature flags, the two launch services and the seven pilot postcode districts. With it, it also creates demo staff (`admin@`, `ops@`, `finance@`, `support@roanwick.example`), one customer (`priya@example.com`), three approved professionals (`elena@`, `tomasz@`, `amara@example.com`) with availability and in-date documents, and two promotion codes (`WELCOME10`, `SPRING5`). All demo accounts use the password you supply. Never seed demo data in production.

Start the web app in a second terminal.

```
cd web
cp .env.example .env.local        # API_URL=http://localhost:8000
npm install
npm run dev                       # or: npm run build && npm run start
```

Open http://localhost:3000 for the website and http://localhost:8000/api/docs for the API. Staff sign in at /login and are taken to /admin.

Run the scheduled jobs by hand with `python -m app.jobs`, or press "Run jobs now" under Settings in the admin console. In production they run every five minutes.

## Run it with Docker

```
cp .env.example .env              # set POSTGRES_PASSWORD and JWT_SECRET
docker compose up --build
```

The stack starts PostgreSQL, runs migrations and seeding once, then starts the API, the job runner and the web app. The Dockerfiles and compose file are syntactically valid (`docker compose config`), but the images have not been built in the environment this repository was developed in, because it had no container daemon. Build them once on a Docker host before relying on them.

## Tests

```
cd backend && pytest -q                       # 73 tests, against a real PostgreSQL test database
cd web && npm run typecheck && npm test       # type check and 8 unit tests
cd web && npm run build && npm run start &    # then, with the API running and demo data seeded:
cd web && E2E_DEMO_PASSWORD='the demo password' npm run e2e   # 49 browser tests
```

The backend tests rebuild the `roanwick_test` schema from the migrations on every run, so they also prove that a clean install works. They need `DATABASE_URL` or `TEST_DATABASE_URL` to point at a database the role may drop and recreate the `public` schema in. Never point it at real data.

What the suites cover: registration and sign-in (validation, lockout, refresh rotation and reuse, password reset, erasure); role and data isolation; itemised pricing; slot search; double-booking (sequential, two professionals, database constraint, and an eight-thread race); idempotent booking and payment; hold expiry; declined and retried payments; webhook signature, duplicate delivery, retry after failure, amount mismatch and late payment; cancellation tiers; rescheduling; re-matching and manual assignment; job progress; messaging; reviews, favourites, complaints and refund requests; onboarding, document review and the verification gate; document expiry removing a professional from availability; regulated category gating; permissions and audit; commission, payout hold and release; the finance report definitions; promotions and referral credit; recurring plans; scheduled jobs; token forgery; bundles and their discount accounting; creating services; two-step verification (including the RFC 6238 test vector and enforcement); quality reviews; clawback netting; erasure of professional documents; retention. The browser suite covers the full customer journey, staff and professional areas, accessibility scans of 17 pages and screens, mobile layout at 375px and keyboard access.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request. The backend job lints, applies the migrations to an empty database, runs `alembic check` to catch drift and runs the tests. The web job type-checks, runs unit tests and builds. The end-to-end job starts both servers against a seeded database and runs the browser suite.

## Deploying to production

These steps assume AWS, with Azure equivalents in brackets.

1. Provision PostgreSQL 16 (RDS, Azure Flexible Server) with automated backups and point-in-time recovery. Create the extensions as a privileged user: `create extension btree_gist; create extension citext;`.
2. Create an object storage bucket (S3, Blob) with public access blocked and server-side encryption. Production storage code must replace `app/services/storage.py` (two functions: `save_upload`, `read_file`) with calls to it. Local disk is not suitable for more than one API instance.
3. Store secrets in Secrets Manager (Key Vault): `JWT_SECRET`, `DATABASE_URL`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, SMTP or provider credentials.
4. Build and push the two images. Run `alembic upgrade head` and `python -m app.seed` as a one-off task before each release.
5. Run the API with at least two tasks behind a load balancer using `/ready` as the health check, the web container behind the same domain (route `/api/*` to the API directly if you prefer, and keep the browser on one origin), and one job runner task.
6. Set `ENV=production`, `PUBLIC_WEB_URL`, and `CORS_ORIGINS`. The API refuses to start in production with the development JWT secret.
7. Point the Stripe webhook at `https://your-domain/api/v1/webhooks/payments` and set `PAYMENT_PROVIDER=stripe` only after test-mode verification (see the readiness checklist).
8. Add alarms for 5xx rate, failed webhook events, a stalled job runner, queued notifications older than ten minutes, and database storage.

Regenerate the API contract after route changes:

```
cd backend && python -c "import json; from app.main import app; json.dump(app.openapi(), open('../docs/openapi.json','w'), indent=1)"
```

## Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| API exits with "JWT_SECRET must be set" | `ENV=production` with the default secret. Set a 32+ character random value. |
| `alembic upgrade` fails on `btree_gist` or `citext` | The role cannot create extensions. Create them as a superuser first. |
| `alembic check` reports differences | Models changed without a migration. Generate one with `alembic revision --autogenerate`. |
| Web shows "Something went wrong on our side" after a booking attempt | Check the API log for the `request_id` in the error. In development, a database created from an earlier version of the migration can have narrower columns than the models. Rebuild it from the migrations. |
| Browser calls fail with 404 on `/api/...` | The web server was built with the wrong `API_URL` (it is read at build time). Rebuild with the right value. |
| Sign-in works but a reload signs you out | The refresh cookie is not reaching the API. Confirm the browser talks to the web origin (not the API directly) and that `ENV=production` is only used over HTTPS, because the cookie is `Secure` there. |
| No slots appear for a professional | Check they are approved, have availability rules, cover the district, offer the service, and that every mandatory document is approved and unexpired (Admin, Professionals). |
| A paid booking is stuck at "awaiting confirmation" | The professional has auto-accept off. The acceptance job re-matches after `provider_acceptance_hours`. Run jobs from Settings, or assign manually. |
| Payments stay "requires payment" in Stripe mode | The webhook is not reaching `/api/v1/webhooks/payments` or the signing secret is wrong. Failed events are listed in `webhook_events`. |
| Emails are not sent | `EMAIL_PROVIDER=console` only logs. Configure SMTP and make sure the job runner is running. |
| Browser tests fail on first run | The demo data must be seeded and the API and web servers running. Set `E2E_DEMO_PASSWORD` to the seed password. |
