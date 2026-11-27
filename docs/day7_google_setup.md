# Day 7: Connect your real Gmail (about 10 minutes, free)

The app works without this (sample emails). Do this only to read your own Gmail.

1. Go to https://console.cloud.google.com and create a project (e.g. "AI Email Assistant").
2. **APIs & Services → Library**: search "Gmail API" and click **Enable**.
3. **Google Auth Platform** (OAuth consent screen):
   - Branding: app name, your email as support/contact.
   - Audience: **External**, publishing status **Testing**. Under **Test users** add your own Gmail address.
   - Data Access: add the scopes `https://www.googleapis.com/auth/gmail.readonly` and (for Day 8 sending) `https://www.googleapis.com/auth/gmail.send`.
4. **Clients → Create client**: type **Web application**. Under *Authorized redirect URIs* add exactly
   `http://localhost:8000/auth/google/callback`.
5. Copy the client ID and secret into `.env` (see `.env.example`):
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   ```
6. Restart the backend, open http://localhost:3000, go to **Connect → Connect Gmail (read-only)**.
7. Google shows "Google hasn't verified this app": click **Advanced → Continue**, keep the read-email box ticked.

## Good to know
- Testing mode: only listed test users can sign in, and access expires after **7 days**; use **Reconnect** then.
- The app first asks for read-only access. Send permission is requested only when you click **Allow sending** (Day 8).
- Tokens are stored in `data/google.token.json` (gitignored, never shown in the app). **Disconnect** deletes them and revokes access at Google.
- Error "Gmail API has not been used…": enable the Gmail API (step 2). Error `redirect_uri_mismatch`: the URI in step 4 must match exactly.
