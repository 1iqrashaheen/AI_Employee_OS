# AI Employee OS Backend

FastAPI backend for authentication, users, customers, tasks, and related records.

## Run locally

1. Create the environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Edit `.env` and set `POSTGRES_PASSWORD`, `DATABASE_URL`, and a strong `SECRET_KEY`
   (at least 32 characters).

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

## Test

```powershell
python -m pytest -q
```

Stop the database container with `docker compose down`.
