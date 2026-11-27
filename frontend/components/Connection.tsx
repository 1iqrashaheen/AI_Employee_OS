"use client";

import { useState } from "react";
import { disconnectGoogle, startGoogleLogin } from "@/lib/api";
import { AuthStatus } from "@/lib/types";

export type Flash = { kind: "success" | "info" | "error"; text: string };

export default function Connection(props: {
  status: AuthStatus | null;
  loadError: string | null;
  flash: Flash | null;
  onRefresh: () => void;
  onUseGmail: () => void;
  onDisconnected: () => void;
}) {
  const { status, loadError } = props;
  const [busy, setBusy] = useState<"connect" | "disconnect" | "grant" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const connect = async (allowSend = false) => {
    setBusy(allowSend ? "grant" : "connect");
    setError(null);
    try {
      const { url } = await startGoogleLogin(allowSend);
      window.location.assign(url); // leave for Google's sign-in page; it sends the user back here
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the connection.");
      setBusy(null);
    }
  };

  const disconnect = async () => {
    if (!window.confirm("Disconnect Gmail? The app will forget this account and ask Google to revoke its access.")) return;
    setBusy("disconnect");
    setError(null);
    try {
      await disconnectGoogle();
      props.onDisconnected();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not disconnect.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="page">
      <div className="page-inner">
        <div className="page-head">
          <h2>Connect your email</h2>
        </div>

        {props.flash && (
          <div className={`card flash flash-${props.flash.kind}`} role={props.flash.kind === "error" ? "alert" : "status"}>
            {props.flash.text}
          </div>
        )}
        {error && (
          <div className="card card-error" role="alert">
            <p>{error}</p>
          </div>
        )}

        <section className="card" aria-labelledby="gmail-title">
          <h3 id="gmail-title">Gmail</h3>

          {loadError ? (
            <>
              <p>{loadError}</p>
              <div className="actions">
                <button className="btn" onClick={props.onRefresh}>
                  Try again
                </button>
              </div>
            </>
          ) : !status ? (
            <p role="status">Checking connection…</p>
          ) : !status.configured ? (
            <>
              <p>
                <strong>Not set up yet.</strong> The app works fine with the sample emails. To read your real Gmail, create a
                Google sign-in for this app (about 10 minutes, free). The step-by-step guide is in{" "}
                <code>docs/day7_google_setup.md</code>.
              </p>
              <ol className="steps">
                <li>In Google Cloud Console, create a project and turn on the Gmail API.</li>
                <li>Set up the consent screen as External, in Testing, and add your own Gmail address as a test user.</li>
                <li>
                  Create an OAuth client of type Web application with this redirect address:{" "}
                  <code>{status.redirect_uri}</code>
                </li>
                <li>
                  Put the client ID and secret in <code>.env</code> as <code>GOOGLE_CLIENT_ID</code> and{" "}
                  <code>GOOGLE_CLIENT_SECRET</code>, then restart the backend.
                </li>
              </ol>
              <p className="note">Still missing: {status.missing.join(", ")}.</p>
              <div className="actions">
                <button className="btn" onClick={props.onRefresh}>
                  Check again
                </button>
              </div>
            </>
          ) : status.connected ? (
            <>
              <p>
                <span className="badge badge-approved">Connected</span> as <strong>{status.email}</strong>
              </p>
              <ul className="perm-list">
                <li>
                  <strong>Read your email:</strong> allowed (read-only).
                </li>
                <li>
                  <strong>Send email:</strong>{" "}
                  {status.can_send
                    ? "allowed. Approved drafts are really sent from this account, always after you confirm."
                    : "not allowed yet. Allow it only when you want the app to send approved drafts."}
                </li>
              </ul>
              <div className="actions">
                <button className="btn btn-primary" onClick={props.onUseGmail}>
                  Show my inbox
                </button>
                <button className="btn" onClick={disconnect} disabled={busy === "disconnect"}>
                  {busy === "disconnect" ? "Disconnecting…" : "Disconnect"}
                </button>
                {!status.can_send && (
                  <button className="btn" onClick={() => connect(true)} disabled={busy === "grant"}>
                    {busy === "grant" ? "Opening Google…" : "Allow sending"}
                  </button>
                )}
              </div>
            </>
          ) : (
            <>
              {status.reauth_required && (
                <p className="notes-inline" role="status">
                  Access for <strong>{status.email ?? "your account"}</strong> expired or was revoked. While the app is in
                  Google&apos;s Testing mode, access lasts 7 days, so reconnecting now and then is normal.
                </p>
              )}
              <p>
                {status.reauth_required ? "Reconnect to keep reading your inbox." : "Connect your Gmail so the assistant can read your recent emails."}{" "}
                You will be sent to Google, then brought back here.
              </p>
              <ul className="perm-list">
                <li>It asks to <strong>read</strong> your email only. It cannot send, change or delete anything.</li>
                <li>
                  Google may say <em>&ldquo;Google hasn&apos;t verified this app&rdquo;</em>. That is expected for a test app: click{" "}
                  <strong>Advanced</strong>, then <strong>Continue</strong>.
                </li>
                <li>Only Gmail addresses added as test users in your Google Cloud project can sign in.</li>
                <li>On the permission screen, keep the box for reading your email ticked.</li>
              </ul>
              <div className="actions">
                <button className="btn btn-primary" onClick={() => connect()} disabled={busy === "connect"}>
                  {busy === "connect" ? "Opening Google…" : status.reauth_required ? "Reconnect Gmail" : "Connect Gmail (read-only)"}
                </button>
              </div>
            </>
          )}
        </section>

        <section className="card" aria-labelledby="privacy-title">
          <h3 id="privacy-title">What happens to your email</h3>
          <ul className="perm-list">
            <li>Nothing is ever sent unless you approved that exact draft and then confirmed in the send window.</li>
            <li>Your sign-in is stored in a file on this computer (not in the browser) and is never shown in the app.</li>
            <li>Real emails are kept in memory for a few minutes and are not saved to disk.</li>
            <li>Summarize, Prioritize and Reply send the email text to your chosen AI provider.</li>
            <li>Disconnecting forgets the account and asks Google to revoke the permission.</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
