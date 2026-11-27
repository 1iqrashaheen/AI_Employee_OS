# AI Employee OS – Frontend & Dashboard

**Owner:** Saud Masood (Task #3 – Frontend and Dashboard)

A responsive Next.js + React + TypeScript + Tailwind CSS frontend foundation for the AI Employee OS internship project.

## 1. Requirements

- Node.js 20.9 or newer
- npm
- Hadeed's FastAPI backend running locally for live authentication/API checks

## 2. Setup

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000.

Set `NEXT_PUBLIC_API_BASE_URL` in `.env.local` to the backend API base URL. The default is `http://127.0.0.1:8000/api/v1` as specified in the supplied API documentation.

## 3. Implemented backend integration

The frontend integrates the endpoints fully described in the supplied `API_DOCUMENTATION.md`:

- `GET /health`
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `GET /auth/me`
- `POST /auth/change-password`

Authentication follows the backend guide: access token held in memory, refresh token persisted in local storage, bearer authorization for protected requests, one retry after `TOKEN_EXPIRED`, and handling of structured API errors. The frontend does not log tokens.

**Logout note:** the supplied document lists `POST /auth/logout` in its table of contents and changelog but does not provide its request/response contract in the endpoint section. The UI attempts the endpoint and always clears the local session. Confirm the final route contract with Hadeed before relying on server-side token revocation.

## 4. Frontend pages

- `/login` – login form
- `/register` – company and first-admin registration
- `/dashboard` – responsive dashboard, account/company snapshot, backend health status, module navigation
- `/dashboard/assistant`
- `/dashboard/crm`
- `/dashboard/email`
- `/dashboard/whatsapp`
- `/dashboard/tasks`
- `/dashboard/invoices`
- `/dashboard/quotations`
- `/dashboard/meetings`
- `/dashboard/documents`
- `/dashboard/reports`
- `/dashboard/automation`

The module pages provide a consistent navigation and UI foundation. Customer, task, invoice, CRM, email, WhatsApp and other module-specific data APIs are not present in the supplied backend document, so those pages clearly show integration-pending states rather than inventing endpoints or pretending to save live records.

## 5. Backend requirements

The backend documentation states that CORS currently allows `http://localhost:3000` and `http://localhost:5173`. Run the frontend on port 3000 unless Hadeed updates CORS.

## 6. Build

```bash
npm run build
```

## 7. GitHub

Create/use your assigned feature branch. Do not push directly to `main`. Commit the complete frontend and share the branch with Arayash for final integration.

## 8. Known integration dependencies

1. Hadeed to publish the Customers, Tasks and Records CRUD endpoints and their request/response schemas.
2. Confirm the exact logout and password-reset/company-profile endpoint contracts if these are to be surfaced in the UI.
3. Each AI module owner to provide their module's service/API contract before live module functionality can be connected.
