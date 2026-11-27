# AI Employee OS Backend

FastAPI backend for authentication, users, customers, tasks, and related records.

## Run locally

1. Create the environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

2. The local template uses `APP_ENV=development`. Edit `.env` and set
   `POSTGRES_PASSWORD`, `DATABASE_URL`, and a strong `SECRET_KEY` (at least 32
   characters). Generate the key with:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. Install dependencies and start PostgreSQL:

   ```powershell
   py -3.12 -m venv venv
   .\venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   docker compose up -d db
   ```

4. Apply migrations and run the API:

   ```powershell
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

The API is available at `http://127.0.0.1:8000/api/v1`. Swagger UI is at
`http://127.0.0.1:8000/docs`.

## Environment configuration

This repository is a Python/FastAPI backend. Use `APP_ENV`, not `NODE_ENV`;
`NODE_ENV` is not read by this application.

| Variable | Development | Production |
|---|---|---|
| `APP_ENV` | `development` | `production` |
| `DATABASE_URL` | Local PostgreSQL from `.env.example` | Production PostgreSQL connection string |
| `SECRET_KEY` | Locally generated, at least 32 characters | Unique secret stored in the deployment platform |
| `CORS_ORIGINS` | `http://localhost:3000` and `http://localhost:5173` | Exact production frontend origin(s) |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` | Used by local Docker Compose | Not needed by the API when using a managed database |

`APP_ENV=development` enables the debug router and detailed debug information
for server errors. `APP_ENV=production` disables those development-only
features. Set the production values from
[.env.production.example](./.env.production.example) in the hosting platform's
environment-variable settings; do not deploy that template or commit actual
secrets. `DATABASE_URL` and `SECRET_KEY` are required in both environments.

## Test

```powershell
python -m pytest -q
```

Stop the database container with `docker compose down`.
