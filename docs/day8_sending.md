# Day 8: Approved sending through Gmail

## How sending works
1. Write or generate a draft, edit it, then **Approve** it (this fixes the exact recipient, subject and text).
2. Click **Send email…**. A window shows From, To, Subject and the full text. Nothing is sent until you press **Yes, send it** (Cancel or Esc sends nothing).
3. The backend re-checks that the draft is approved and unchanged, then sends one email through the Gmail API as your own account.

## Three modes (shown as a pill in the header)
| Pill | Meaning |
|---|---|
| Demo sending | No Gmail connected. Send only marks the draft as sent. Nothing is delivered (clearly labeled everywhere). |
| Sending not allowed yet | Gmail connected for reading only. Click **Allow sending**; Google asks for the extra permission. The approved draft stays saved. |
| Live sending | Sending is allowed. Approved drafts are really delivered. |

## Safety rules (all enforced in the backend, covered by tests)
- Unapproved, edited-after-approval or already-sent drafts cannot be sent (409).
- A draft being sent cannot be edited, revoked or sent a second time at the same moment.
- Recipient must be exactly one valid address; line breaks in To/Subject are refused (no header injection).
- If Gmail clearly fails (bad address, expired login, no permission), the draft stays approved and the reason is shown; retry sends exactly one email.
- If the result is unclear (timeout or Gmail 5xx), the app does not guess: it says to check your Gmail Sent folder before trying again.
- Replies to a real Gmail message keep the same conversation (threadId, In-Reply-To, References).
- The send permission (`gmail.send`) is requested only on **Allow sending**. If you untick it on Google's screen, the read-only connection is kept.

## Activity log
Drafts tab → Activity log (also `GET /activity`). One line per approval, revoke, send, failure, connect and disconnect, with recipient and subject, never the email text. Stored in `data/activity.jsonl` (gitignored).

## Try it for real (needs your Google setup from `docs/day7_google_setup.md`)
Send a test email to your own second address first. Real delivery has not been tested against Google by the developer; it is tested with a fake Google (190 backend tests, 28 browser checks).
