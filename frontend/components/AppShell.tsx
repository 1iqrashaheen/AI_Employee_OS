"use client";

import { useCallback, useEffect, useState } from "react";
import { getAuthStatus } from "@/lib/api";
import { AuthStatus, DraftRecord, Email, EmailSource } from "@/lib/types";
import Compose from "./Compose";
import Connection, { Flash } from "./Connection";
import Drafts from "./Drafts";
import Inbox from "./Inbox";

type Tab = "inbox" | "compose" | "drafts" | "connect";
const TABS: { id: Tab; label: string }[] = [
  { id: "inbox", label: "Inbox" },
  { id: "compose", label: "Compose" },
  { id: "drafts", label: "Drafts" },
  { id: "connect", label: "Connect" },
];

export default function AppShell() {
  const [tab, setTab] = useState<Tab>("inbox");
  const [seed, setSeed] = useState<{ key: number; replyTo: Email | null; draft: DraftRecord | null }>({
    key: 0,
    replyTo: null,
    draft: null,
  });
  const [draftsVersion, setDraftsVersion] = useState(0);
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [source, setSource] = useState<EmailSource>("sample");
  const [flash, setFlash] = useState<Flash | null>(null);

  const refreshAuth = useCallback(async () => {
    setAuthError(null);
    try {
      setAuth(await getAuthStatus());
    } catch (e) {
      setAuthError(e instanceof Error ? e.message : "Could not check the Gmail connection.");
    }
  }, []);

  useEffect(() => {
    refreshAuth();

    // Google sends the user back to /?google=connected (or denied, or error). Show the result, then tidy the address.
    const params = new URLSearchParams(window.location.search);
    const result = params.get("google");
    if (result) {
      if (result === "send_enabled") setFlash({ kind: "success", text: "Sending is now allowed. Open your approved draft in Drafts and send it." });
      else if (result === "connected") setFlash({ kind: "success", text: "Gmail is connected. You can now show your real inbox." });
      else if (result === "denied") setFlash({ kind: "info", text: "You cancelled the Google sign-in, so nothing was connected." });
      else setFlash({ kind: "error", text: params.get("reason") || "Connecting Gmail did not work. Please try again." });
      setTab("connect");
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, [refreshAuth]);

  // Opening the Connect tab always re-checks, so it never shows a stale "connected" after Google access expired.
  useEffect(() => {
    if (tab === "connect") refreshAuth();
  }, [tab, refreshAuth]);

  // If the connection goes away while the Gmail inbox is showing, fall back to the sample emails.
  const gmailEmail = auth?.connected ? auth.email : null;
  // demo: no Gmail connected (nothing is delivered) | needs_permission: connected for reading only | real: can send
  const sendMode: "mock" | "real" | "needs_permission" | "reconnect" | null = !auth ? null : auth.reauth_required ? "reconnect" : !auth.connected ? "mock" : auth.can_send ? "real" : "needs_permission";
  useEffect(() => {
    if (auth && !auth.connected && source === "gmail") setSource("sample");
  }, [auth, source]);

  // Every view stays mounted (just hidden), so the inbox keeps its selection and results when you switch tabs.
  const open = (next: { replyTo?: Email | null; draft?: DraftRecord | null }) => {
    setSeed((s) => ({ key: s.key + 1, replyTo: next.replyTo ?? null, draft: next.draft ?? null }));
    setTab("compose");
  };

  return (
    <div className="shell">
      <header className="appbar">
        <h1>AI Email Assistant</h1>
        <nav className="tabs" aria-label="Sections">
          {TABS.map((t) => (
            <button key={t.id} className="tab" aria-current={tab === t.id ? "page" : undefined} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        <span className="pills">
          {gmailEmail && (
            <span className="demo-pill pill-ok" title="Reading is connected. Nothing is changed in your mailbox.">
              Gmail: {gmailEmail}
            </span>
          )}
          {sendMode === "mock" && (
            <span className="demo-pill" title="No Gmail is connected. Send only marks a draft as sent; no email is delivered.">
              Demo sending
            </span>
          )}
          {sendMode === "needs_permission" && (
            <span className="demo-pill" title="Gmail is connected for reading only. Allow sending on the Connect tab.">
              Sending not allowed yet
            </span>
          )}
          {sendMode === "reconnect" && (
            <span className="demo-pill" title="Gmail access expired. Reconnect on the Connect tab before sending.">
              Reconnect Gmail to send
            </span>
          )}
          {sendMode === "real" && (
            <span className="demo-pill pill-live" title="Approved drafts are really sent from your Gmail account.">
              Live sending
            </span>
          )}
        </span>
      </header>
      <div className="views">
        <div className="view" hidden={tab !== "inbox"}>
          <Inbox
            onReply={(email) => open({ replyTo: email })}
            source={source}
            gmailEmail={gmailEmail}
            onSourceChange={setSource}
            onOpenConnect={() => setTab("connect")}
          />
        </div>
        <div className="view" hidden={tab !== "compose"}>
          <Compose
            key={seed.key}
            replyTo={seed.replyTo}
            initialDraft={seed.draft}
            sendMode={sendMode}
            account={gmailEmail}
            onSendFailed={refreshAuth}
            onChanged={() => setDraftsVersion((v) => v + 1)}
            onNew={() => open({})}
          />
        </div>
        <div className="view" hidden={tab !== "drafts"}>
          <Drafts active={tab === "drafts"} refreshKey={draftsVersion} onOpen={(d) => open({ draft: d })} />
        </div>
        <div className="view" hidden={tab !== "connect"}>
          <Connection
            status={auth}
            loadError={authError}
            flash={flash}
            onRefresh={refreshAuth}
            onUseGmail={() => {
              setSource("gmail");
              setTab("inbox");
            }}
            onDisconnected={() => {
              setFlash({ kind: "info", text: "Gmail was disconnected." });
              setSource("sample");
              refreshAuth();
            }}
          />
        </div>
      </div>
    </div>
  );
}
