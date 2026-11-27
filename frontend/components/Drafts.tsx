"use client";

import { useCallback, useEffect, useState } from "react";
import { getActivity, listDrafts } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { ActivityEntry, DraftRecord } from "@/lib/types";

const LABEL = { draft: "Draft", approved: "Approved", sent: "Sent" } as const;

export default function Drafts(props: { active: boolean; refreshKey: number; onOpen: (d: DraftRecord) => void }) {
  const [drafts, setDrafts] = useState<DraftRecord[] | null>(null);
  const [activity, setActivity] = useState<ActivityEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    getActivity().then(setActivity).catch(() => setActivity(null)); // the log is secondary: never block the drafts
    try {
      setDrafts(await listDrafts());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load drafts.");
    }
  }, []);

  // Refresh whenever the tab is opened or a draft changed.
  useEffect(() => {
    if (props.active) load();
  }, [props.active, props.refreshKey, load]);

  return (
    <div className="page">
      <div className="page-inner">
        <div className="page-head">
          <h2>Drafts</h2>
        </div>
        {error ? (
          <div className="card card-error" role="alert">
            <p>{error}</p>
            <div className="actions">
              <button className="btn" onClick={load}>
                Try again
              </button>
            </div>
          </div>
        ) : drafts === null ? (
          <div className="empty" role="status">
            Loading drafts…
          </div>
        ) : drafts.length === 0 ? (
          <div className="empty">No drafts yet. Reply to an email or write a new one.</div>
        ) : (
          <ul className="draft-list">
            {drafts.map((d) => (
              <li key={d.id}>
                <button className="row draft-row" onClick={() => props.onOpen(d)}>
                  <div className="row-top">
                    <span className="row-from">{d.recipient || "No recipient yet"}</span>
                    <span className="row-date">{formatDate(d.updated_at)}</span>
                  </div>
                  <div className="row-subject">{d.subject}</div>
                  <span className={`badge badge-${d.status}`}>{LABEL[d.status]}</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        <section className="card activity" aria-labelledby="activity-title">
          <h3 id="activity-title">Activity log</h3>
          <p className="note">What this app did with your email account. Email text is never stored here.</p>
          {activity === null ? (
            <p className="note">The activity log is not available right now.</p>
          ) : activity.length === 0 ? (
            <p className="note">Nothing yet.</p>
          ) : (
            <ul className="activity-list">
              {activity.map((a, i) => (
                <li key={i}>
                  <span className="note">{formatDate(a.at)}</span> <strong>{a.label}</strong>
                  {a.to && <> to {a.to}</>}
                  {a.subject && <> · &ldquo;{a.subject}&rdquo;</>}
                  {a.delivery === "demo" && <span className="badge">demo</span>}
                  {a.event === "sent" && a.delivery === "gmail" && <span className="badge badge-sent">delivered</span>}
                  {(a.event === "send_failed" || a.event === "send_unknown") && a.detail && <div className="note">{a.detail}</div>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
