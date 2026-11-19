# AI Employee OS: Backend API Documentation

**Version:** 0.2.0 (Authentication)
**Maintainer:** Hadeed Ul Hassan (Backend APIs and Database)
**Audience:** Frontend and integration teammates

This document describes every endpoint that is currently available. New sections will be added as the Users, Customers, Tasks, and Records APIs are completed.

---

## Table of Contents

1. [Quick start](#1-quick-start)
2. [Conventions](#2-conventions)
3. [Authentication flow](#3-authentication-flow)
4. [Roles and permissions](#4-roles-and-permissions)
5. [Endpoints](#5-endpoints)
   - [GET /health](#get-health)
   - [POST /auth/register](#post-authregister)
   - [POST /auth/login](#post-authlogin)
   - [POST /auth/refresh](#post-authrefresh)
   - [GET /auth/me](#get-authme)
   - [POST /auth/change-password](#post-authchange-password)
   - [GET /auth/admin-check](#get-authadmin-check)
6. [Validation rules](#6-validation-rules)
7. [Error reference](#7-error-reference)
8. [Frontend integration guide](#8-frontend-integration-guide)
9. [Reporting a bug (500 errors)](#9-reporting-a-bug-500-errors)
10. [Changelog](#10-changelog)

---

## 1. Quick start

| Item | Value |
|---|---|
| Base URL (local) | `http://127.0.0.1:8000/api/v1` |
| Interactive docs (Swagger UI) | `http://127.0.0.1:8000/docs` |
| OpenAPI schema (JSON) | `http://127.0.0.1:8000/openapi.json` |
| Content type | `application/json` for every request with a body |
| Auth header | `Authorization: Bearer <access_token>` |

**CORS:** the backend currently allows the origins `http://localhost:3000` and `http://localhost:5173`. If your frontend runs on another origin, tell the backend owner so it can be added.

**Try it in Swagger:** open `/docs`, call `POST /auth/login`, copy the `access_token`, click **Authorize**, and paste the token **without** the word `Bearer`.

---

## 2. Conventions

| Topic | Rule |
|---|---|
| Field names | `snake_case` in requests and responses |
| IDs | UUID strings, for example `3f2b6c1e-9a4d-4b7e-8c21-0d5f6a7b8c9d` |
| Dates and times | ISO 8601 in UTC, for example `2026-11-19T10:00:00Z` |
| Emails | Trimmed and lowercased by the backend |
| Unknown JSON fields in a request | Ignored |

### Success response

```json
{
  "success": true,
  "message": "Login successful",
  "data": { }
}
```

### Error response

Every error, from every endpoint, has this shape:

```json
{
  "success": false,
  "message": "Human readable explanation",
  "code": "MACHINE_READABLE_CODE",
  "errors": [{ "field": "email", "message": "Enter a valid email address" }],
  "request_id": "a1b2c3d4e5f6"
}
```

| Key | Always present | Meaning |
|---|---|---|
| `success` | Yes | Always `false` for errors |
| `message` | Yes | Safe to show to the user |
| `code` | Yes | Use this in your code to decide what to do (do not parse `message`) |
| `errors` | Only for `VALIDATION_ERROR` | List of problems per field |
| `request_id` | Yes | Unique ID of the request. Also sent in the `X-Request-ID` response header. Include it in bug reports. |
| `debug` | Only on a development server for 500/503 | Exception name, location in the code, and call stack. Never present in production. |

**Tip:** you can send your own `X-Request-ID` header (8 to 64 characters: letters, digits, `-`, `_`) and the backend will reuse it, which lets you trace one user action across frontend and backend logs.

---

## 3. Authentication flow

The API uses **JWT bearer tokens**: a short-lived access token and a longer-lived refresh token.

| Token | Lifetime | Used for |
|---|---|---|
| `access_token` | 60 minutes (`expires_in` is in seconds) | Sent on every protected request |
| `refresh_token` | 7 days | Only sent to `POST /auth/refresh` to get new tokens |

```
Register or Login ──► access_token + refresh_token
        │
        ▼
Call protected APIs with  Authorization: Bearer <access_token>
        │
        ├── 200 OK ─► continue
        │
        └── 401 TOKEN_EXPIRED ─► POST /auth/refresh with refresh_token
                                      ├── 200 ─► store new tokens, retry the request once
                                      └── 401 ─► go to the login page
```

Important behavior:

- **Do not send the refresh token as a bearer token.** It will be rejected with `TOKEN_INVALID`. Likewise, the access token cannot be used on `/auth/refresh`.
- **The role comes from the database on every request**, not from the token. If an admin changes someone's role or deactivates them, it takes effect immediately.
- **Changing the password invalidates all tokens** issued before the change. The `change-password` response returns a fresh token pair so the current session can continue.
- **There is no logout endpoint.** To log out, delete both tokens on the client.

---

## 4. Roles and permissions

| Role | Description | Created by |
|---|---|---|
| `admin` | Full control of the company. The first user created by `/auth/register` is always an `admin`. | Register |
| `manager` | Can manage customers, tasks, and records, and see the user list | Admin (Users API, coming soon) |
| `member` | Standard staff user | Admin (Users API, coming soon) |

Every protected endpoint is scoped to the company in the user's account. A user can never see another company's data, and the company is always taken from the token, never from the request body.

| Endpoint | admin | manager | member |
|---|---|---|---|
| `GET /auth/me` | Yes | Yes | Yes |
| `POST /auth/change-password` | Yes | Yes | Yes |
| `GET /auth/admin-check` | Yes | 403 | 403 |

---

## 5. Endpoints

### GET /health

Checks that the API and the database are running. No authentication.

**Response 200**
```json
{
  "success": true,
  "message": "OK",
  "data": { "status": "healthy", "database": "connected" }
}
```

**Response 503** (database not reachable): code `DATABASE_UNAVAILABLE`.

---

### POST /auth/register

Creates a new company and its first user, who becomes the company `admin`. No authentication.

**Request body**

| Field | Type | Required | Rules |
|---|---|---|---|
| `company_name` | string | Yes | 2 to 150 characters |
| `full_name` | string | Yes | 2 to 150 characters |
| `email` | string | Yes | Valid email address, must not already be registered |
| `password` | string | Yes | See [password rules](#password-rules) |

```json
{
  "company_name": "Acme Traders",
  "full_name": "Ali Khan",
  "email": "ali@acme.com",
  "password": "Str0ngPass123"
}
```

**Response 201**
```json
{
  "success": true,
  "message": "Account created successfully",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
      "id": "6f1c2d3e-4a5b-4c6d-8e7f-9a0b1c2d3e4f",
      "company_id": "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
      "full_name": "Ali Khan",
      "email": "ali@acme.com",
      "role": "admin",
      "phone": null,
      "is_active": true,
      "last_login_at": null,
      "created_at": "2026-11-19T10:00:00Z"
    },
    "company": {
      "id": "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
      "name": "Acme Traders",
      "email": "ali@acme.com",
      "phone": null,
      "plan": "basic",
      "is_active": true
    }
  }
}
```

**Errors**

| Status | `code` | When |
|---|---|---|
| 409 | `EMAIL_ALREADY_REGISTERED` | The email already has an account |
| 422 | `VALIDATION_ERROR` | A field failed validation (see `errors`) |

**curl**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"company_name":"Acme Traders","full_name":"Ali Khan","email":"ali@acme.com","password":"Str0ngPass123"}'
```

---

### POST /auth/login

Logs in with email and password. No authentication.

**Request body**

| Field | Type | Required |
|---|---|---|
| `email` | string | Yes |
| `password` | string | Yes |

```json
{ "email": "ali@acme.com", "password": "Str0ngPass123" }
```

**Response 200**: same `data` shape as register (tokens, `user`, `company`).
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": { "id": "...", "company_id": "...", "full_name": "Ali Khan", "email": "ali@acme.com", "role": "admin", "phone": null, "is_active": true, "last_login_at": "2026-11-19T10:05:00Z", "created_at": "2026-11-19T10:00:00Z" },
    "company": { "id": "...", "name": "Acme Traders", "email": "ali@acme.com", "phone": null, "plan": "basic", "is_active": true }
  }
}
```

**Errors**

| Status | `code` | When |
|---|---|---|
| 401 | `INVALID_CREDENTIALS` | Wrong email or wrong password. The message is intentionally the same for both, so attackers cannot find out which emails exist. |
| 403 | `ACCOUNT_DISABLED` | Correct credentials, but the user is deactivated |
| 403 | `COMPANY_DISABLED` | Correct credentials, but the company is deactivated |
| 422 | `VALIDATION_ERROR` | Missing field or malformed email |

**curl**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ali@acme.com","password":"Str0ngPass123"}'
```

---

### POST /auth/refresh

Exchanges a valid refresh token for a new access token and a new refresh token. No `Authorization` header is needed.

**Request body**

| Field | Type | Required |
|---|---|---|
| `refresh_token` | string | Yes |

```json
{ "refresh_token": "eyJhbGciOiJIUzI1NiIs..." }
```

**Response 200**
```json
{
  "success": true,
  "message": "Token refreshed successfully",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

Replace both stored tokens with the new ones.

**Errors**

| Status | `code` | When | What to do |
|---|---|---|---|
| 401 | `TOKEN_EXPIRED` | Refresh token is older than 7 days | Send the user to login |
| 401 | `TOKEN_INVALID` | Malformed, wrong signature, or it is an access token | Send the user to login |
| 401 | `TOKEN_REVOKED` | Password was changed after this token was issued | Send the user to login |
| 403 | `ACCOUNT_DISABLED` / `COMPANY_DISABLED` | User or company was deactivated | Show the message |

**curl**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'
```

---

### GET /auth/me

Returns the logged-in user and their company. Requires a valid access token. Any role.

**Response 200**
```json
{
  "success": true,
  "message": "OK",
  "data": {
    "user": { "id": "...", "company_id": "...", "full_name": "Ali Khan", "email": "ali@acme.com", "role": "admin", "phone": null, "is_active": true, "last_login_at": "2026-11-19T10:05:00Z", "created_at": "2026-11-19T10:00:00Z" },
    "company": { "id": "...", "name": "Acme Traders", "email": "ali@acme.com", "phone": null, "plan": "basic", "is_active": true }
  }
}
```

**Errors:** `AUTH_REQUIRED`, `TOKEN_EXPIRED`, `TOKEN_INVALID`, `TOKEN_REVOKED` (all 401), and `ACCOUNT_DISABLED` / `COMPANY_DISABLED` (403). See the [error reference](#7-error-reference).

**curl**
```bash
curl http://127.0.0.1:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

---

### POST /auth/change-password

Changes the password of the logged-in user. Requires a valid access token. Any role.

**Request body**

| Field | Type | Required | Rules |
|---|---|---|---|
| `current_password` | string | Yes | Must match the existing password |
| `new_password` | string | Yes | See [password rules](#password-rules). Must differ from the current password. |

```json
{ "current_password": "Str0ngPass123", "new_password": "NewStr0ngPass456" }
```

**Response 200**: all older tokens stop working, so this response gives you a fresh pair. Store them.
```json
{
  "success": true,
  "message": "Password changed successfully",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

**Errors**

| Status | `code` | When |
|---|---|---|
| 400 | `INVALID_CURRENT_PASSWORD` | `current_password` is wrong. This is deliberately a **400**, not a 401, so your "401 means log out" handler does not log the user out by mistake. |
| 422 | `VALIDATION_ERROR` | New password too weak, or same as the current one |
| 401 | `AUTH_REQUIRED`, `TOKEN_EXPIRED`, `TOKEN_INVALID`, `TOKEN_REVOKED` | Token problems |

**curl**
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/change-password \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"current_password":"Str0ngPass123","new_password":"NewStr0ngPass456"}'
```

---

### GET /auth/admin-check

A small demo endpoint for testing role protection. Only users with the `admin` role get `200`. It will be removed once real admin-only endpoints exist in the Users API.

**Response 200**
```json
{
  "success": true,
  "message": "You are an admin",
  "data": { "user_id": "...", "role": "admin" }
}
```

**Errors**

| Status | `code` | When |
|---|---|---|
| 403 | `FORBIDDEN` | Logged in, but not an admin |
| 401 | token codes | Token problems |

---

## 6. Validation rules

### Password rules

| Rule | Detail |
|---|---|
| Length | 8 to 72 **bytes** (letters, digits and symbols count as 1 byte each; many emoji and non-Latin characters count as 2 to 4) |
| Content | At least one letter and at least one digit |

The 72-byte limit comes from the bcrypt algorithm used to store passwords. For the login endpoint only a non-empty value of at most 128 characters is required, because the password rules apply when a password is **set**, not when it is checked.

### Field rules

| Field | Rule |
|---|---|
| `email` | Valid format. Addresses on reserved domains such as `.test`, `.local`, or `.invalid` are rejected, so use a real-looking domain like `acme.com` in tests. |
| `company_name`, `full_name` | 2 to 150 characters, leading and trailing spaces are removed |
| `refresh_token` | Non-empty string |

---

## 7. Error reference

Use `code`, never `message`, to decide what your UI does.

| HTTP | `code` | Meaning | Suggested frontend action |
|---|---|---|---|
| 400 | `INVALID_CURRENT_PASSWORD` | Wrong current password on change-password | Show the message on that field |
| 400 | `BAD_REQUEST` | Request could not be processed | Show the message |
| 401 | `AUTH_REQUIRED` | No `Authorization: Bearer` header was sent | Go to login |
| 401 | `INVALID_CREDENTIALS` | Wrong email or password | Show the message on the login form |
| 401 | `TOKEN_EXPIRED` | Token lifetime is over | Call `/auth/refresh` once, then retry. If that fails, go to login. |
| 401 | `TOKEN_INVALID` | Token is malformed, tampered with, or the wrong type | Go to login |
| 401 | `TOKEN_REVOKED` | Password changed since the token was issued | Go to login |
| 403 | `FORBIDDEN` | The role is not allowed to do this | Show "no permission" and hide the action |
| 403 | `ACCOUNT_DISABLED` | The user is deactivated | Show the message |
| 403 | `COMPANY_DISABLED` | The company is deactivated | Show the message |
| 404 | `NOT_FOUND` | The URL or the item does not exist | Show "not found" |
| 405 | `METHOD_NOT_ALLOWED` | Wrong HTTP method for this URL | Fix the call (bug) |
| 409 | `EMAIL_ALREADY_REGISTERED` | Email already has an account | Suggest logging in |
| 422 | `VALIDATION_ERROR` | One or more fields are invalid | Show each `errors[].message` next to `errors[].field` |
| 500 | `INTERNAL_ERROR` | Unexpected backend crash | Show a generic message and the `request_id`. Report it. |
| 503 | `DATABASE_UNAVAILABLE` | Database is down | Show "try again shortly" |

### Validation error example (422)

```json
{
  "success": false,
  "message": "Validation failed",
  "code": "VALIDATION_ERROR",
  "errors": [
    { "field": "email", "message": "value is not a valid email address: An email address must have an @-sign." },
    { "field": "password", "message": "Password must contain at least one letter and one number" }
  ],
  "request_id": "a1b2c3d4e5f6"
}
```

Nested fields use dots (for example `items.0.quantity`). A field value of `request` means the problem is with the request as a whole, and `body` means the JSON could not be parsed.

---

## 8. Frontend integration guide

### Token storage

Keep the `access_token` in memory (a store or context) if you can. The `refresh_token` has to survive a page reload, so store it in `localStorage` or a secure cookie handled by your framework. Never log tokens or put them in URLs.

### Axios example with automatic refresh

```javascript
import axios from "axios";

const api = axios.create({ baseURL: "http://127.0.0.1:8000/api/v1" });

let accessToken = null;           // in memory
let refreshToken = localStorage.getItem("refresh_token");

export function saveTokens(tokens) {
  accessToken = tokens.access_token;
  refreshToken = tokens.refresh_token;
  localStorage.setItem("refresh_token", refreshToken);
}

// Attach the access token to every request
api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

// On TOKEN_EXPIRED: refresh once, then retry the original request
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const code = error.response?.data?.code;

    if (code === "TOKEN_EXPIRED" && !original._retried && refreshToken) {
      original._retried = true;
      try {
        const { data } = await axios.post(`${api.defaults.baseURL}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        saveTokens(data.data);
        original.headers.Authorization = `Bearer ${accessToken}`;
        return api(original);
      } catch {
        // refresh failed: fall through to the login redirect below
      }
    }

    if (["AUTH_REQUIRED", "TOKEN_EXPIRED", "TOKEN_INVALID", "TOKEN_REVOKED"].includes(code)) {
      accessToken = null;
      localStorage.removeItem("refresh_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;
```

### Fetch example (login)

```javascript
const res = await fetch("http://127.0.0.1:8000/api/v1/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password }),
});
const body = await res.json();

if (!body.success) {
  // body.code is the machine-readable reason, body.message is safe to display
  console.error(body.code, body.message, body.request_id);
} else {
  saveTokens(body.data);
}
```

### Checklist for the frontend

- [ ] Send `Content-Type: application/json` with every JSON body
- [ ] Send `Authorization: Bearer <access_token>` on every protected call
- [ ] Branch on `code`, not on `message` or on the HTTP status alone
- [ ] Show `errors[].message` next to the matching form field on `422`
- [ ] Treat `INVALID_CURRENT_PASSWORD` (400) as a form error, not a logout
- [ ] After `change-password`, replace both stored tokens with the new ones
- [ ] Show `request_id` in your error screen for 500 and 503 so users can report it

---

## 9. Reporting a bug (500 errors)

A `500 INTERNAL_ERROR` always means a bug on the backend, never a mistake in your request. To get it fixed fast, send the backend owner:

1. The **`request_id`** from the response body (or the `X-Request-ID` header)
2. The endpoint and method you called
3. What you sent, **without** passwords or tokens

With the `request_id`, the backend owner finds the exact crash and its full stack trace in the server logs in seconds.

If you are running the backend locally, the response also contains a `debug` object that names the exception and the line of backend code where it crashed:

```json
{
  "success": false,
  "message": "An unexpected error occurred. Please share the request_id with the backend team.",
  "code": "INTERNAL_ERROR",
  "request_id": "a1b2c3d4e5f6",
  "debug": {
    "exception": "ZeroDivisionError",
    "detail": "division by zero",
    "location": "app\\routers\\debug.py:18 in crash",
    "stack": ["app\\routers\\debug.py:18 in crash"]
  }
}
```

`debug` is only included when the server runs in development mode.

**Browser shows a "CORS error" instead of the JSON?** When the server crashes hard, some browsers hide the response and report a CORS error. Open the browser's Network tab: if the status is 500, it is a backend crash. Ask the backend owner to check the logs.

---

## 10. Changelog

| Version | Date | Changes |
|---|---|---|
| 0.2.0 | 2026-11-19 | Authentication: register, login, refresh, me, change-password, admin-check. Standard error format with `request_id`. |
| 0.1.0 | 2026-11-18 | Project setup, database schema, `GET /health` |

**Coming next:** Users, Customers, Tasks, and Records APIs. Endpoint paths and field names were shared earlier in the design document and will not change without notice.