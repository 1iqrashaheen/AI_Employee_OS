# AI Employee OS - Quick Manual Testing

Use Postman or Thunder Client against `http://127.0.0.1:8000/api/v1`.
The interactive equivalent is available at `http://127.0.0.1:8000/docs`.

## 1. Start and verify

1. Start PostgreSQL with `docker compose up -d db`.
2. Run migrations with `alembic upgrade head`.
3. Run `uvicorn app.main:app --reload`.
4. Send `GET /health` with no authentication.

Expected: `200` and `data.status` is `healthy`.

## 2. Register and authenticate

Send `POST /auth/register`:

```json
{
  "company_name": "Manual Test Co",
  "full_name": "Test Admin",
  "email": "admin@example.com",
  "password": "Str0ngPass123"
}
```

Save `access_token` and `refresh_token` from the `data` object.

Manual repeatable checks:

- Register the same email again: expected `409` `CUSTOMER_EMAIL_EXISTS` or `EMAIL_EXISTS`
- Send `GET /auth/me` without a token: expected `401`
- Send `GET /auth/me` with `Authorization: Bearer <access_token>`: expected `200`
- Send `POST /auth/refresh` with the refresh token: expected a new access/refresh pair

## 3. Test users

With the admin access token:

1. `POST /users` to create a member.
2. `GET /users` to list users.
3. `GET /users/directory` to verify assignee names.
4. `GET /users/{user_id}` to fetch a member.
5. `PATCH /users/{user_id}` to update that member.

Expected: members cannot create or deactivate users and receive `403`.

## 4. Test customers

Send `POST /customers`:

```json
{
  "name": "Test Customer",
  "email": "customer@example.com",
  "phone": "+923001234567",
  "stage": "lead",
  "source": "manual"
}
```

Then test:

- `GET /customers?search=Test`
- `PATCH /customers/{customer_id}` with `"stage": "qualified"`
- `GET /customers/{customer_id}/timeline`
- `DELETE /customers/{customer_id}`
- `GET /customers/{customer_id}` after deletion

Expected: create `201`, list/update/timeline `200`, delete `200`, and fetch after
deletion `404`.

## 5. Test tasks

Send `POST /tasks`:

```json
{
  "title": "Follow up with customer",
  "description": "Call the customer and record the outcome",
  "priority": "high",
  "status": "todo",
  "customer_id": "<customer_uuid>",
  "assignee_id": "<member_uuid>",
  "due_at": "2026-11-30T12:00:00Z"
}
```

Then test:

- `GET /tasks?mine=true`
- `GET /tasks?status=todo&priority=high`
- `PATCH /tasks/{task_id}` with `"status": "done"`
- `DELETE /tasks/{task_id}`

Expected: done tasks no longer appear in the `overdue=true` filter.

## 6. Negative and error checks

- Send a request with an unknown JSON field: expected `422`.
- Send an invalid UUID path: expected `422`.
- Send `Authorization: Bearer not-a-token`: expected `401`.
- Use an inactive user or change password, then reuse its old access token:
  expected `401`.
- Stop PostgreSQL and call `GET /health`: expected `503` with
  `DATABASE_UNAVAILABLE`.

In Postman or Thunder Client, save the `request_id` header/value for any `500`
or `503` and include it in backend bug reports.
