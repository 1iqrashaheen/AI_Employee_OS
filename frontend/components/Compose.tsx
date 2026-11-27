"use client";

import { useEffect, useRef, useState } from "react";
import {
  approveDraft,
  createDraft,
  generateDraft,
  getEmail,
  revokeApproval,
  saveDraft,
  sendDraft,
  startGoogleLogin,
} from "@/lib/api";
import { formatDate, isValidRecipient, senderName } from "@/lib/format";
import { DraftRecord, DraftStatus, Email, TONES, Tone } from "@/lib/types";

type Busy = "generate" | "save" | "approve" | "revoke" | "send" | "grant" | null;

const STEPS: { id: DraftStatus; label: string }[] = [
  { id: "draft", label: "Draft" },
  { id: "approved", label: "Approved" },
  { id: "sent", label: "Sent" },
];

const messageOf = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong. Please try again.");

export default function Compose(props: {
  replyTo: Email | null;
  initialDraft: DraftRecord | null;
  sendMode: "mock" | "real" | "needs_permission" | "reconnect" | null;
  account: string | null; // the connected Gmail address, shown in the send confirmation
  onChanged: () => void;
  onSendFailed: () => void; // lets the app re-check the Gmail connection after a failed send
  onNew: () => void;
}) {
  const { initialDraft } = props;
  const [replyTo, setReplyTo] = useState<Email | null>(props.replyTo);
  const [instruction, setInstruction] = useState(initialDraft?.instruction ?? "");
  const [tone, setTone] = useState<Tone>("professional");
  const [recipient, setRecipient] = useState(initialDraft?.recipient ?? props.replyTo?.from ?? "");
  const [subject, setSubject] = useState(initialDraft?.subject ?? "");
  const [body, setBody] = useState(initialDraft?.body ?? "");
  const [record, setRecord] = useState<DraftRecord | null>(initialDraft);
  const [notes, setNotes] = useState<string[]>([]);
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = dialogRef.current;
    if (!d) return;
    if (confirming && !d.open) d.showModal();
    if (!confirming && d.open) d.close();
  }, [confirming]);

  // Opening a saved reply draft: load the email it answers so we can show it.
  useEffect(() => {
    const id = initialDraft?.reply_to_email_id;
    if (!props.replyTo && id) getEmail(id).then(setReplyTo).catch(() => undefined);
  }, [initialDraft, props.replyTo]);

  const status = record?.status ?? null;
  const locked = status === "sent";
  const unsaved =
    !!record && (subject !== record.subject || body !== record.body || recipient.trim() !== (record.recipient ?? ""));
  const recipientOk = isValidRecipient(recipient);
  const demo = props.sendMode === "mock" || props.sendMode === null;
  const needsPermission = props.sendMode === "needs_permission";
  const needsReconnect = props.sendMode === "reconnect";

  const canApprove = !!record && status === "draft" && !unsaved && recipientOk && !!subject.trim() && !!body.trim() && !busy;
  const canSend = !!record && status === "approved" && !unsaved && !busy && !needsPermission && !needsReconnect;

  /** Show exactly what the server stored (it trims whitespace), so "unsaved" never gets stuck on. */
  const adopt = (rec: DraftRecord) => {
    setRecord(rec);
    setSubject(rec.subject);
    setBody(rec.body);
    setRecipient(rec.recipient ?? "");
    props.onChanged();
  };

  const run = async (kind: Exclude<Busy, null>, work: () => Promise<void>) => {
    setBusy(kind);
    setError(null);
    try {
      await work();
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(null);
    }
  };

  const generate = () => {
    if (instruction.trim().length < 3) {
      setError("Tell the AI what the email should say (at least a few words).");
      return;
    }
    if (recipient.trim() && !recipientOk) {
      setError("That recipient is not a valid email address. Fix it or leave it empty.");
      return;
    }
    if (record && unsaved && !window.confirm("Replace your unsaved edits with a new draft?")) return;
    run("generate", async () => {
      const to = recipient.trim() || null;
      const gen = await generateDraft({
        instruction: instruction.trim(),
        tone,
        recipient: to,
        reply_to_email_id: replyTo?.id ?? null,
      });
      const content = { subject: gen.subject, body: gen.body, recipient: to };
      const rec = record
        ? await saveDraft(record.id, content)
        : await createDraft({ ...content, reply_to_email_id: replyTo?.id ?? null, instruction: instruction.trim() });
      adopt(rec);
      setNotes(gen.notes);
    });
  };

  const save = () =>
    run("save", async () => {
      if (!record) return;
      adopt(await saveDraft(record.id, { subject, body, recipient: recipient.trim() || null }));
    });
  const approve = () =>
    run("approve", async () => {
      if (record) adopt(await approveDraft(record.id));
    });
  const revoke = () =>
    run("revoke", async () => {
      if (record) adopt(await revokeApproval(record.id));
    });
  // Sending always goes through a confirmation step that shows exactly who gets what.
  const askToSend = () => {
    if (canSend) setConfirming(true);
  };
  const confirmSend = async () => {
    setConfirming(false);
    await run("send", async () => {
      if (!record) return;
      try {
        adopt(await sendDraft(record.id));
      } catch (e) {
        props.onSendFailed();
        throw e;
      }
    });
  };
  const allowSending = () =>
    run("grant", async () => {
      const { url } = await startGoogleLogin(true);
      window.location.assign(url); // Google asks for the send permission, then returns to the app
    });

  const stepIndex = STEPS.findIndex((s) => s.id === status);

  let approveHint = "";
  if (record && status === "draft") {
    if (unsaved) approveHint = "Save your changes before approving.";
    else if (!recipientOk) approveHint = "Add a valid recipient to approve.";
  }

  return (
    <div className="page">
      <div className="page-inner">
        <div className="page-head">
          <h2>{replyTo ? `Reply to ${senderName(replyTo.from)}` : "New email"}</h2>
          {(record || instruction || replyTo) && (
            <button className="btn" onClick={props.onNew} disabled={!!busy}>
              Start over
            </button>
          )}
        </div>

        {replyTo && (
          <details className="card reply-card">
            <summary>
              Replying to: <strong>{replyTo.subject}</strong> · {formatDate(replyTo.date)}
            </summary>
            {/* Plain text only. Email content is never rendered as HTML. */}
            <pre className="body-text">{replyTo.body}</pre>
          </details>
        )}

        <section className="card" aria-labelledby="step-ask">
          <h3 id="step-ask">1. Tell the AI what to write</h3>
          <div className="field">
            <label htmlFor="instruction">Instruction</label>
            <textarea
              id="instruction"
              rows={3}
              value={instruction}
              maxLength={2000}
              disabled={locked || busy === "generate"}
              placeholder={
                replyTo
                  ? "e.g. Say Friday at 3 PM works and ask for the agenda"
                  : "e.g. Tell John the quotation for 25 laptops will be ready by Friday"
              }
              onChange={(e) => setInstruction(e.target.value)}
            />
          </div>
          <div className="field-row">
            <div className="field grow">
              <label htmlFor="recipient">To</label>
              <input
                id="recipient"
                type="text"
                value={recipient}
                disabled={locked}
                placeholder="Name <name@example.com>"
                aria-invalid={!!recipient.trim() && !recipientOk}
                onChange={(e) => setRecipient(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="tone">Tone</label>
              <select id="tone" value={tone} disabled={locked} onChange={(e) => setTone(e.target.value as Tone)}>
                {TONES.map((t) => (
                  <option key={t} value={t}>
                    {t[0].toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="note">The AI only writes the text. It never sees the address and cannot change who the email goes to.</p>
          <div className="actions">
            <button className="btn btn-primary" onClick={generate} disabled={locked || !!busy || instruction.trim().length < 3}>
              {busy === "generate" ? "Writing…" : record ? "Generate again" : "Generate draft"}
            </button>
          </div>
        </section>

        {error && (
          <div className="card card-error" role="alert">
            <h3>Something went wrong</h3>
            <p>{error}</p>
          </div>
        )}

        {busy === "generate" && !record && (
          <div className="card" role="status" aria-label="Writing the draft">
            <div className="skeleton" />
            <div className="skeleton" />
            <div className="skeleton short" />
          </div>
        )}

        {record && (
          <>
            <section className="card" aria-labelledby="step-edit">
              <h3 id="step-edit">2. Review and edit</h3>
              {notes.length > 0 && (
                <ul className="notes" aria-label="Notes about this draft">
                  {notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              )}
              <div className="field">
                <label htmlFor="subject">Subject</label>
                <input
                  id="subject"
                  type="text"
                  value={subject}
                  maxLength={998}
                  readOnly={locked}
                  onChange={(e) => setSubject(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="body">Message</label>
                <textarea id="body" rows={12} value={body} readOnly={locked} onChange={(e) => setBody(e.target.value)} />
              </div>
              {!locked && (
                <div className="actions">
                  <button className="btn" onClick={save} disabled={!unsaved || !!busy}>
                    {busy === "save" ? "Saving…" : "Save changes"}
                  </button>
                  {unsaved && (
                    <span className="note" role="status">
                      Unsaved changes
                    </span>
                  )}
                  {!unsaved && status === "draft" && <span className="note">Saved</span>}
                </div>
              )}
              {status === "approved" && (
                <p className="note">Editing an approved draft removes the approval, so you always approve exactly what gets sent.</p>
              )}
            </section>

            <section className="card" aria-labelledby="step-approve">
              <h3 id="step-approve">3. Approve and send</h3>
              <ol className="stepper" aria-label="Draft progress">
                {STEPS.map((s, i) => (
                  <li
                    key={s.id}
                    className={i < stepIndex ? "done" : i === stepIndex ? "current" : "todo"}
                    aria-current={i === stepIndex ? "step" : undefined}
                  >
                    {s.label}
                  </li>
                ))}
              </ol>

              {status === "draft" && (
                <>
                  <p>Nothing is sent until you approve this draft.</p>
                  <div className="summary-box">
                    <div>
                      <strong>To:</strong> {record.recipient || <em>no recipient yet</em>}
                    </div>
                    <div>
                      <strong>Subject:</strong> {record.subject}
                    </div>
                  </div>
                  <div className="actions">
                    <button className="btn btn-primary" onClick={approve} disabled={!canApprove}>
                      {busy === "approve" ? "Approving…" : "Approve draft"}
                    </button>
                    <button className="btn" disabled title="Approve the draft first">
                      {demo ? "Send (demo)" : "Send email"}
                    </button>
                  </div>
                  {approveHint && <p className="note">{approveHint}</p>}
                </>
              )}

              {status === "approved" && (
                <>
                  <p>
                    <strong>Approved</strong>
                    {record.approved_at && ` on ${formatDate(record.approved_at)}`}. You can now send it.
                  </p>
                  <div className="summary-box">
                    <div>
                      <strong>To:</strong> {record.recipient}
                    </div>
                    <div>
                      <strong>Subject:</strong> {record.subject}
                    </div>
                  </div>
                  <div className="actions">
                    {needsPermission ? (
                      <button className="btn btn-primary" onClick={allowSending} disabled={!!busy || unsaved}>
                        {busy === "grant" ? "Opening Google…" : "Allow sending with Google"}
                      </button>
                    ) : (
                      <button className="btn btn-primary" onClick={askToSend} disabled={!canSend}>
                        {busy === "send" ? "Sending…" : demo ? "Send (demo)…" : "Send email…"}
                      </button>
                    )}
                    <button className="btn" onClick={revoke} disabled={!!busy}>
                      {busy === "revoke" ? "Revoking…" : "Revoke approval"}
                    </button>
                  </div>
                  {needsPermission && (
                    <p className="note">
                      Your Gmail is connected for reading only. To send, allow the sending permission on Google&apos;s screen. This
                      draft stays approved and saved.
                    </p>
                  )}
                  {needsReconnect && (
                    <p className="note">Gmail access expired. Reconnect Gmail on the Connect tab to send. This draft stays approved and saved.</p>
                  )}
                  {unsaved && <p className="note">Save or undo your edits first. Saving them removes the approval.</p>}
                </>
              )}

              {status === "sent" && (
                <div role="status">
                  <p>
                    <strong>Sent</strong>
                    {record.sent_at && ` on ${formatDate(record.sent_at)}`}.
                  </p>
                  {record.delivery === "gmail" && (
                    <p className="note">
                      Delivered through your Gmail account. You can see it in your Gmail Sent folder.
                    </p>
                  )}
                  {record.delivery === "mock" && (
                    <p className="note">
                      Demo mode: it was marked as sent, but no email was delivered because no email account is connected yet.
                    </p>
                  )}
                  <div className="actions">
                    <button className="btn btn-primary" onClick={props.onNew}>
                      Write another email
                    </button>
                  </div>
                </div>
              )}
            </section>

            <details className="card history">
              <summary>History ({record.history.length})</summary>
              <ul>
                {[...record.history].reverse().map((h, i) => (
                  <li key={i}>
                    <span className="note">{formatDate(h.at)}</span> {h.event}
                  </li>
                ))}
              </ul>
            </details>
          </>
        )}
      </div>

      <dialog ref={dialogRef} className="confirm" aria-labelledby="confirm-title" onClose={() => setConfirming(false)}>
        {record && (
          <div>
            <h3 id="confirm-title">{demo ? "Send this email (demo)?" : "Send this email now?"}</h3>
            <div className="summary-box">
              {!demo && props.account && (
                <div>
                  <strong>From:</strong> {props.account}
                </div>
              )}
              <div>
                <strong>To:</strong> {record.recipient}
              </div>
              <div>
                <strong>Subject:</strong> {record.subject}
              </div>
            </div>
            <pre className="body-text confirm-body">{record.body}</pre>
            <p className="note">
              {demo
                ? "Demo mode: the draft is marked as sent, but nothing is delivered."
                : "This really sends the email from your Gmail account. It cannot be undone."}
            </p>
            <div className="actions">
              <button className="btn btn-primary" onClick={confirmSend} autoFocus={false}>
                {demo ? "Send (demo)" : "Yes, send it"}
              </button>
              <button className="btn" onClick={() => setConfirming(false)} autoFocus>
                Cancel
              </button>
            </div>
          </div>
        )}
      </dialog>
    </div>
  );
}
