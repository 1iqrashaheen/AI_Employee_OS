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

## 7. Logout and password reset

### Logout

Send `POST /auth/logout` with the current access token.

Expected: `200`. The old access and refresh tokens are revoked immediately.

### Forgot password

Send `POST /auth/forgot-password`:

```json
{
  "email": "admin@example.com"
}
```

The response is deliberately the same whether or not the account exists.
In development, `data.reset_token` contains the reset token.
Email delivery is not implemented yet.

### Reset password

Send `POST /auth/reset-password`:

```json
{
  "reset_token": "<token>",
  "new_password": "N3wStr0ngPass"
}
```

Expected: `200`. Existing tokens are revoked and the user must log in again.

## 8. Company management

Send `GET /companies/me` with any authenticated role.

Send `PATCH /companies/me` with an admin access token:

```json
{
  "name": "Updated Company",
  "phone": "+923001234567",
  "plan": "pro"
}
```

Expected: `200`. Members and managers receive `403`.

## 9. Records

Create a record after creating a customer:

```json
{
  "type": "invoice",
  "customer_id": "<customer_uuid>",
  "task_id": "<optional_task_uuid>",
  "title": "Invoice for consulting",
  "reference_no": "INV-2026-001",
  "status": "pending",
  "amount": "1250.00",
  "currency": "USD",
  "data": {
    "line_items": [
      {"description": "Consulting", "amount": 1250}
    ]
  }
}
```

Useful requests:

- `GET /records?type=invoice`
- `GET /records?customer_id=<customer_uuid>`
- `GET /records?type=invoice&customer_id=<customer_uuid>`
- `PATCH /records/<record_uuid>` with only the fields to change
- `DELETE /records/<record_uuid>`

The `task_id` must belong to the selected customer and the same company.
