# Roanwick

A home-services marketplace for London, starting with recurring and end-of-tenancy cleaning in south-west London. Customers see an itemised price and the cancellation terms before they pay, can ask for the same professional every visit, and can see exactly which documents we have checked. Professionals set their own hours and areas and see their commission before they accept a job. Operations and finance see, for every booking, whether it made money.

This is a working pilot build, not a prototype. The booking lifecycle runs end to end: discovery, quotation, availability, booking, assignment, payment, completion, payout and review. Payments run in sandbox mode until Stripe credentials and approvals exist, and the documents say plainly which parts are sandboxed.

## Where to start

| If you want to | Read |
| --- | --- |
| Understand the strategy, personas, scope and risks | [docs/01-product-strategy.md](docs/01-product-strategy.md) |
| See how it is built and why | [docs/02-architecture.md](docs/02-architecture.md) |
| Understand the data | [docs/03-data-model.md](docs/03-data-model.md) |
| Use or integrate with the API | [docs/04-api.md](docs/04-api.md) and [docs/openapi.json](docs/openapi.json) |
| Check the numbers behind the business | [docs/05-commercial-model.md](docs/05-commercial-model.md) |
| Know what needs a lawyer or accountant | [docs/06-compliance-and-legal.md](docs/06-compliance-and-legal.md) |
| Install, test and deploy | [docs/07-deployment.md](docs/07-deployment.md) |
| Run the pilot day to day | [docs/08-admin-guide.md](docs/08-admin-guide.md) |
| See what is done, what is not, and what blocks launch | [docs/09-status-and-readiness.md](docs/09-status-and-readiness.md) |

## Quick start

```
# API
cd backend && python3.13 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
cp .env.example .env     # set DATABASE_URL and JWT_SECRET
alembic upgrade head
SEED_DEMO=1 SEED_ADMIN_PASSWORD='a-long-demo-password' python -m app.seed
uvicorn app.main:app --port 8000

# Web (second terminal)
cd web && npm install && npm run dev
```

Open http://localhost:3000. The API documentation is at http://localhost:8000/api/docs. Full instructions, including Docker, are in the deployment guide.

## Layout

```
backend/   FastAPI service: models, services, routers, migrations, tests
web/       Next.js app: customer site, professional portal, admin console, browser tests
docs/      Strategy, architecture, data model, API, commercial model, compliance, operations
docker-compose.yml, .env.example, .github/workflows/ci.yml
```

## Stack

Next.js 16, React 19, TypeScript and Tailwind CSS 4 on the front. Python 3.13, FastAPI, SQLAlchemy 2 and Alembic on the back, with PostgreSQL 16. Argon2id and JWT for authentication. Stripe Connect behind a provider interface, with a credential-free sandbox. Docker, GitHub Actions, structured JSON logs and optional Sentry.
